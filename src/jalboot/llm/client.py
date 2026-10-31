"""A client for any server that speaks the OpenAI chat completions API.

It uses plain HTTP with httpx, so the project depends on no vendor SDK and tests
can swap in a mock transport. Groq is the default provider.

Environment variables:
    LLM_PROVIDER      groq (default) or compatible
    LLM_API_KEY       the key
    LLM_API_KEY_ENV   the name of another variable that holds the key
    LLM_BASE_URL      overrides the provider's URL; required for compatible
    LLM_MODEL         default openai/gpt-oss-20b on Groq
    LLM_TIMEOUT       seconds, default 60
    LLM_MAX_TOKENS    default 1000
    LLM_MAX_WAIT      longest wait for a rate limit, seconds, default 30

Errors never carry a key or the provider's error text, only the status and a
short code, because providers can echo part of the key or the prompt.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

import httpx

from jalboot.llm.ratelimit import LLMError, RateLimited, RateLimiter

__all__ = [
    "LLMClient", "LLMError", "LLMReply", "OpenAICompatibleClient", "RateLimited",
    "ToolCall", "client_from_env", "strip_reasoning",
]

THINK_BLOCK = re.compile(r"<think>.*?(</think>|\Z)", re.DOTALL | re.IGNORECASE)
ERROR_CODE = re.compile(r"^[\w.-]{1,64}$")
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-20b"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # True when the model's arguments were not valid JSON. The call is refused
    # and the model is told, instead of guessing what it meant.
    malformed: bool = False


@dataclass
class LLMReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient(Protocol):
    provider: str
    model: str

    def chat(self, messages: Sequence[dict], tools: Sequence[dict] | None = None) -> LLMReply: ...


def strip_reasoning(text: str) -> str:
    """Remove <think> blocks, which may hold draft claims. An unclosed block means
    the reply was cut off while thinking, so all of it goes."""
    return THINK_BLOCK.sub("", text).strip()


def error_code(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
        code = (error.get("code") or error.get("type")) if isinstance(error, dict) else None
    except (ValueError, AttributeError):
        return ""
    return f" ({code})" if isinstance(code, str) and ERROR_CODE.match(code) else ""


def request_options(provider: str, model: str) -> dict[str, Any]:
    """Keep model reasoning out of the reply. On Groq, GPT OSS models return it in
    a separate field when it is asked for."""
    if provider == "groq" and model.startswith("openai/gpt-oss"):
        return {"include_reasoning": False, "reasoning_effort": "low"}
    return {}


def parse_tool_calls(message: Mapping[str, Any]) -> list[ToolCall]:
    calls = []
    for index, raw in enumerate(message.get("tool_calls") or []):
        function = raw.get("function") or {}
        text = function.get("arguments") or "{}"
        malformed = False
        try:
            arguments = json.loads(text) if isinstance(text, str) else text
        except ValueError:
            arguments, malformed = {}, True
        if not isinstance(arguments, dict):
            arguments, malformed = {}, True
        calls.append(
            ToolCall(raw.get("id") or f"call_{index}", function.get("name") or "", arguments, malformed)
        )
    return calls


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        provider: str = "compatible",
        timeout: float = 60.0,
        max_tokens: int = 1000,
        limiter: RateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.limiter = limiter or RateLimiter()
        self._field = "max_completion_tokens" if provider == "groq" else "max_tokens"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def chat(self, messages: Sequence[dict], tools: Sequence[dict] | None = None) -> LLMReply:
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            self._field: self.max_tokens,
            "messages": list(messages),
            **request_options(self.provider, self.model),
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        size = sum(len(str(m.get("content") or "")) for m in messages)
        # Arabic runs near 3 characters per token, and the output counts too.
        estimated = size // 3 + self.max_tokens
        try:
            response = self.limiter.send(
                lambda: self._client.post("/chat/completions", json=payload), estimated
            )
            if response.is_error:
                raise LLMError(f"{self.provider} returned HTTP {response.status_code}{error_code(response)}")
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            content = strip_reasoning(message.get("content") or "")
            calls = parse_tool_calls(message)
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
            raise LLMError(f"{self.provider} request failed: {type(exc).__name__}") from None
        reason = choice.get("finish_reason") or "stop"
        if reason == "length":
            raise LLMError(f"{self.provider} reply was cut off at {self.max_tokens} tokens")
        if not content and not calls:
            raise LLMError(f"{self.provider} returned an empty reply")
        return LLMReply(content, calls, reason, body.get("usage") or {})


def key_from_env(env: Mapping[str, str]) -> str:
    name = env.get("LLM_API_KEY_ENV", "").strip() or "LLM_API_KEY"
    return env.get(name, "").strip()


def client_from_env(
    env: Mapping[str, str] | None = None,
    transport: httpx.BaseTransport | None = None,
    model: str | None = None,
) -> OpenAICompatibleClient | None:
    """Build a client from the environment, or None when no key is set."""
    env = os.environ if env is None else env
    key = key_from_env(env)
    if not key:
        return None
    provider = env.get("LLM_PROVIDER", "").strip().lower() or "groq"
    base_url = env.get("LLM_BASE_URL", "").strip() or (GROQ_URL if provider == "groq" else "")
    chosen = model or env.get("LLM_MODEL", "").strip() or (GROQ_MODEL if provider == "groq" else "")
    if not base_url or not chosen:
        raise LLMError("a compatible provider needs LLM_BASE_URL and LLM_MODEL")
    return OpenAICompatibleClient(
        key,
        chosen,
        base_url,
        provider,
        float(env.get("LLM_TIMEOUT", "") or 60),
        int(env.get("LLM_MAX_TOKENS", "") or 1000),
        RateLimiter(max_wait=float(env.get("LLM_MAX_WAIT", "") or 30)),
        transport,
    )
