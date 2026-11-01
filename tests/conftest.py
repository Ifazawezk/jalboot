from datetime import timedelta

import pytest

from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import Conversation
from jalboot.policy.rules import Rules
from jalboot.tools.executor import ToolContext, ToolExecutor
from jalboot.world.demo import add_demo_customers
from jalboot.world.generator import DEFAULT_ANCHOR, generate_world

ANCHOR = DEFAULT_ANCHOR
RULES = Rules.load()


@pytest.fixture
def db():
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    session = make_session_factory(engine)()
    generate_world(session, seed=5, customers=10, drivers=10, orders=40, tickets=5)
    add_demo_customers(session, ANCHOR)
    yield session
    session.close()


def make_conversation(session, customer_id="C-1001", verified=True, language="en", name="conv-1"):
    conversation = Conversation(
        id=name, language=language, created_at=ANCHOR, updated_at=ANCHOR,
        customer_id=customer_id if verified else None, verified_at=ANCHOR if verified else None,
    )
    session.add(conversation)
    session.commit()
    return conversation


def tools_for(session, conversation, turn="t1", now=None, **kwargs):
    context = ToolContext(
        session=session, conversation=conversation, rules=RULES, now=now or ANCHOR, turn_id=turn, **kwargs,
    )
    return ToolExecutor(context)


@pytest.fixture
def layla(db):
    return tools_for(db, make_conversation(db))


@pytest.fixture
def later():
    return ANCHOR + timedelta(minutes=5)
