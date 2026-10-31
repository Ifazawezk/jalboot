"""Sends one very small request, to see if the model is available and whether it can
call a tool. Prints the status and the limits the provider reports. It never prints a
key, and it does not retry past a limit.

    python scripts/llm_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jalboot.env import load_env_file  # noqa: E402
from jalboot.llm.client import LLMError, RateLimited, client_from_env  # noqa: E402

TOOL = {
    "type": "function",
    "function": {
        "name": "track_order",
        "description": "Get the status of an order.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
}


def main() -> int:
    load_env_file()
    client = client_from_env()
    if client is None:
        print("no key found")
        return 1
    client.max_tokens = 200
    print(f"provider {client.provider}, model {client.model}")
    try:
        reply = client.chat(
            [
                {"role": "system", "content": "Use the tool when asked about an order."},
                {"role": "user", "content": "Where is order JB-1234?"},
            ],
            [TOOL],
        )
    except RateLimited as stop:
        print(f"stopped at a limit: {stop}")
        return 2
    except LLMError as failed:
        print(f"failed: {failed}")
        return 3
    limiter = client.limiter
    print(f"tool calls: {[(c.name, c.arguments) for c in reply.tool_calls]}")
    print(f"text: {reply.content[:80]!r}")
    print(f"usage: {reply.usage.get('total_tokens')} tokens")
    print(f"remaining requests {limiter.remaining_requests} of {limiter.limit_requests}")
    print(f"remaining tokens {limiter.remaining_tokens} of {limiter.limit_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
