"""Loads evaluation cases and builds the simulated world each case describes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from jalboot.db.models import (
    Address, Conversation, Customer, Driver, Merchant, Message, Order, OrderItem, PromoRedemption, Ticket,
)
from jalboot.env import ROOT

EVAL_DIR = ROOT / "eval"
SETS = ("support", "knowledge", "handoff", "redteam")
ORIGIN_PIN = (25.0, 51.0)
KM_PER_DEGREE = 111.195
DEFAULT_NOW = "2026-11-03T19:00:00+03:00"
UNKNOWN = {"en": "I don't know, can you check?", "ar": "ما أعرف، ممكن تتأكد؟"}


def load_cases(split: str, sets: tuple[str, ...] = SETS) -> list[dict[str, Any]]:
    cases = []
    for name in sets:
        path = EVAL_DIR / split / f"{name}.jsonl"
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                cases.extend(json.loads(line) for line in handle if line.strip())
    return cases


def case_now(case: dict[str, Any]) -> datetime:
    """Knowledge cases are questions with no world, so they have no clock of their own."""
    return datetime.fromisoformat(case.get("now", DEFAULT_NOW)).astimezone(timezone.utc)


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).astimezone(timezone.utc) if value else None


def _customer(row: dict[str, Any], now: datetime, claims: dict[str, Any] | None = None) -> Customer:
    extra = dict(row.get("extra") or {})
    if claims:
        extra.update(
            prior_claims_30d=claims.get("claims_30d", 0),
            prior_claims_90d=claims.get("claims_90d", 0),
            prior_claims_total_30d_dh=claims.get("claims_total_30d_dh", 0),
            prior_not_received_90d=claims.get("not_received_90d", 0),
            prior_goodwill_30d_dh=claims.get("goodwill_30d_dh", 0),
        )
    return Customer(
        id=row["id"],
        name=row.get("name", row["id"]),
        name_ar=row.get("name_ar", ""),
        phone=row.get("phone") or f"+974 0999 {abs(hash(row['id'])) % 10000:04d}",
        email=row.get("email") or f"{row['id'].lower()}@sim.jalboot.example",
        language=row.get("language", "en"),
        tier=row.get("tier", "standard"),
        wallet_dh=row.get("wallet_dh", 0),
        created_at=now - timedelta(days=int(row.get("account_age_days", 365))),
        extra=extra,
    )


def _order(row: dict[str, Any], state: dict[str, Any], now: datetime) -> Order:
    extra = dict(row.get("extra") or {})
    claims = state.get("claims") or {}
    fee_keys = ("service_fee_dh", "small_order_fee_dh", "peak_fee_dh", "weather_fee_dh")
    if (state.get("flags") or {}).get("severe_weather"):
        extra["severe_weather"] = True
    extra["prior_refunded_dh"] = (claims.get("refunded_on_order_dh") or {}).get(row["id"], 0)
    extra["prior_credit_dh"] = (claims.get("credit_on_order_dh") or {}).get(row["id"], 0)
    extra["pin_lat"], extra["pin_lng"] = ORIGIN_PIN
    order = Order(
        id=row["id"],
        customer_id=row["customer_id"],
        merchant_id=row.get("merchant_id"),
        driver_id=row.get("driver_id"),
        category=row["category"],
        status=row["status"],
        subtotal_dh=row.get("subtotal_dh", 0),
        delivery_fee_dh=row.get("delivery_fee_dh", 0),
        other_fees_dh=sum(int(extra.get(key, 0) or 0) for key in fee_keys),
        tip_dh=int(extra.get("tip_dh", 0) or 0),
        discount_dh=row.get("discount_dh", 0),
        total_dh=row.get("total_dh", 0),
        payment_method=row.get("payment_method", "card"),
        placed_at=_time(row.get("placed_at")) or now,
        promised_at=_time(row.get("promised_at")),
        delivered_at=_time(row.get("delivered_at")),
        address_text=row.get("address_text", ""),
        merchant_note=row.get("merchant_note", ""),
        customer_note=row.get("customer_note", ""),
        delay_reason=row.get("delay_reason", ""),
        extra=extra,
    )
    for item in row.get("items", []):
        order.items.append(OrderItem(
            name=item["name"], name_ar=item.get("name_ar", ""), quantity=item.get("quantity", 1),
            unit_price_dh=item.get("unit_price_dh", 0), extra=item.get("extra") or {},
        ))
    return order


def load_state(session: Session, case: dict[str, Any], conversation_id: str = "case") -> Conversation:
    """Writes one case's state to an empty database and returns its conversation."""
    now = case_now(case)
    state = case.get("state") or {}
    owner = state.get("customer") or {"id": "C-GUEST"}
    session.add(_customer(owner, now, state.get("claims")))

    known_customers = {owner["id"]}
    merchants: dict[str, Merchant] = {}
    drivers: dict[str, Driver] = {}
    orders = state.get("orders") or []
    for row in orders:
        other = row["customer_id"]
        if other not in known_customers:
            known_customers.add(other)
            session.add(_customer({"id": other}, now))
        merchant = row.get("merchant_id")
        if merchant and merchant not in merchants:
            merchants[merchant] = Merchant(
                id=merchant, name=row.get("merchant_name", merchant), name_ar=row.get("merchant_name_ar", ""),
                category=row["category"], zone="",
            )
        driver = row.get("driver_id")
        if driver and driver not in drivers:
            drivers[driver] = Driver(id=driver, name=row.get("driver_name", "Driver"))
    session.add_all(merchants.values())
    session.add_all(drivers.values())
    session.flush()
    session.add_all(_order(row, state, now) for row in orders)
    session.flush()

    for index, row in enumerate(state.get("addresses") or []):
        distance = float(row.get("distance_km_from_order_pin", 0.0))
        session.add(Address(
            id=row.get("id", f"A-{index}"), customer_id=owner["id"], label=row.get("label", ""),
            zone=row.get("zone", ""), line=row.get("line", ""),
            lat=ORIGIN_PIN[0] + distance / KM_PER_DEGREE, lng=ORIGIN_PIN[1],
        ))

    cart = state.get("cart")
    if cart:
        session.add(Order(
            id=f"BASKET-{owner['id']}", customer_id=owner["id"], category=cart.get("category", "food"),
            status="basket", subtotal_dh=cart.get("subtotal_dh", 0),
            delivery_fee_dh=cart.get("delivery_fee_dh", 0), total_dh=cart.get("subtotal_dh", 0),
            placed_at=now, address_text=cart.get("zone", ""),
        ))
        session.flush()

    for row in state.get("promo_redemptions") or []:
        at = _time(row.get("created_at")) or now
        session.add(PromoRedemption(
            code=row["code"], period=row.get("period") or at.strftime("%Y-%m"), customer_id=owner["id"],
            order_id=row.get("order_id") or (orders[0]["id"] if orders else ""), amount_dh=row.get("amount_dh", 0),
            created_at=at,
        ))
    for index, row in enumerate(state.get("tickets") or []):
        session.add(Ticket(
            id=row.get("id", f"T-{index}"), customer_id=owner["id"], order_id=row.get("order_id"),
            category=row.get("category", "other"), status=row.get("status", "open"),
            subject=row.get("subject", ""), created_at=_time(row.get("created_at")) or now,
        ))

    session_state = state.get("session") or {}
    verified = bool(session_state.get("verified"))
    conversation = Conversation(
        id=conversation_id,
        customer_id=owner["id"] if verified else None,
        verified_at=now if verified else None,
        language=session_state.get("language", case.get("lang", "en")),
        failures=int(session_state.get("failures", 0)),
        first_report_at=_time(session_state.get("first_report_at")),
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    session.flush()
    for turn in case.get("history") or []:
        session.add(Message(conversation_id=conversation.id, role=turn["role"], text=turn["text"], created_at=now))
    session.commit()
    return conversation


def complete_identity(session: Session, conversation: Conversation, case: dict[str, Any]) -> bool:
    """Plays the identity check the way the case says it goes. Only a passing check
    binds the customer, the same as the real endpoints."""
    state = case.get("state") or {}
    if (state.get("session") or {}).get("verification") != "pass":
        return False
    conversation.customer_id = state["customer"]["id"]
    conversation.verified_at = case_now(case)
    session.commit()
    return True
