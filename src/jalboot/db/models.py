"""Tables for the simulated world and for the support system around it.

Money is stored as whole dirhams (1 QAR = 100 dirhams) in columns ending in _dh.
Floats would round, and a refund limit that is off by a fraction is a real bug.

Several safety rules also live here as constraints, so that they hold even if
application code has a bug: a refund or approval key can only exist once, and an
amount cannot be zero or negative.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jalboot.db.base import Base, UTCDateTime, utcnow


class WorldMeta(Base):
    """One row saying how this simulated world was generated."""

    __tablename__ = "world_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    anchor: Mapped[datetime] = mapped_column(UTCDateTime)
    notice: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(160))
    language: Mapped[str] = mapped_column(String(2), default="en")
    tier: Mapped[str] = mapped_column(String(16), default="standard")
    wallet_dh: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    addresses: Mapped[list["Address"]] = relationship(back_populates="customer")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    label: Mapped[str] = mapped_column(String(40))
    zone: Mapped[str] = mapped_column(String(60))
    line: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(default=0.0)
    lng: Mapped[float] = mapped_column(default=0.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped[Customer] = relationship(back_populates="addresses")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(120), default="")
    category: Mapped[str] = mapped_column(String(16), index=True)
    zone: Mapped[str] = mapped_column(String(60))
    rating: Mapped[float] = mapped_column(default=4.5)
    prep_minutes: Mapped[int] = mapped_column(Integer, default=15)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    vehicle: Mapped[str] = mapped_column(String(16), default="motorbike")
    zone: Mapped[str] = mapped_column(String(60), default="")
    rating: Mapped[float] = mapped_column(default=4.7)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    driver_id: Mapped[Optional[str]] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    subtotal_dh: Mapped[int] = mapped_column(Integer, default=0)
    delivery_fee_dh: Mapped[int] = mapped_column(Integer, default=0)
    other_fees_dh: Mapped[int] = mapped_column(Integer, default=0)
    tip_dh: Mapped[int] = mapped_column(Integer, default=0)
    discount_dh: Mapped[int] = mapped_column(Integer, default=0)
    total_dh: Mapped[int] = mapped_column(Integer, default=0)
    payment_method: Mapped[str] = mapped_column(String(16), default="card")
    placed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    promised_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    address_id: Mapped[Optional[str]] = mapped_column(ForeignKey("addresses.id"), nullable=True)
    address_text: Mapped[str] = mapped_column(String(240), default="")
    # Free text written by a merchant or customer. It is data: it is shown to the
    # model inside a marked block and never treated as an instruction.
    merchant_note: Mapped[str] = mapped_column(Text, default="")
    customer_note: Mapped[str] = mapped_column(Text, default="")
    delay_reason: Mapped[str] = mapped_column(String(32), default="")
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    merchant: Mapped[Optional[Merchant]] = relationship()
    driver: Mapped[Optional[Driver]] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.at"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    name_ar: Mapped[str] = mapped_column(String(160), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_dh: Mapped[int] = mapped_column(Integer, default=0)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    order: Mapped[Order] = relationship(back_populates="items")


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = mapped_column(UTCDateTime)
    detail: Mapped[str] = mapped_column(Text, default="")

    order: Mapped[Order] = relationship(back_populates="events")


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (UniqueConstraint("code", "customer_id", "period", name="uq_promo_per_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32))
    # A calendar month such as 2026-11, or "once" for a code with a lifetime limit.
    period: Mapped[str] = mapped_column(String(8))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    amount_dh: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    # Set only by a successful identity check, never from anything the model says.
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    status: Mapped[str] = mapped_column(String(16), default="bot", index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    assigned_staff_id: Mapped[Optional[str]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    token_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    order_id: Mapped[str] = mapped_column(String(32), default="")
    handoff_reason: Mapped[str] = mapped_column(String(32), default="")
    handoff_summary: Mapped[str] = mapped_column(Text, default="")
    handoff_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(16), default="")
    topic: Mapped[str] = mapped_column(String(32), default="")
    failures: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    turn_state: Mapped[str] = mapped_column(String(20), default="")
    language: Mapped[str] = mapped_column(String(2), default="en")
    citations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[str] = mapped_column(String(12), default="normal")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(2), default="en")
    source: Mapped[str] = mapped_column(String(16), default="seed")
    csat: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(16), default="")
    first_reply_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)


class Approval(Base):
    """An action the bot may ask for and only a person may allow."""

    __tablename__ = "approvals"
    __table_args__ = (CheckConstraint("amount_dh >= 0", name="ck_approval_amount"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[Optional[str]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    amount_dh: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    required_role: Mapped[str] = mapped_column(String(16), default="agent")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount_dh > 0", name="ck_refund_positive"),
        Index("ix_refund_customer_time", "customer_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    amount_dh: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32))
    items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    approved_by: Mapped[str] = mapped_column(String(32), default="policy")
    approval_id: Mapped[Optional[str]] = mapped_column(ForeignKey("approvals.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)


class ActionRecord(Base):
    """The stored result of a state-changing tool call, keyed for idempotency."""

    __tablename__ = "action_records"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    tool: Mapped[str] = mapped_column(String(32))
    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditEvent(Base):
    """Append-only log. Each row holds a hash of the row before it, so an edit or a
    deleted row breaks the chain and can be detected."""

    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(48), index=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="agent")
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WebSession(Base):
    """A browser session. Only a hash of the cookie value is stored, so a copy of
    the database cannot be used to sign in."""

    __tablename__ = "web_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    staff_id: Mapped[Optional[str]] = mapped_column(ForeignKey("staff_users.id"), nullable=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    phone_key: Mapped[str] = mapped_column(String(64), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class LoginThrottle(Base):
    __tablename__ = "login_throttle"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    blocked_until: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
