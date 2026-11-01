import asyncio
import io
import os
import subprocess
import sys
from types import SimpleNamespace

import uvicorn
from uvicorn import Config
from uvicorn.importer import import_from_string
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.server import ServerState

from jalboot import cli
from jalboot.env import ROOT

POSTGRES = "postgresql+psycopg://jalboot:s3cret@db:5432/jalboot"


def seed_output(monkeypatch, url, encoding):
    """Runs the seed command against stdout in a chosen encoding, as a console would."""
    fake = SimpleNamespace(settings=SimpleNamespace(database_url=url))
    monkeypatch.setattr("jalboot.api.runtime.build_runtime", lambda _settings: fake)
    monkeypatch.setattr("jalboot.config.load_settings", lambda: None)
    stream = io.TextIOWrapper(io.BytesIO(), encoding=encoding)
    monkeypatch.setattr(sys, "stdout", stream)
    assert cli.seed(SimpleNamespace()) == 0
    stream.flush()
    return stream.buffer.getvalue().decode(encoding)


def test_seed_never_prints_a_database_password(monkeypatch):
    output = seed_output(monkeypatch, POSTGRES, "utf-8")
    assert "s3cret" not in output
    assert "jalboot:***@db" in output


def test_seed_survives_an_arabic_path_on_a_console_that_cannot_print_it(monkeypatch):
    output = seed_output(monkeypatch, "sqlite:///C:/Users/n/الصور/app.sqlite3", "cp1252")
    assert "app.sqlite3" in output


def test_ctrl_c_does_not_wait_for_open_streams(monkeypatch):
    started = {}
    monkeypatch.setattr(uvicorn, "run", lambda _app, **options: started.update(options))
    monkeypatch.setattr("jalboot.api.app.create_app", lambda: object())
    cli.serve(SimpleNamespace(host="127.0.0.1", port=9))
    assert started["timeout_graceful_shutdown"] == 2


def event_loop_for(monkeypatch, platform):
    started = {}
    monkeypatch.setattr(uvicorn, "run", lambda _app, **options: started.update(options))
    monkeypatch.setattr("jalboot.api.app.create_app", lambda: object())
    monkeypatch.setattr(sys, "platform", platform)
    cli.serve(SimpleNamespace(host="127.0.0.1", port=9))
    return started["loop"]


def test_windows_serves_on_the_selector_loop(monkeypatch):
    """The default Windows loop stops accepting for good after about 100 connection resets."""
    assert event_loop_for(monkeypatch, "win32") == "jalboot.cli:selector_loop"


def test_other_platforms_keep_the_default_loop(monkeypatch):
    assert event_loop_for(monkeypatch, "linux") == "auto"


def protocol_for(monkeypatch, platform):
    started = {}
    monkeypatch.setattr(uvicorn, "run", lambda _app, **options: started.update(options))
    monkeypatch.setattr("jalboot.api.app.create_app", lambda: object())
    monkeypatch.setattr(sys, "platform", platform)
    cli.serve(SimpleNamespace(host="127.0.0.1", port=9))
    return started["http"]


def test_windows_serves_with_the_connection_cap(monkeypatch):
    assert issubclass(protocol_for(monkeypatch, "win32"), H11Protocol)


def test_other_platforms_keep_the_default_protocol(monkeypatch):
    assert protocol_for(monkeypatch, "linux") == "auto"


class FakeTransport:
    def __init__(self):
        self.aborted = False

    def get_extra_info(self, _name, default=None):
        return default

    def abort(self):
        self.aborted = True

    def close(self):
        pass

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass


async def no_app(_scope, _receive, _send):
    return None


def connect_with(open_connections):
    """Makes one connection while this many others are already open."""
    loop = asyncio.new_event_loop()
    try:
        state = ServerState()
        state.connections.update(object() for _ in range(open_connections))
        config = Config(no_app, loop="none")
        config.load()
        protocol = cli.capped_protocol()(config, state, {}, _loop=loop)
        transport = FakeTransport()
        protocol.connection_made(transport)
        return protocol, transport, state
    finally:
        loop.close()


def test_a_connection_below_the_cap_is_kept():
    _protocol, transport, _state = connect_with(cli.MAX_CONNECTIONS - 1)
    assert not transport.aborted


def test_a_connection_past_the_cap_is_dropped_and_cleans_up():
    """select() on Windows fails past about 510 sockets, and that failure ends the event
    loop for good. Dropping one connection is the difference between busy and dead."""
    protocol, transport, state = connect_with(cli.MAX_CONNECTIONS)
    assert transport.aborted
    protocol.connection_lost(None)
    assert len(state.connections) == cli.MAX_CONNECTIONS


def test_the_cap_stays_below_the_windows_select_limit():
    assert cli.MAX_CONNECTIONS < 500


def test_uvicorn_can_build_the_loop_it_is_given():
    loop = import_from_string("jalboot.cli:selector_loop")()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_the_package_runs_with_python_dash_m():
    done = subprocess.run(
        [sys.executable, "-m", "jalboot", "--help"], capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert "serve" in done.stdout
