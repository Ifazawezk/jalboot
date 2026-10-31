"""Open streams and slow models must not use up the database connection pool, and a
stream must not outlive the access that opened it.

A stream can stay open for as long as a page does, and the pool has 15 connections,
so anything that holds one for the life of a response takes the API down. These run
the app directly, because a test client waits for a response to finish and an event
stream never does.
"""

import asyncio
import json
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from jalboot.api import chat, events
from jalboot.api.app import COOKIE, create_app
from jalboot.api.events import MAX_STREAMS_PER_CLIENT, MAX_STREAMS_PER_CONVERSATION
from jalboot.config import Settings
from jalboot.db.base import utcnow
from jalboot.db.models import StaffUser, WebSession
from jalboot.llm.client import LLMReply, ToolCall
from tests.conftest import database_url
from tests.test_api import PASSWORD, V1, Scripted, signed_in, start, verify


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_url=database_url(tmp_path), web_dist=tmp_path / "missing", world_scale=0.05))


def scope(path, headers, client):
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "server": ("testserver", 80), "client": (client, 50000),
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
    }


class Stream:
    """One open GET. It stays connected until told to leave, like a page does."""

    def __init__(self, app, path, headers, client="127.0.0.1"):
        self.status = None
        self.body = b""
        self.opened = asyncio.Event()
        self.leave = asyncio.Event()
        self.task = asyncio.create_task(app(scope(path, headers, client), self.receive, self.send))

    async def receive(self):
        await self.leave.wait()
        return {"type": "http.disconnect"}

    async def send(self, message):
        if message["type"] == "http.response.start":
            self.status = message["status"]
        elif message["type"] == "http.response.body":
            self.body += message.get("body", b"")
            self.opened.set()

    async def ready(self):
        await asyncio.wait_for(self.opened.wait(), 20)
        return self

    async def close(self):
        self.leave.set()
        await asyncio.wait_for(self.task, 20)


def conversations(app, count):
    with TestClient(app, base_url="http://testserver") as client:
        return [start(client) for _ in range(count)]


def cookie_for(app, email="sara@jalboot.example"):
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(f"{V1}/desk/session", json={"email": email, "password": PASSWORD})
        return {"Cookie": f"{COOKIE}={response.cookies[COOKIE]}"}


def test_open_customer_streams_hold_no_database_connection(app):
    opened = conversations(app, MAX_STREAMS_PER_CLIENT)

    async def run():
        streams = [Stream(app, f"{V1}/conversations/{cid}/events", auth) for cid, auth in opened]
        await asyncio.gather(*(stream.ready() for stream in streams))
        held = app.state.runtime.engine.pool.checkedout()
        await asyncio.gather(*(stream.close() for stream in streams))
        return held, {stream.status for stream in streams}

    assert asyncio.run(run()) == (0, {200})


def test_open_desk_streams_hold_no_database_connection(app):
    headers = cookie_for(app)

    async def run():
        streams = [Stream(app, f"{V1}/desk/events", headers) for _ in range(MAX_STREAMS_PER_CLIENT)]
        await asyncio.gather(*(stream.ready() for stream in streams))
        held = app.state.runtime.engine.pool.checkedout()
        await asyncio.gather(*(stream.close() for stream in streams))
        return held, {stream.status for stream in streams}

    assert asyncio.run(run()) == (0, {200})


