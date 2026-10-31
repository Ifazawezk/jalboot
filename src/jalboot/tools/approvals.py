"""Human decisions on actions the bot may only propose.

The approval queue is the only way a pending refund becomes money, and only a signed-in
person reaches this code. The limits are checked again at decision time, because the
order may have changed since the claim was filed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.db.models import Approval, Conversation, Order, Refund, StaffUser
from jalboot.policy import engine
from jalboot.policy.rules import Rules, to_qar
from jalboot.tools.executor import new_id
from jalboot.tools.facts import COMPENSATION, claim_facts, order_facts

ROLE_RANK = {"agent": 1, "supervisor": 2, "finance_lead": 3}


class DecisionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def can_decide(role: str, approval: Approval) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(approval.required_role, 99)


@dataclass
class Outcome:
    approval: Approval
    refund: Refund | None


def _pay(session: Session, rules: Rules, approval: Approval, staff: StaffUser, now: datetime) -> Refund | None:
    order = session.get(Order, approval.order_id)
    customer = order.customer
    if approval.kind == "address_change":
        order.address_text = str(approval.payload.get("new_address", ""))
        order.address_id = None
        extra = dict(order.extra or {})
        extra["address_changes"] = int(extra.get("address_changes", 0)) + 1
        order.extra = extra
        return None

    facts = order_facts(order)
    # The cap can have moved since filing, so it is enforced again here. A parcel payout
    # follows its cover (PCL-03), not the amount paid.
    room = engine.remaining_refundable_dh(facts, claim_facts(session, customer, order, now))
    if order.category != "parcel" and approval.amount_dh > room:
        raise DecisionError("amount_exceeds_paid")
    if approval.kind == "credit":
        method, credit_part = COMPENSATION, approval.amount_dh
    else:
        original, credit_part, overflow = engine.refund_split(rules, facts, approval.amount_dh, customer.wallet_dh)
        if overflow:
            raise DecisionError("wallet_at_limit")
        method = engine.refund_method(original, credit_part)
    refund = Refund(
        id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=approval.amount_dh,
        method=method, reason=str(approval.payload.get("reason") or approval.reason),
        items=list(approval.payload.get("items") or []), approved_by=staff.id, approval_id=approval.id,
        created_at=now, idempotency_key=approval.idempotency_key,
    )
    session.add(refund)
    customer.wallet_dh += credit_part
    return refund


def decide(
    session: Session,
    approval_id: str,
    staff: StaffUser,
    action: str,
    note: str,
    version: int,
    now: datetime,
    rules: Rules,
) -> Outcome:
    with audit.serial_write(session):
        approval = session.get(Approval, approval_id)
        if approval is None:
            raise DecisionError("not_found")
        if approval.status != "pending" or approval.version != version:
            raise DecisionError("refund_already_decided")
        if not can_decide(staff.role, approval):
            audit.record(
                session, actor_type="staff", actor_id=staff.id, action="guardrail.blocked", outcome="denied",
                conversation_id=approval.conversation_id, customer_id=approval.customer_id,
                order_id=approval.order_id,
                detail={"reason": "approval_limit_exceeded", "approval_id": approval.id},
            )
            session.commit()
            raise DecisionError("approval_limit_exceeded")

        refund = _pay(session, rules, approval, staff, now) if action == "approve" else None
        approval.status = "approved" if action == "approve" else "rejected"
        approval.decided_at = now
        approval.decided_by = staff.id
        approval.decision_note = note.strip()
        approval.version += 1
        audit.record(
            session, actor_type="staff", actor_id=staff.id,
            action="refund.approved" if action == "approve" else "refund.rejected",
            outcome="allowed", conversation_id=approval.conversation_id, customer_id=approval.customer_id,
            order_id=approval.order_id,
            detail={"approval_id": approval.id, "amount_qar": to_qar(approval.amount_dh), "kind": approval.kind},
        )
        if approval.conversation_id:
            conversation = session.get(Conversation, approval.conversation_id)
            if conversation is not None:
                conversation.updated_at = now
    return Outcome(approval, refund)
