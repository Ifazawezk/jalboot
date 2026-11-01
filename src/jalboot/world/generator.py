"""Generates the simulated world from a seed.

The same seed and anchor always give the same rows, because every choice comes
from one seeded random source and nothing reads the real clock. Phone numbers
start with 0 after the country code, which no real Qatari number does, and email
addresses use the reserved .example domain, so no record can reach a real person.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot.db.models import (
    Address, Customer, Driver, Merchant, Order, OrderEvent, OrderItem, Ticket, WorldMeta,
)
from jalboot.policy.rules import Rules, percent_of, to_dh
from jalboot.world import catalog

DEFAULT_ANCHOR = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)  # 18:00 in Doha
PAYMENT_METHODS = ("card", "card", "card", "wallet", "cash")


def _fake_phone(index: int) -> str:
    return f"+974 0{index:03d} {index * 37 % 10000:04d}"


class WorldBuilder:
    def __init__(self, seed: int, anchor: datetime, rules: Rules):
        self.random = random.Random(seed)
        self.seed = seed
        self.anchor = anchor
        self.rules = rules
        self.fee_zone = {
            area: letter for letter, zone in rules.get("fees.zones").items() for area in zone["areas"]
        }
        self.customers: list[Customer] = []
        self.addresses: dict[str, list[Address]] = {}
        self.merchants: list[Merchant] = []
        self.drivers: list[Driver] = []
        self.orders: list[Order] = []
        self.tickets: list[Ticket] = []

    def _name(self) -> tuple[str, str]:
        first, first_ar = self.random.choice(catalog.FIRST_NAMES)
        last, last_ar = self.random.choice(catalog.LAST_NAMES)
        return f"{first} {last}", f"{first_ar} {last_ar}"

    def _when(self, days_back: int) -> datetime:
        minutes = self.random.randrange(1, max(days_back, 1) * 24 * 60)
        return self.anchor - timedelta(minutes=minutes)

    def build_customers(self, count: int) -> None:
        for index in range(count):
            number = 1100 + index
            name, name_ar = self._name()
            customer = Customer(
                id=f"C-{number}",
                name=name,
                name_ar=name_ar,
                phone=_fake_phone(index + 100),
                email=f"customer{number}@sim.jalboot.example",
                language="ar" if self.random.random() < 0.45 else "en",
                tier=self.random.choices(("standard", "plus"), (80, 20))[0],
                wallet_dh=self.random.choice((0, 0, 0, 500, 1000, 2500)),
                created_at=self._when(700),
            )
            self.customers.append(customer)
            zones = self.random.sample(catalog.ZONES, self.random.choice((1, 2, 2, 3)))
            saved = []
            for position, (zone, _zone_ar, lat, lng) in enumerate(zones):
                saved.append(Address(
                    id=f"A-{number}-{position + 1}",
                    customer_id=customer.id,
                    label=("Home", "Work", "Family")[position],
                    zone=zone,
                    line=f"Zone {self.random.randrange(10, 90)}, Street {self.random.randrange(100, 980)}, "
                         f"Building {self.random.randrange(1, 120)}, {zone}",
                    lat=round(lat + self.random.uniform(-0.01, 0.01), 5),
                    lng=round(lng + self.random.uniform(-0.01, 0.01), 5),
                ))
            self.addresses[customer.id] = saved

    def build_merchants(self) -> None:
        number = 200
        for category, names in catalog.MERCHANTS.items():
            for name, name_ar in names:
                for zone, zone_ar, _lat, _lng in self.random.sample(catalog.ZONES, 2 if category == "food" else 1):
                    number += 1
                    self.merchants.append(Merchant(
                        id=f"M-{number}",
                        name=f"{name}, {zone}",
                        name_ar=f"{name_ar}، {zone_ar}",
                        category=category,
                        zone=zone,
                        rating=round(self.random.uniform(3.6, 4.9), 1),
                        prep_minutes=self.random.randrange(8, 32),
                    ))

    def build_drivers(self, count: int) -> None:
        for index in range(count):
            self.drivers.append(Driver(
                id=f"D-{300 + index}",
                name=self._name()[0],
                vehicle=self.random.choices(("motorbike", "car"), (80, 20))[0],
                zone=self.random.choice(catalog.ZONES)[0],
                rating=round(self.random.uniform(4.0, 5.0), 1),
            ))

    def _order_items(self, order: Order) -> int:
        chosen = self.random.sample(catalog.ITEMS[order.category], self.random.randrange(1, 4))
        subtotal = 0
        for name, name_ar, low, high in chosen:
            price = self.random.randrange(low, high + 1) * 100
            quantity = self.random.choice((1, 1, 1, 2))
            subtotal += price * quantity
            order.items.append(OrderItem(
                name=name, name_ar=name_ar, quantity=quantity, unit_price_dh=price,
                extra={"prescription": True} if name in catalog.PRESCRIPTION_ITEMS else {},
            ))
        return subtotal

    def _delivery_fee_dh(self, category: str, zone: str) -> int:
        letter = self.fee_zone.get(zone, "A")
        if category == "parcel":
            return to_dh(self.rules.get("parcels.base_fee_qar")[letter])
        fee = self.rules.get("fees.delivery_fee_qar")[letter][category]
        # Food is not delivered to Zone D, so those orders use the Zone C fee.
        return to_dh(fee if fee is not None else self.rules.get("fees.delivery_fee_qar")["C"]["food"])

    def _service_fee_dh(self, subtotal: int) -> int:
        fee = percent_of(subtotal, self.rules.get("fees.service_fee.pct"))
        return min(max(fee, self.rules.dh("fees.service_fee.min_qar")), self.rules.dh("fees.service_fee.max_qar"))

    def _timeline(self, order: Order, merchant: Merchant, late: bool) -> None:
        placed = order.placed_at
        accepted = placed + timedelta(minutes=2)
        ready = accepted + timedelta(minutes=merchant.prep_minutes)
        picked = ready + timedelta(minutes=self.random.randrange(2, 9))
        travel = self.random.randrange(9, 26)
        order.promised_at = placed + timedelta(minutes=merchant.prep_minutes + 22)
        arrived = picked + timedelta(minutes=travel)
        if late:
            order.delay_reason = self.random.choice(catalog.DELAY_REASONS)
            arrived = max(arrived, order.promised_at) + timedelta(minutes=self.random.randrange(12, 75))
        steps = [("placed", placed), ("accepted", accepted), ("ready", ready), ("picked_up", picked)]
        if order.status == "delivered":
            order.delivered_at = arrived
            steps.append(("delivered", arrived))
        elif order.status == "cancelled":
            steps = steps[:2] + [("cancelled", accepted + timedelta(minutes=4))]
        for kind, moment in steps:
            if moment <= self.anchor:
                order.events.append(OrderEvent(kind=kind, at=moment))

    def build_orders(self, count: int) -> None:
        categories = ("food", "grocery", "pharmacy", "parcel")
        by_category = {c: [m for m in self.merchants if m.category == c] for c in categories}
        for index in range(count):
            customer = self.random.choice(self.customers)
            category = self.random.choices(categories, (62, 24, 8, 6))[0]
            merchant = self.random.choice(by_category[category])
            address = self.random.choice(self.addresses[customer.id])
            live = index >= count - max(count // 40, 8)
            path = self.rules.get("general.order_status_paths")[category]
            status = (
                self.random.choice(path[:-1]) if live
                else self.random.choices(("delivered", "cancelled"), (93, 7))[0]
            )
            placed = (
                self.anchor - timedelta(minutes=self.random.randrange(5, 55)) if live
                else self._when(60)
            )
            order = Order(
                id=f"JB-{500000 + index * 7}",
                customer_id=customer.id,
                merchant_id=merchant.id,
                driver_id=None if status == "placed" else self.random.choice(self.drivers).id,
                category=category,
                status=status,
                payment_method=self.random.choice(PAYMENT_METHODS),
                placed_at=placed,
                address_id=address.id,
                address_text=address.line,
            )
            subtotal = self._order_items(order)
            order.subtotal_dh = subtotal
            order.delivery_fee_dh = self._delivery_fee_dh(category, address.zone)
            order.other_fees_dh = 0 if category == "parcel" else self._service_fee_dh(subtotal)
            order.tip_dh = self.random.choice((0, 0, 0, 200, 500, 1000))
            order.total_dh = subtotal + order.delivery_fee_dh + order.other_fees_dh + order.tip_dh
            self._timeline(order, merchant, late=self.random.random() < 0.18)
            self.orders.append(order)

    def build_tickets(self, count: int) -> None:
        topics = catalog.TICKET_TOPICS
        weights = [topic[1] for topic in topics]
        delivered = [order for order in self.orders if order.status == "delivered"]
        self.language_of = {customer.id: customer.language for customer in self.customers}
        for index in range(count):
            category, _weight, subject, subject_ar = self.random.choices(topics, weights)[0]
            order = self.random.choice(delivered)
            created = order.placed_at + timedelta(hours=self.random.randrange(1, 30))
            if created > self.anchor:
                created = self.anchor - timedelta(minutes=self.random.randrange(1, 300))
            resolved = self.random.random() < 0.9
            language = self.language_of[order.customer_id]
            # The share the bot closes rises slowly across the window, so the desk has a trend.
            progress = 1 - (self.anchor - created).total_seconds() / (60 * 86400)
            by_bot = resolved and self.random.random() < 0.52 + 0.2 * max(progress, 0.0)
            self.tickets.append(Ticket(
                id=f"T-{70000 + index}",
                customer_id=order.customer_id,
                order_id=order.id,
                category=category,
                priority=self.random.choices(("normal", "high"), (85, 15))[0],
                status="resolved" if resolved else "open",
                subject=subject_ar if language == "ar" else subject,
                language=language,
                source="seed",
                csat=self.random.choices((5, 4, 3, 2, 1), (46, 28, 14, 7, 5))[0] if resolved else None,
                resolved_by=("bot" if by_bot else "agent") if resolved else "",
                first_reply_seconds=self.random.randrange(3, 20) if by_bot else self.random.randrange(40, 900),
                created_at=created,
                resolved_at=created + timedelta(minutes=self.random.randrange(4, 400)) if resolved else None,
            ))


def generate_world(
    session: Session,
    seed: int = 2026,
    anchor: datetime = DEFAULT_ANCHOR,
    customers: int = 400,
    drivers: int = 80,
    orders: int = 3000,
    tickets: int = 600,
    rules: Rules | None = None,
) -> dict[str, int]:
    """Fill an empty database and return how many rows of each kind were made."""
    if session.scalar(select(WorldMeta.id).limit(1)) is not None:
        raise ValueError("this database already holds a world")
    builder = WorldBuilder(seed, anchor, rules or Rules.load())
    builder.build_customers(customers)
    builder.build_merchants()
    builder.build_drivers(drivers)
    builder.build_orders(orders)
    builder.build_tickets(tickets)

    session.add_all(builder.customers)
    session.add_all(a for saved in builder.addresses.values() for a in saved)
    session.add_all(builder.merchants)
    session.add_all(builder.drivers)
    session.flush()
    session.add_all(builder.orders)
    session.flush()
    session.add_all(builder.tickets)
    counts = {
        "customers": len(builder.customers),
        "merchants": len(builder.merchants),
        "drivers": len(builder.drivers),
        "orders": len(builder.orders),
        "tickets": len(builder.tickets),
    }
    session.add(WorldMeta(seed=seed, anchor=anchor, notice=catalog.SIMULATION_NOTICE, counts=counts))
    session.commit()
    return counts


def world_digest(session: Session) -> str:
    """A hash of the generated rows, used to prove that a seed reproduces its world."""
    rows: list[list[str]] = []
    for model, key in ((Customer, "id"), (Merchant, "id"), (Driver, "id"), (Order, "id"), (Ticket, "id")):
        for row in session.scalars(select(model).order_by(getattr(model, key))):
            values = {
                column.name: getattr(row, column.name) for column in model.__table__.columns
            }
            rows.append([model.__tablename__, json.dumps(values, default=str, sort_keys=True, ensure_ascii=False)])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()
