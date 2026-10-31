"""Reads facts from the database for the policy engine."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jalboot.db.models import Approval, Customer, Order, OrderItem, Refund
from jalboot.policy.engine import NOT_CLAIMS, ClaimFacts, ItemFact, OrderFacts

COMPENSATION = "compensation"


def _item_fact(item: OrderItem) -> ItemFact:
    extra = item.extra or {}
    free = 0
    if extra.get("offer") == "buy_one_get_one":
        free = item.quantity - int(extra.get("charged_units", item.quantity))
    return ItemFact(
        item.name, item.quantity, item.unit_price_dh, not extra.get("prescription"),
        free_units=max(free, 0), approved_substitute=bool(extra.get("customer_approved")),
        chilled=bool(extra.get("chilled")), cold_chain=bool(extra.get("cold_chain")),
    )


def order_facts(order: Order) -> OrderFacts:
    extra = order.extra or {}

    def moment(name: str) -> datetime | None:
        value = extra.get(name)
        return datetime.fromisoformat(value) if value else None

    charges = tuple(
        (datetime.fromisoformat(row["at"]), int(row["amount_dh"]), str(row.get("kind", "final")))
        for row in extra.get("charges") or ()
    )
    return OrderFacts(
        id=order.id,
        category=order.category,
        status=order.status,
        placed_at=order.placed_at,
        promised_at=order.promised_at,
        delivered_at=order.delivered_at,
        subtotal_dh=order.subtotal_dh,
        discount_dh=order.discount_dh,
        delivery_fee_dh=order.delivery_fee_dh,
        other_fees_dh=order.other_fees_dh,
        tip_dh=order.tip_dh,
        payment_method=order.payment_method,
        severe_weather=bool(extra.get("severe_weather")),
        failed_contact=bool(extra.get("failed_contact")),
        proof_of_delivery=bool(extra.get("proof_of_delivery")),
        gps_distance_m=extra.get("gps_distance_m"),
        items=tuple(_item_fact(item) for item in order.items),
        estimate_at=moment("estimate_at"),
        iftar_window=bool(extra.get("iftar_window")),
        cancelled_by=str(extra.get("cancelled_by") or ""),
        scheduled_slot_at=moment("scheduled_slot_at"),
        charges=charges,
        open_bank_dispute=bool(extra.get("open_bank_dispute")),
        cold_chain=any((item.extra or {}).get("cold_chain") for item in order.items),
        credit_paid_dh=int(extra.get("credit_paid_dh") or 0),
        final_subtotal_dh=extra.get("final_subtotal_dh"),
        cancelled_at=moment("cancelled_at"),
        status_at_first_request=str(extra.get("status_at_first_request") or ""),
        driver_wait_minutes=extra.get("driver_wait_minutes"),
        driver_calls=extra.get("driver_calls"),
        left_for_safety=bool(extra.get("left_for_safety")),
        change_short_dh=int(extra.get("driver_change_short_dh") or 0),
        leave_at_door=bool(extra.get("leave_at_door")),
        declared_value_dh=extra.get("declared_value_dh"),
        documents=bool(extra.get("documents")),
        extended_cover=bool(extra.get("extended_cover")),
    )


def claim_facts(session: Session, customer: Customer, order: Order | None, now: datetime) -> ClaimFacts:
    """Works out history from the refunds table. Figures the customer or the model
    states are never used here."""
    refunded = credited = late_credit = late_fee = 0
    if order is not None:
        rows = session.scalars(select(Refund).where(Refund.order_id == order.id)).all()
        refunded = sum(r.amount_dh for r in rows if r.method != COMPENSATION)
        credited = sum(r.amount_dh for r in rows if r.method == COMPENSATION)
        late_credit = sum(r.amount_dh for r in rows if r.reason == "late_delivery")
        late_fee = sum(r.amount_dh for r in rows if r.reason == "late_delivery_fee")

    history = session.scalars(select(Refund).where(Refund.customer_id == customer.id)).all()

    def since(days: int) -> list[Refund]:
        return [r for r in history if r.created_at >= now - timedelta(days=days)]

    claims_30 = [r for r in since(30) if r.reason not in NOT_CLAIMS]
    claims_90 = [r for r in since(90) if r.reason not in NOT_CLAIMS]
    return ClaimFacts(
        refunded_on_order_dh=refunded,
        credit_on_order_dh=credited,
        claims_30d=len(claims_30),
        claims_90d=len(claims_90),
        claims_total_30d_dh=sum(r.amount_dh for r in claims_30),
        not_received_90d=sum(1 for r in since(90) if r.reason == "not_received"),
        goodwill_30d_dh=sum(r.amount_dh for r in since(30) if r.reason == "goodwill"),
        account_age_days=max((now - customer.created_at).days, 0),
        wallet_dh=customer.wallet_dh,
        late_credit_on_order_dh=late_credit,
        late_fee_refunded_dh=late_fee,
    )


def refunded_items(session: Session, order_id: str, *, include_pending: bool = True) -> dict[str, int]:
    """Units already claimed, by item. Claims waiting for a person count, so one item
    cannot be filed twice and then approved twice."""
    done: dict[str, int] = {}
    rows = list(session.scalars(select(Refund.items).where(Refund.order_id == order_id)))
    if include_pending:
        waiting = select(Approval.payload).where(Approval.order_id == order_id, Approval.status == "pending")
        rows.extend((payload or {}).get("items") for payload in session.scalars(waiting))
    for items in rows:
        for entry in items or []:
            done[entry["name"]] = max(done.get(entry["name"], 0), int(entry["units"]))
    return done


def order_count(session: Session, customer_id: str, status: str) -> int:
    return session.scalar(
        select(func.count()).select_from(Order).where(Order.customer_id == customer_id, Order.status == status)
    ) or 0
