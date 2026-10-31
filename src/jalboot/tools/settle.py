"""The one place money moves.

The bot, the approval queue and cancellation all pay through these functions, so they
cannot disagree about where money goes. Each writes the refund row and moves the wallet
in the caller's transaction, and the row's unique key means a repeat cannot pay twice.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from jalboot.db.models import Customer, Order, Refund
from jalboot.policy import engine
from jalboot.policy.rules import Rules
from jalboot.tools.facts import COMPENSATION, order_facts


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def add_to_wallet(session: Session, customer: Customer, amount_dh: int) -> None:
    """In SQL, so two credits at once cannot overwrite each other."""
    session.execute(
        update(Customer).where(Customer.id == customer.id).values(wallet_dh=Customer.wallet_dh + amount_dh)
        .execution_options(synchronize_session=False)
    )
    session.refresh(customer, ["wallet_dh"])


class WalletFull(Exception):
    """REF-04: on a cash order, only a person can place what the wallet cannot hold."""


@dataclass(frozen=True)
class Settlement:
    refund: Refund
    original_dh: int
    credit_dh: int


def settle_refund(
    session: Session,
    rules: Rules,
    order: Order,
    amount_dh: int,
    *,
    reason: str,
    key: str,
    approved_by: str,
    now: datetime,
    items: list[dict[str, Any]] | None = None,
    method: str | None = None,
    approval_id: str | None = None,
) -> Settlement:
    """Splits a refund under REF-04, records it and credits the wallet."""
    customer = order.customer
    session.refresh(customer, ["wallet_dh"])
    original, credit, overflow = engine.refund_split(
        rules, order_facts(order), amount_dh, customer.wallet_dh, to_credit=method == "refund_credit",
    )
    if overflow:
        raise WalletFull
    refund = Refund(
        id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=amount_dh,
        method=engine.refund_method(original, credit), reason=reason, items=items or [],
        approved_by=approved_by, approval_id=approval_id, created_at=now, idempotency_key=key,
    )
    session.add(refund)
    if credit:
        add_to_wallet(session, customer, credit)
    return Settlement(refund, original, credit)


def settle_credit(
    session: Session,
    order: Order,
    amount_dh: int,
    *,
    reason: str,
    key: str,
    approved_by: str,
    now: datetime,
    approval_id: str | None = None,
) -> Refund:
    """Compensation credit, which only ever goes to the wallet."""
    refund = Refund(
        id=new_id("R"), order_id=order.id, customer_id=order.customer_id, amount_dh=amount_dh,
        method=COMPENSATION, reason=reason, approved_by=approved_by, approval_id=approval_id,
        created_at=now, idempotency_key=key,
    )
    session.add(refund)
    add_to_wallet(session, order.customer, amount_dh)
    return refund
