"""Command line entry points."""

from __future__ import annotations

import argparse
import sys

from jalboot.env import load_env_file


def serve(args: argparse.Namespace) -> int:
    import uvicorn

    from jalboot.api.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


def seed(_args: argparse.Namespace) -> int:
    from jalboot.api.runtime import build_runtime
    from jalboot.config import load_settings

    runtime = build_runtime(load_settings())
    print(f"world ready at {runtime.settings.database_url}")
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
