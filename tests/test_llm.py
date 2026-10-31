import json

import httpx
import pytest

from jalboot.llm.cache import Budget, BudgetExhausted, CachedClient, ResponseCache
from jalboot.llm.client import (
    LLMError,
    OpenAICompatibleClient,
    client_from_env,
    strip_reasoning,
)
from jalboot.llm.ratelimit import RateLimited, RateLimiter, parse_duration

SECRET = "test-key-that-must-not-leak"


def reply(content="hello", tool_calls=None, finish="stop"):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": finish}],
        "usage": {"total_tokens": 42},
    }


def client_with(handler, **kwargs):
    limiter = kwargs.pop("limiter", RateLimiter(sleep=lambda _: None))
    return OpenAICompatibleClient(
        SECRET, "m", "https://example.test/v1", "groq",
        limiter=limiter, transport=httpx.MockTransport(handler), **kwargs,
    )


def test_chat_sends_tools_and_reads_tool_calls():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=reply("", [{
            "id": "c1",
            "function": {"name": "track_order", "arguments": '{"order_id": "Q-1"}'},
        }]))

    out = client_with(handler).chat(
        [{"role": "user", "content": "hi"}],
        [{"type": "function", "function": {"name": "track_order"}}],
    )
    assert seen["tool_choice"] == "auto"
    assert seen["max_completion_tokens"] == 1000
    assert out.tool_calls[0].name == "track_order"
    assert out.tool_calls[0].arguments == {"order_id": "Q-1"}
    assert out.tool_calls[0].malformed is False


def test_bad_tool_json_is_flagged_and_never_guessed():
    def handler(request):
        return httpx.Response(200, json=reply("", [{
            "id": "c1", "function": {"name": "issue_refund", "arguments": "{amount: lots"},
        }]))

    call = client_with(handler).chat([{"role": "user", "content": "hi"}]).tool_calls[0]
    assert call.malformed is True
    assert call.arguments == {}


def test_errors_carry_only_status_and_code():
    def handler(request):
        return httpx.Response(401, json={"error": {"code": "invalid_key", "message": f"bad {SECRET}"}})

    with pytest.raises(LLMError) as caught:
        client_with(handler).chat([{"role": "user", "content": "hi"}])
    assert SECRET not in str(caught.value)
    assert "invalid_key" in str(caught.value)


def test_reply_cut_off_raises():
    client = client_with(lambda request: httpx.Response(200, json=reply("par", finish="length")))
    with pytest.raises(LLMError, match="cut off"):
        client.chat([{"role": "user", "content": "hi"}])


def test_think_blocks_are_removed_even_when_unclosed():
    assert strip_reasoning("<think>draft</think>final") == "final"
    assert strip_reasoning("before <think>never closed") == "before"


def test_long_retry_after_stops_instead_of_waiting():
    client = client_with(lambda request: httpx.Response(429, headers={"retry-after": "3600"}))
    with pytest.raises(RateLimited):
        client.chat([{"role": "user", "content": "hi"}])


def test_short_retry_after_waits_then_succeeds():
    sleeps, responses = [], [
        httpx.Response(429, headers={"retry-after": "2"}),
        httpx.Response(200, json=reply()),
    ]
    limiter = RateLimiter(sleep=sleeps.append)
    client = client_with(lambda request: responses.pop(0), limiter=limiter)
    assert client.chat([{"role": "user", "content": "hi"}]).content == "hello"
    assert sleeps == [2.0]


def test_limiter_refuses_to_wait_past_the_limit_it_read():
    now = [0.0]
    limiter = RateLimiter(max_wait=10, clock=lambda: now[0], sleep=lambda _: None)
    limiter.observe({"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "1h"})
    with pytest.raises(RateLimited):
        limiter.send(lambda: httpx.Response(200))


@pytest.mark.parametrize("text,seconds", [("7.66s", 7.66), ("2m30s", 150.0), ("120ms", 0.12), ("3", 3.0)])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == pytest.approx(seconds)


def test_client_reads_the_key_from_a_named_variable():
    env = {"LLM_API_KEY_ENV": "OTHER_KEY", "OTHER_KEY": "abc"}
    client = client_from_env(env)
    assert client is not None
    assert client.provider == "groq"
    assert client.model == "openai/gpt-oss-20b"


def test_no_key_means_no_client():
    assert client_from_env({}) is None


def counting_client(calls):
    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=reply("cached"))
    return client_with(handler)


def test_cache_means_a_rerun_makes_no_requests(tmp_path):
    calls = []
    path = tmp_path / "llm.jsonl"
    messages = [{"role": "user", "content": "مرحبا"}]
    CachedClient(counting_client(calls), ResponseCache(path), Budget()).chat(messages)
    budget = Budget()
    out = CachedClient(counting_client(calls), ResponseCache(path), budget).chat(messages)
    assert len(calls) == 1
    assert budget.cache_hits == 1
    assert out.content == "cached"


def test_a_torn_cache_line_is_skipped(tmp_path):
    path = tmp_path / "llm.jsonl"
    path.write_text('{"key": "a", "content": "ok"}\n{"key": "b", "cont', encoding="utf-8")
    assert list(ResponseCache(path).entries) == ["a"]


def test_budget_stops_the_run(tmp_path):
    calls = []
    client = CachedClient(counting_client(calls), ResponseCache(tmp_path / "c.jsonl"), Budget(requests=1))
    client.chat([{"role": "user", "content": "one"}])
    with pytest.raises(BudgetExhausted):
        client.chat([{"role": "user", "content": "two"}])
    assert len(calls) == 1


def test_a_provider_limit_ends_the_run_rather_than_degrading(tmp_path):
    client = client_with(lambda request: httpx.Response(429, headers={"retry-after": "9999"}))
    cached = CachedClient(client, ResponseCache(tmp_path / "c.jsonl"), Budget())
    with pytest.raises(BudgetExhausted):
        cached.chat([{"role": "user", "content": "hi"}])
