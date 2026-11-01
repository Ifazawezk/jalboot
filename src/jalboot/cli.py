"""Command line entry points."""

from __future__ import annotations

import argparse
import sys

from jalboot.env import load_env_file

SHUTDOWN_SECONDS = 2


def serve(args: argparse.Namespace) -> int:
    import uvicorn

    from jalboot.api.app import create_app

    # An event stream never ends by itself, so Ctrl+C must not wait for one.
    uvicorn.run(
        create_app(), host=args.host, port=args.port, log_level="info", timeout_graceful_shutdown=SHUTDOWN_SECONDS,
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
