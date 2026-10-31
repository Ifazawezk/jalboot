import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import (
    Approval, Customer, Merchant, Order, Refund, Ticket, WorldMeta,
)
from jalboot.world.generator import generate_world, world_digest

SMALL = dict(customers=40, drivers=10, orders=200, tickets=30)


def fresh(seed=7):
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    session = make_session_factory(engine)()
    generate_world(session, seed=seed, **SMALL)
    return session


def test_the_same_seed_gives_the_same_world():
    assert world_digest(fresh(7)) == world_digest(fresh(7))


def test_a_different_seed_gives_a_different_world():
    assert world_digest(fresh(7)) != world_digest(fresh(8))


def test_world_is_labelled_as_simulated():
    meta = fresh().scalar(select(WorldMeta))
    assert "simulated" in meta.notice.lower()


def test_contact_details_cannot_reach_a_real_person():
    session = fresh()
    for customer in session.scalars(select(Customer)):
        # Qatari numbers never start with 0 after the country code.
        assert re.fullmatch(r"\+974 0\d{3} \d{4}", customer.phone)
        assert customer.email.endswith("@sim.jalboot.example")


def test_every_order_has_consistent_money_and_a_timeline():
    session = fresh()
    for order in session.scalars(select(Order)):
        assert order.items
        assert order.total_dh == (
            order.subtotal_dh - order.discount_dh + order.delivery_fee_dh + order.other_fees_dh + order.tip_dh
        )
        assert sum(i.quantity * i.unit_price_dh for i in order.items) == order.subtotal_dh
        assert order.events[0].kind == "placed"
        if order.status == "delivered":
            assert order.delivered_at is not None
            assert order.events[-1].kind == "delivered"


def test_all_four_verticals_exist():
    session = fresh()
    kinds = set(session.scalars(select(Merchant.category).distinct()))
    assert kinds == {"food", "grocery", "pharmacy", "parcel"}


def test_some_orders_are_live_and_some_are_late():
    session = fresh()
    live = session.scalar(
        select(func.count()).select_from(Order).where(Order.status.notin_(("delivered", "cancelled")))
    )
    late = session.scalar(select(func.count()).select_from(Order).where(Order.delay_reason != ""))
    assert live > 0 and late > 0


def test_a_database_cannot_be_filled_twice():
    with pytest.raises(ValueError):
        generate_world(fresh(), **SMALL)


def test_tickets_point_at_orders():
    session = fresh()
    for ticket in session.scalars(select(Ticket)):
        assert ticket.order_id is not None


def test_the_database_refuses_a_duplicate_refund_key():
    session = fresh()
    order = session.scalar(select(Order).where(Order.status == "delivered"))
    row = dict(order_id=order.id, customer_id=order.customer_id, amount_dh=100, method="card",
               reason="late", idempotency_key="same")
    session.add(Refund(id="R-1", **row))
    session.commit()
    session.add(Refund(id="R-2", **row))
    with pytest.raises(IntegrityError):
        session.commit()


def test_the_database_refuses_a_zero_refund():
    session = fresh()
    order = session.scalar(select(Order).where(Order.status == "delivered"))
    session.add(Refund(id="R-3", order_id=order.id, customer_id=order.customer_id, amount_dh=0,
                       method="card", reason="late", idempotency_key="zero"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_the_database_refuses_a_duplicate_approval_key():
    session = fresh()
    order = session.scalar(select(Order))
    row = dict(kind="refund", customer_id=order.customer_id, order_id=order.id, idempotency_key="k")
    session.add(Approval(id="AP-1", **row))
    session.commit()
    session.add(Approval(id="AP-2", **row))
    with pytest.raises(IntegrityError):
        session.commit()
