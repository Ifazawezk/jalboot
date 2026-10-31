"""A resumable local cache and request budget for evaluation runs.

Free tiers allow few tokens a day, so evaluation runs in small steps. Every reply
is appended to a local file as soon as it arrives, so a run that stops for any
reason loses nothing, and the next run only pays for what is missing.

This is for evaluation only. The server never uses it, so messages from a live
chat are not written here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from jalboot.llm.client import LLMClient, LLMError, LLMReply, RateLimited, ToolCall


class BudgetExhausted(RuntimeError):
    """This run must stop: it spent its budget or reached the provider's limit.

    Deliberately not an LLMError. Those are caught and degrade to a safe reply,
    which is right for a live chat, but in an evaluation it would score the
    fallback as if the model had produced it.
    """


@dataclass
class Budget:
    """Limits for one run, plus a limit per model per day, which keeps a free tier's
    daily allowance safe because providers do not report what is left of it.
    Replies from the cache cost nothing."""

    requests: int | None = None
    tokens: int | None = None
    daily_tokens: int | None = None
    requests_used: int = 0
    tokens_used: int = 0
    cache_hits: int = 0

    def check(self) -> None:
        if self.requests is not None and self.requests_used >= self.requests:
            raise BudgetExhausted(f"request budget of {self.requests} is spent")
        if self.tokens is not None and self.tokens_used >= self.tokens:
            raise BudgetExhausted(f"token budget of {self.tokens} is spent")


def utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def request_key(provider: str, model: str, messages: Sequence[dict], tools: Sequence[dict] | None) -> str:
    text = json.dumps(
        [provider, model, list(messages), list(tools or [])], ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ResponseCache:
    """Append-only JSONL file. A line cut short by a crash is skipped on load."""

    def __init__(self, path: Path):
        self.path = path
        self.entries: dict[str, dict] = {}
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                        self.entries[row["key"]] = row
                    except (ValueError, KeyError, TypeError):
                        continue

    def get(self, key: str) -> dict | None:
        return self.entries.get(key)

    def spent_today(self, model: str) -> int:
        today = utc_day()
        return sum(
            row.get("tokens", 0) for row in self.entries.values()
            if row.get("model") == model and row.get("day") == today
        )

    def put(self, key: str, model: str, reply: LLMReply, tokens: int) -> None:
        row = {
            "key": key,
            "model": model,
            "content": reply.content,
            "tool_calls": [asdict(call) for call in reply.tool_calls],
            "finish_reason": reply.finish_reason,
            "tokens": tokens,
            "day": utc_day(),
        }
        self.entries[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()


class CachedClient:
    """A client that answers from the cache and spends from a shared budget."""

    def __init__(self, client: LLMClient, cache: ResponseCache, budget: Budget):
        self.client = client
        self.cache = cache
        self.budget = budget
        self.provider = client.provider
        self.model = client.model

    def chat(self, messages: Sequence[dict], tools: Sequence[dict] | None = None) -> LLMReply:
        key = request_key(self.provider, self.model, messages, tools)
        hit = self.cache.get(key)
        if hit is not None:
            self.budget.cache_hits += 1
            calls = [ToolCall(**call) for call in hit.get("tool_calls", [])]
            return LLMReply(hit.get("content", ""), calls, hit.get("finish_reason", "stop"))
        self.budget.check()
        daily = self.budget.daily_tokens
        if daily is not None and self.cache.spent_today(self.model) >= daily:
            raise BudgetExhausted(f"daily token cap of {daily} for {self.model} is spent")
        self.budget.requests_used += 1
        try:
            reply = self.client.chat(messages, tools)
        except RateLimited as exc:
            raise BudgetExhausted(f"stopped at the provider's limit: {exc}") from exc
        except LLMError:
            raise
        tokens = int(reply.usage.get("total_tokens") or 0)
        self.budget.tokens_used += tokens
        self.cache.put(key, self.model, reply, tokens)
        return reply
