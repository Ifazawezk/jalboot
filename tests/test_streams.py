"""Open streams and slow models must not use up the database connection pool.

A stream can stay open for as long as a page does, and the pool has 15 connections,
so anything that holds one for the life of a response takes the API down. These run
the app directly, because a test client waits for a response to finish and an event
stream never does.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from jalboot.api.app import COOKIE, create_app
from jalboot.config import Settings
from jalboot.llm.client import LLMReply, ToolCall
from tests.conftest import database_url
from tests.test_api import PASSWORD, V1, Scripted, start, verify

STREAMS = 20


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_url=database_url(tmp_path), web_dist=tmp_path / "missing", world_scale=0.05))


def scope(path, headers):
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "server": ("testserver", 80), "client": ("127.0.0.1", 50000),
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
    }


async def open_stream(app, path, headers, opened, leave):
    """Runs one GET until the first body chunk, then stays connected until told to leave."""

    async def receive():
        await leave.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and not opened.done():
            opened.set_result(True)

    await app(scope(path, headers), receive, send)


async def hold_open(app, paths_and_headers):
    """Opens every stream, reports how many connections they hold, then closes them."""
    leave = asyncio.Event()
    openings = [asyncio.get_running_loop().create_future() for _ in paths_and_headers]
    tasks = [
        asyncio.create_task(open_stream(app, path, headers, opened, leave))
        for (path, headers), opened in zip(paths_and_headers, openings)
    ]
    await asyncio.wait_for(asyncio.gather(*openings), 20)
    held = app.state.runtime.engine.pool.checkedout()
    leave.set()
    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 20)
    return held


def test_open_customer_streams_hold_no_database_connection(app):
    with TestClient(app, base_url="http://testserver") as client:
        conversations = [start(client) for _ in range(STREAMS)]
    streams = [(f"{V1}/conversations/{cid}/events", auth) for cid, auth in conversations]
    assert asyncio.run(hold_open(app, streams)) == 0


def test_open_desk_streams_hold_no_database_connection(app):
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(f"{V1}/desk/session", json={"email": "sara@jalboot.example", "password": PASSWORD})
        cookie = response.cookies[COOKIE]
    streams = [(f"{V1}/desk/events", {"Cookie": f"{COOKIE}={cookie}"})] * STREAMS
    assert asyncio.run(hold_open(app, streams)) == 0


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
