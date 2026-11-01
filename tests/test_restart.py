"""A server that dies mid turn leaves its message marked running. The list of running
turns is memory only, so after a restart nothing can still be running, and that row
must not block the customer. The retry runs the tools again, and the action records
stop it paying twice."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from jalboot.api.app import create_app
from jalboot.config import Settings
from jalboot.db.models import Customer, Message, Refund
from tests.conftest import database_url
from tests.test_api import V1, find, say, start, verify

CLAIM = "The Karak tea is missing from JB-700102"
CLIENT_ID = "crash-1"


def settings(tmp_path):
    return Settings(database_url=database_url(tmp_path), web_dist=tmp_path / "missing", world_scale=0.05)


def crash(app, cid):
    """Leaves the database as a killed server does. The tools have committed, and the
    reply and the end of the turn were never written."""
    with app.state.runtime.sessions() as session:
        session.execute(delete(Message).where(Message.conversation_id == cid, Message.role == "bot"))
        session.execute(update(Message).where(Message.client_id == CLIENT_ID).values(turn_state="running"))
        session.commit()
    app.state.runtime.engine.dispose()


def paid(app, order_id="JB-700102"):
    with app.state.runtime.sessions() as session:
        count = session.scalar(select(func.count()).select_from(Refund).where(Refund.order_id == order_id))
        wallets = sum(session.scalars(select(Customer.wallet_dh)))
    return count, wallets


@pytest.fixture
def after_a_crash(tmp_path):
    """A claim that paid, a crash, then a restart on the same database."""
    first = create_app(settings(tmp_path))
    with TestClient(first, base_url="http://testserver") as client:
        cid, auth = start(client)
        verify(client, cid, auth)
        response = say(client, cid, auth, CLAIM, CLIENT_ID)
        assert find(response, "message.end") == {"finish": "complete"}
    before = paid(first)
    assert before[0] == 1
    crash(first, cid)
    return create_app(settings(tmp_path)), cid, auth, before


def test_a_turn_cut_off_by_a_crash_can_be_sent_again(after_a_crash):
    app, cid, auth, _ = after_a_crash
    with TestClient(app, base_url="http://testserver") as client:
        response = say(client, cid, auth, CLAIM, CLIENT_ID)
        assert response.status_code == 200
        assert find(response, "message.end") == {"finish": "complete"}


def test_sending_it_again_after_a_crash_does_not_pay_twice(after_a_crash):
    app, cid, auth, before = after_a_crash
    with TestClient(app, base_url="http://testserver") as client:
        say(client, cid, auth, CLAIM, CLIENT_ID)
    assert paid(app) == before


def test_a_finished_retry_is_finished(after_a_crash):
    app, cid, auth, _ = after_a_crash
    with TestClient(app, base_url="http://testserver") as client:
        say(client, cid, auth, CLAIM, CLIENT_ID)
        again = say(client, cid, auth, CLAIM, CLIENT_ID)
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "duplicate_message"


def test_a_restart_leaves_finished_messages_alone(tmp_path):
    first = create_app(settings(tmp_path))
    with TestClient(first, base_url="http://testserver") as client:
        cid, auth = start(client)
        say(client, cid, auth, "how long does delivery take", CLIENT_ID)
    first.state.runtime.engine.dispose()
    second = create_app(settings(tmp_path))
    with second.state.runtime.sessions() as session:
        states = session.scalars(select(Message.turn_state).where(Message.client_id == CLIENT_ID)).all()
    assert states == ["complete"]


def test_a_turn_running_right_now_is_not_refused_as_finished(tmp_path):
    """The sweep is at startup only, so a live turn keeps its normal answer."""
    app = create_app(settings(tmp_path))
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
        with app.state.runtime.sessions() as session:
            session.add(Message(
                conversation_id=cid, role="customer", text="hello", client_id=CLIENT_ID, turn_state="running",
            ))
            session.commit()
        response = client.post(
            f"{V1}/conversations/{cid}/messages", headers=auth,
            json={"clientMessageId": CLIENT_ID, "text": "hello", "locale": "en"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "turn_in_progress"
