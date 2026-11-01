"""Human decisions on actions the bot may only propose.

The approval queue is the only way a pending claim becomes money, and only a signed-in
person reaches this code. An order can change between filing and deciding, so the same
rules run again here on what is true now, including which role may approve it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.db.models import Approval, Conversation, Order, Refund, StaffUser
from jalboot.policy import engine
from jalboot.policy.rules import Rules, to_qar
from jalboot.tools.facts import MONEY_KINDS, claim_facts, order_facts, refunded_items
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


def _role_after_payment(rules: Rules, approval: Approval, claims: engine.ClaimFacts) -> str:
    """REF-05 goes by the total on the order, so small approvals cannot add up past a
    role's limit. PAY-03 stands apart, because that money was never owed. A role can
    only rise from the one set at filing."""
    if approval.reason == "duplicate_charge":
        return approval.required_role
    total = claims.refunded_on_order_dh + claims.credit_on_order_dh + approval.amount_dh
    return max(engine.approval_role(rules, total), approval.required_role, key=lambda role: ROLE_RANK.get(role, 99))


def _recheck(rules: Rules, approval: Approval, order: Order, claims: engine.ClaimFacts) -> None:
    """The rules that filed this claim, on today's facts. The time stays the customer's
    report, because a person taking a day to decide must not close the window. Sending
    a claim to a person is not an objection here: this is that person."""
    payload = approval.payload or {}
    recorded = payload.get("reported_at")
    reported = datetime.fromisoformat(recorded) if recorded else approval.created_at
    reason = str(payload.get("reason") or approval.reason)
    facts = order_facts(order)
    if approval.kind == "credit":
        decision = engine.decide_credit(
            rules, facts, claims, approval.amount_dh, reason, reported, photo_provided=True,
        )
    else:
        decision = engine.decide_refund(
            rules, facts, claims, approval.amount_dh, reason, reported, photo_provided=True,
            window_reason=payload.get("window_reason"),
        )
    if decision.outcome == engine.DENY or decision.code == "wallet_at_limit":
        raise DecisionError(decision.code)


def _pay(
    session: Session, rules: Rules, approval: Approval, staff: StaffUser, now: datetime,
    claims: engine.ClaimFacts | None,
) -> Refund | None:
    order = session.get(Order, approval.order_id)
    if approval.kind == "address_change":
        _move_order(rules, approval, order)
        return None

    payload = approval.payload or {}
    reason = str(payload.get("reason") or approval.reason)
    _recheck(rules, approval, order, claims)
    if approval.kind == "credit":
        return settle_credit(
            session, order, approval.amount_dh, reason=reason, key=approval.idempotency_key,
            approved_by=staff.id, now=now, approval_id=approval.id,
        )

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
        claims = None
        if action == "approve" and approval.kind in MONEY_KINDS:
            order = session.get(Order, approval.order_id)
            claims = claim_facts(session, order.customer, order, now, rules, excluding=approval.id)
            approval.required_role = _role_after_payment(rules, approval, claims)
        if not can_decide(staff.role, approval):
            audit.record(
                session, actor_type="staff", actor_id=staff.id, action="guardrail.blocked", outcome="denied",
                conversation_id=approval.conversation_id, customer_id=approval.customer_id,
                order_id=approval.order_id,
                detail={"reason": "approval_limit_exceeded", "approval_id": approval.id},
            )
            session.commit()
            raise DecisionError("approval_limit_exceeded")

        refund = _pay(session, rules, approval, staff, now, claims) if action == "approve" else None
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
