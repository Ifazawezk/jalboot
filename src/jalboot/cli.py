"""Command line entry points."""

from __future__ import annotations

import argparse
import asyncio
import sys

from jalboot.env import load_env_file

SHUTDOWN_SECONDS = 2
# Below the point where select() fails on Windows, which is about 510 sockets.
MAX_CONNECTIONS = 480


def selector_loop() -> asyncio.AbstractEventLoop:
    """The default Windows loop stops accepting for good after a burst of connection
    resets (WinError 64), with the process still alive and looking healthy. A selector
    loop cannot run subprocesses on Windows, and nothing in serve starts one."""
    return asyncio.SelectorEventLoop()


def capped_protocol() -> type[asyncio.Protocol]:
    """The selector loop has a limit of its own: past about 510 sockets select() raises,
    which ends the event loop for good. This drops a connection before asyncio registers
    it, so too many clients get refused until others leave, and the server survives."""
    from uvicorn.protocols.http.h11_impl import H11Protocol

    class CappedProtocol(H11Protocol):
        def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
            super().connection_made(transport)
            if len(self.connections) > MAX_CONNECTIONS:
                transport.abort()

    return CappedProtocol


def serve(args: argparse.Namespace) -> int:
    import uvicorn

    from jalboot.api.app import create_app

    windows = sys.platform == "win32"
    # An event stream never ends by itself, so Ctrl+C must not wait for one.
    uvicorn.run(
        create_app(), host=args.host, port=args.port, log_level="info", timeout_graceful_shutdown=SHUTDOWN_SECONDS,
        loop="jalboot.cli:selector_loop" if windows else "auto",
        http=capped_protocol() if windows else "auto",
    )
    return 0


def printable_url(url: str) -> str:
    """Hides any password, and escapes what this console cannot show, such as an
    Arabic folder name on a Windows code page."""
    from sqlalchemy.engine import make_url

    safe = make_url(url).render_as_string(hide_password=True)
    encoding = sys.stdout.encoding or "utf-8"
    return safe.encode(encoding, "backslashreplace").decode(encoding)


def seed(_args: argparse.Namespace) -> int:
    from jalboot.api.runtime import build_runtime
    from jalboot.config import load_settings

    runtime = build_runtime(load_settings())
    print(f"world ready at {printable_url(runtime.settings.database_url)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = argparse.ArgumentParser(prog="jalboot", description="AI support for a fictional delivery app.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("serve", help="start the web server")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8000)
    run.set_defaults(func=serve)
    commands.add_parser("seed", help="generate the simulated world").set_defaults(func=seed)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