def test_a_stream_still_checks_who_is_asking(app):
    with TestClient(app, base_url="http://testserver") as client:
        cid, _ = start(client)
        assert client.get(f"{V1}/conversations/{cid}/events").status_code == 401
        assert client.get(f"{V1}/conversations/{cid}/events", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert client.get(f"{V1}/desk/events").status_code == 401


def test_a_stream_that_is_refused_gives_its_connection_back(app):
    with TestClient(app, base_url="http://testserver") as client:
        cid, _ = start(client)
        client.get(f"{V1}/conversations/{cid}/events")
        client.get(f"{V1}/desk/events")
        assert app.state.runtime.engine.pool.checkedout() == 0


def test_one_conversation_cannot_open_streams_without_limit(app):
    (cid, auth), = conversations(app, 1)
    path = f"{V1}/conversations/{cid}/events"

    async def run():
        kept = [await Stream(app, path, auth).ready() for _ in range(MAX_STREAMS_PER_CONVERSATION)]
        refused = await Stream(app, path, auth).ready()
        await refused.close()
        await kept[0].close()
        room_again = await Stream(app, path, auth).ready()
        await asyncio.gather(room_again.close(), *(stream.close() for stream in kept[1:]))
        return [stream.status for stream in kept], refused.status, refused.body, room_again.status

    statuses, refused, body, again = asyncio.run(run())
    assert statuses == [200] * MAX_STREAMS_PER_CONVERSATION
    assert refused == 429
    assert json.loads(body)["error"]["code"] == "too_many_streams"
    assert again == 200


def test_one_client_cannot_open_streams_without_limit(app):
    opened = conversations(app, MAX_STREAMS_PER_CLIENT + 2)
    paths = [(f"{V1}/conversations/{cid}/events", auth) for cid, auth in opened]

    async def run():
        kept = [await Stream(app, path, auth).ready() for path, auth in paths[:MAX_STREAMS_PER_CLIENT]]
        over = await Stream(app, *paths[MAX_STREAMS_PER_CLIENT]).ready()
        elsewhere = await Stream(app, *paths[MAX_STREAMS_PER_CLIENT + 1], client="198.51.100.7").ready()
        await asyncio.gather(*(stream.close() for stream in [*kept, over, elsewhere]))
        return over.status, elsewhere.status

    assert asyncio.run(run()) == (429, 200)
    assert app.state.runtime.broker.client_count("127.0.0.1") == 0


def log_out(session):
    session.execute(delete(WebSession))


def deactivate(session):
    session.scalar(select(StaffUser).where(StaffUser.email == "sara@jalboot.example")).active = False


def expire(session):
    for row in session.scalars(select(WebSession)):
        row.expires_at = utcnow() - timedelta(minutes=1)


@pytest.mark.parametrize("end_access", [log_out, deactivate, expire])
def test_a_desk_stream_ends_when_its_access_does_even_while_busy(app, monkeypatch, end_access):
    """A stream that always has events to send is never idle, so a check that only ran
    on idle keepalives would let it run forever. That is why events keep arriving here."""
    monkeypatch.setattr(events, "KEEPALIVE_SECONDS", 0.05)
    headers = cookie_for(app)
    runtime = app.state.runtime
    topic = chat.desk_topic("agent", "en")

    def change_access():
        with runtime.sessions() as session:
            end_access(session)
            session.commit()

    async def run():
        stream = await Stream(app, f"{V1}/desk/events", headers).ready()
        runtime.broker.publish(topic, {"type": "summary.updated", "marker": "before"})
        await asyncio.sleep(0.02)
        assert b"before" in stream.body
        await asyncio.to_thread(change_access)
        deadline = time.monotonic() + 5
        while not stream.task.done() and time.monotonic() < deadline:
            runtime.broker.publish(topic, {"type": "summary.updated", "marker": "after"})
            await asyncio.sleep(0.02)
        ended = stream.task.done()
        await stream.close()
        return ended

    assert asyncio.run(run())
    assert runtime.broker.count(topic) == 0


def test_a_customer_stream_ends_after_the_conversation_is_closed(app, monkeypatch):
    monkeypatch.setattr(events, "KEEPALIVE_SECONDS", 0.05)
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
        csrf = signed_in(client)

        async def run():
            stream = await Stream(app, f"{V1}/conversations/{cid}/events", auth).ready()
            await asyncio.to_thread(client.post, f"{V1}/desk/conversations/{cid}/close", headers=csrf)
            await asyncio.wait_for(asyncio.shield(stream.task), 5)
            return stream.body

        assert b"conversation.closed" in asyncio.run(run())


def test_a_closed_conversation_cannot_open_a_new_stream(app):
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
        csrf = signed_in(client)
        client.post(f"{V1}/desk/conversations/{cid}/close", headers=csrf)

    async def run():
        stream = await Stream(app, f"{V1}/conversations/{cid}/events", auth).ready()
        status = stream.status
        await stream.close()
        return status

    assert asyncio.run(run()) == 409


class Watched(Scripted):
    """Records how many connections are out at the moment the model is called."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.engine = None
        self.held = []

    def chat(self, messages, tools=None):
        self.held.append(self.engine.pool.checkedout())
        return super().chat(messages, tools)


def test_no_connection_is_held_while_the_model_thinks(tmp_path):
    """Covers the call after a tool ran, because reading the order for its card opens a
    new transaction, and a slow model must not sit on that one either."""
    model = Watched(
        LLMReply("", [ToolCall("t1", "track_order", {"order_id": "JB-700101"})]),
        LLMReply("", [ToolCall("t2", "get_order_details", {"order_id": "JB-700101"})]),
        LLMReply("Your order is on its way."),
    )
    settings = Settings(database_url=database_url(tmp_path), web_dist=tmp_path / "missing", world_scale=0.05)
    app = create_app(settings, model)
    model.engine = app.state.runtime.engine
    with TestClient(app, base_url="http://testserver") as client:
        cid, auth = start(client)
        verify(client, cid, auth)
        response = client.post(
            f"{V1}/conversations/{cid}/messages", headers=auth,
            json={"clientMessageId": "c1", "text": "please check the status of my order", "locale": "en"},
        )
        assert response.status_code == 200
        assert "order.card" in response.text
    assert model.held == [0, 0, 0]
