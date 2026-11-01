"""Races, on a real file database with real threads.

A single-threaded test cannot show these. Two requests that both read "not refunded
yet" and then both pay is the bug a duplicate click or a retry would produce.

The same tests run on PostgreSQL when TEST_DATABASE_URL names one.
"""

import threading
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from jalboot import audit
from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import Approval, Conversation, Customer, Order, Refund, StaffUser
from jalboot.policy.rules import Rules
from jalboot.tools.approvals import DecisionError, decide
from jalboot.tools.executor import ToolContext, ToolExecutor
from jalboot.world.demo import add_demo_customers
from jalboot.tools.settle import settle_credit
from jalboot.world.generator import DEFAULT_ANCHOR, generate_world
from tests.conftest import database_url

RULES = Rules.load()
THREADS = 8
REFUND = {"order_id": "JB-700102", "amount_qar": 4.0, "reason": "missing_item", "items": [{"name": "Karak tea"}]}
LARGE = {"order_id": "JB-700103", "amount_qar": 90.0, "reason": "wrong_item", "items": [{"name": "Grilled hammour"}]}


@pytest.fixture
def sessions(tmp_path):
    engine = make_engine(database_url(tmp_path))
    create_schema(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        generate_world(session, seed=5, customers=10, drivers=10, orders=40, tickets=5)
        add_demo_customers(session, DEFAULT_ANCHOR)
        session.add(Conversation(
            id="race", language="en", customer_id="C-1001", verified_at=DEFAULT_ANCHOR,
            created_at=DEFAULT_ANCHOR, updated_at=DEFAULT_ANCHOR,
        ))
        session.commit()
    yield factory
    engine.dispose()


def in_parallel(work, count=THREADS):
    barrier = threading.Barrier(count)
    results, errors = [], []

    def run(index):
        try:
            barrier.wait(timeout=20)
            results.append(work(index))
        except Exception as error:  # noqa: BLE001
            errors.append(repr(error))

    threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    return results, errors


def call(factory, tool, arguments, turn):
    with factory() as session:
        conversation = session.get(Conversation, "race")
        context = ToolContext(
            session=session, conversation=conversation, rules=RULES,
            now=DEFAULT_ANCHOR + timedelta(minutes=1), turn_id=turn,
        )
        return ToolExecutor(context).execute(tool, arguments)


def test_the_same_refund_in_parallel_pays_once(sessions):
    results, errors = in_parallel(lambda n: call(sessions, "issue_refund", REFUND, f"t{n}"))
    assert errors == []
    assert sum(1 for r in results if r.get("status") == "done" and not r.get("replayed")) == 1
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Refund)) == 1


def test_a_refund_in_parallel_moves_the_wallet_once(sessions):
    with sessions() as session:
        session.get(Order, "JB-700102").payment_method = "cash"
        before = session.get(Customer, "C-1001").wallet_dh
        session.commit()
    in_parallel(lambda n: call(sessions, "issue_refund", REFUND, f"t{n}"))
    with sessions() as session:
        assert session.get(Customer, "C-1001").wallet_dh == before + 400
        assert session.scalar(select(func.count()).select_from(Refund)) == 1


def test_a_request_above_the_limit_in_parallel_files_one_approval(sessions):
    in_parallel(lambda n: call(sessions, "issue_refund", LARGE, f"t{n}"))
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Approval)) == 1


def test_two_people_approving_at_once_pay_once(sessions):
    call(sessions, "issue_refund", LARGE, "t0")
    with sessions() as session:
        approval_id = session.scalar(select(Approval.id))
        for index in range(THREADS):
            session.add(StaffUser(
                id=f"S-{index}", email=f"s{index}@sim.jalboot.example", name="Sim", role="agent",
                password_hash="x",
            ))
        session.commit()

    def approve(index):
        with sessions() as session:
            staff = session.get(StaffUser, f"S-{index}")
            try:
                decide(session, approval_id, staff, "approve", "", 1, DEFAULT_ANCHOR, RULES)
                return "paid"
            except DecisionError as failed:
                return failed.code

    results, errors = in_parallel(approve)
    assert errors == []
    assert results.count("paid") == 1
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Refund)) == 1


def test_the_audit_chain_survives_parallel_writers(sessions):
    def work(index):
        return call(sessions, "track_order", {"order_id": "JB-700101"}, f"t{index}")

    results, errors = in_parallel(work)
    assert errors == []
    assert len(results) == THREADS
    with sessions() as session:
        assert audit.verify_chain(session) == (True, None)




def test_two_credits_at_once_both_reach_the_wallet(sessions):
    """Security review 16: each session read the same balance, so one credit was lost."""
    first, second = sessions(), sessions()
    orders = [session.get(Order, "JB-700102") for session in (first, second)]
    before = orders[0].customer.wallet_dh
    assert orders[1].customer.wallet_dh == before
    settle_credit(second, orders[1], 2000, reason="goodwill", key="b", approved_by="t", now=DEFAULT_ANCHOR)
    second.commit()
    settle_credit(first, orders[0], 2000, reason="goodwill", key="a", approved_by="t", now=DEFAULT_ANCHOR)
    first.commit()
    assert orders[0].customer.wallet_dh == before + 4000
    first.close()
    second.close()
    with sessions() as session:
        assert session.get(Customer, "C-1001").wallet_dh == before + 4000


def test_reads_outside_the_write_lock_do_not_collide_with_writers(sessions):
    quote = {"order_id": "JB-700102", "reason": "not_received"}

    def work(index):
        if index % 2:
            return call(sessions, "quote_refund", quote, f"t{index}")
        return call(sessions, "track_order", {"order_id": "JB-700101"}, f"t{index}")

    results, errors = in_parallel(work)
    assert errors == []
    assert len(results) == THREADS
    with sessions() as session:
        assert audit.verify_chain(session) == (True, None)
