"""Human decisions on actions the bot may only propose.

The approval queue is the only way a pending claim becomes money, and only a signed-in
person reaches this code. An order can change between filing and deciding, so every
limit that applied at filing is checked again here, with the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.db.models import Approval, Conversation, Order, Refund, StaffUser
from jalboot.policy import engine
from jalboot.policy.rules import Rules, to_qar
from jalboot.tools.facts import claim_facts, order_facts, refunded_items
from jalboot.tools.settle import WalletFull, settle_credit, settle_refund

ROLE_RANK = {"agent": 1, "supervisor": 2, "finance_lead": 3}
LOCKED_AFTER_PICKUP = {"picked_up", "on_the_way", "delivered", "cancelled", "failed_customer"}


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


def _move_order(rules: Rules, approval: Approval, order: Order) -> None:
    extra = dict(order.extra or {})
    limit = int(rules.get("account.address_change.max_per_order"))
    if order.category != "parcel" and (order.status in LOCKED_AFTER_PICKUP or int(extra.get("address_changes", 0)) >= limit):
        raise DecisionError("address_change_no_longer_possible")
    order.address_text = str(approval.payload.get("new_address", ""))
    order.address_id = None
    extra["address_changes"] = int(extra.get("address_changes", 0)) + 1
    order.extra = extra


def _check_item_refund(session: Session, approval: Approval, order: Order) -> None:
    """The same unit may have been paid since this claim was filed."""
    done = refunded_items(session, order.id, include_pending=False)
    for entry in (approval.payload or {}).get("items") or []:
        if done.get(entry["name"], 0) >= int(entry["units"]):
            raise DecisionError("item_already_refunded")


def _pay(session: Session, rules: Rules, approval: Approval, staff: StaffUser, now: datetime) -> Refund | None:
    order = session.get(Order, approval.order_id)
    if approval.kind == "address_change":
        _move_order(rules, approval, order)
        return None

    customer = order.customer
    payload = approval.payload or {}
    reason = str(payload.get("reason") or approval.reason)
    claims = claim_facts(session, customer, order, now)
    if approval.kind == "credit":
        if claims.credit_on_order_dh + approval.amount_dh > rules.dh("compensation_credit_cap_per_order_qar"):
            raise DecisionError("credit_cap_per_order")
        if customer.wallet_dh + approval.amount_dh > rules.dh("credit_wallet.max_balance_qar"):
            raise DecisionError("wallet_at_limit")
        return settle_credit(
            session, order, approval.amount_dh, reason=reason, key=approval.idempotency_key,
            approved_by=staff.id, now=now, approval_id=approval.id,
        )

    # A parcel payout follows its cover (PCL-03), not the amount paid.
    room = engine.remaining_refundable_dh(order_facts(order), claims)
    if order.category != "parcel" and approval.amount_dh > room:
        raise DecisionError("amount_exceeds_paid")
    _check_item_refund(session, approval, order)
    try:
        return settle_refund(
            session, rules, order, approval.amount_dh, reason=reason, key=approval.idempotency_key,
            approved_by=staff.id, now=now, items=list(payload.get("items") or []),
            method=payload.get("method"), approval_id=approval.id,
        ).refund
    except WalletFull:
        raise DecisionError("wallet_at_limit") from None


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
