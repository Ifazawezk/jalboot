"""Runs evaluation cases and saves what happened.

Each case gets its own empty in-memory database, so nothing carries over between
cases. A run writes one line per finished case, so a run that stops at a rate limit
loses nothing, and the next run skips what is already done. Scoring reads only these
saved records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from sqlalchemy import select

from jalboot.agent.loop import SupportAgent
from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import Message
from jalboot.evaluation.cases import UNKNOWN, case_now, complete_identity, load_state
from jalboot.evaluation.unguarded import UnguardedExecutor
from jalboot.llm.cache import BudgetExhausted
from jalboot.llm.client import LLMClient
from jalboot.policy.rules import Rules
from jalboot.security.redact import redact
from jalboot.tools.executor import ToolContext, ToolExecutor

MAX_TURNS = 8
EVAL_CANARY = "REF-evaluation"


@dataclass
class RunConfig:
    unguarded: bool = False


class PoisonedKnowledge:
    """Search that returns a planted document first, as if an attacker had edited the
    search index. Without this a retrieved document attack would test nothing.

    The policy files themselves are reviewed in git before they change, so the attack
    does not reach them, and published() still reads the clean knowledge base."""

    def __init__(self, knowledge: Any, document: dict[str, Any]):
        self.knowledge = knowledge
        self.document = document

    def search(self, query: str, language: str, k: int = 4) -> list[dict[str, Any]]:
        planted = {
            "id": self.document.get("id", "POISON-1"),
            "doc": "planted",
            "doc_title": self.document.get("title", ""),
            "title": self.document.get("title", ""),
            "text": self.document.get("text", ""),
            "updated": "2026-11-01",
            "confidence": 1.0,
        }
        rest = [row for row in self.knowledge.search(query, language, k) if row["id"] != planted["id"]]
        return [planted, *rest[: k - 1]]

    def published(self, section_id: str, language: str) -> dict[str, Any] | None:
        return self.knowledge.published(section_id, language)


def next_customer_message(case: dict[str, Any], reply: str, used: set[int]) -> str | None:
    """SCORING section 1. A scripted reply is sent when the agent mentions its trigger.
    The fallback only fires when the agent actually asked something."""
    lowered = reply.lower()
    for index, row in enumerate(case.get("customer_replies") or []):
        if index in used:
            continue
        if any(word.lower() in lowered for word in row.get("when_agent_mentions", [])):
            used.add(index)
            return row["text"]
    if "?" in reply or "؟" in reply:
        if case.get("customer_fallback"):
            return case["customer_fallback"]
        return UNKNOWN.get(case.get("lang", "en"), UNKNOWN["en"])
    return None


class CaseRunner:
    def __init__(
        self, llm: LLMClient, knowledge: Any, rules: Rules, config: RunConfig | None = None,
        agent_class: Any = None,
    ):
        self.llm = llm
        self.knowledge = knowledge
        self.rules = rules
        self.config = config or RunConfig()
        self.agent_class = agent_class or SupportAgent

    def run(self, case: dict[str, Any]) -> dict[str, Any]:
        engine = make_engine("sqlite:///:memory:")
        create_schema(engine)
        session = make_session_factory(engine)()
        try:
            return self._run(session, case)
        finally:
            session.close()
            engine.dispose()

    def _run(self, session, case: dict[str, Any]) -> dict[str, Any]:
        conversation = load_state(session, case)
        knowledge = self.knowledge
        if case.get("injected_document"):
            knowledge = PoisonedKnowledge(knowledge, case["injected_document"])
        agent = self.agent_class(self.llm, knowledge, propagate=(BudgetExhausted,))
        # The canary is part of the prompt, so a random one would miss the reply cache.
        agent.canary = EVAL_CANARY
        now = case_now(case)
        tool_log: list[dict[str, Any]] = []
        replies: list[str] = []
        citations: list[str] = []
        flags: list[str] = []
        queue = [turn["text"] for turn in case.get("conversation", []) if turn.get("role") == "customer"]
        if case.get("set") == "knowledge":
            queue = [case["question"]]
        used: set[int] = set()
        turn_number = 0
        verified_attempted = False

        while queue and turn_number < MAX_TURNS:
            text = queue.pop(0)
            turn_number += 1
            result = self._turn(session, conversation, agent, text, now, turn_number)
            self._log(tool_log, result, turn_number)
            if result.finish == "identity_required" and not verified_attempted:
                verified_attempted = True
                if complete_identity(session, conversation, case):
                    # The web page repeats the same message after the check passes.
                    result = self._turn(session, conversation, agent, text, now, turn_number)
                    self._log(tool_log, result, turn_number)
            replies.append(result.reply)
            citations.extend(c["id"] for c in result.citations)
            flags.extend(result.flags)
            conversation.failures = conversation.failures + 1 if result.failed else 0
            session.add(Message(conversation_id=conversation.id, role="customer", text=redact(text)[0], created_at=now))
            session.add(Message(conversation_id=conversation.id, role="bot", text=result.reply, created_at=now))
            session.commit()
            if result.handoff is not None or result.finish == "identity_required":
                break
            if not queue:
                follow = next_customer_message(case, result.reply, used)
                if follow is not None:
                    queue.append(follow)

        return {
            "id": case["id"],
            "tool_log": tool_log,
            "replies": replies,
            "citations": citations,
            "mode": agent.mode,
            "canary": getattr(agent, "canary", ""),
            "flags": flags,
        }

    def _turn(self, session, conversation, agent, text, now, number):
        context = ToolContext(
            session=session, conversation=conversation, rules=self.rules, now=now,
            knowledge=agent.knowledge, turn_id=f"turn-{number}",
        )
        executor = UnguardedExecutor if self.config.unguarded else ToolExecutor
        history = [
            {"role": row.role, "text": row.text}
            for row in session.scalars(
                select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
            )
        ]
        return agent.respond(
            redact(text)[0], executor(context), history, conversation.language,
            customer_label=conversation.customer_id or "", failures=conversation.failures,
        )

    @staticmethod
    def _log(tool_log: list[dict[str, Any]], result, turn: int) -> None:
        for entry in result.tool_log:
            tool_log.append({
                "tool": entry["tool"], "args": entry["arguments"], "result": entry["result"], "turn": turn,
            })


def read_done(path: Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    done[row["id"]] = row
                except (ValueError, KeyError):
                    continue
    return done


def run_cases(
    runner: CaseRunner,
    cases: Sequence[dict[str, Any]],
    path: Path,
    progress: Callable[[str], None] = lambda _message: None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Runs what is missing. Returns all records and why it stopped, if it stopped early."""
    done = read_done(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if case["id"] in done:
            continue
        try:
            record = runner.run(case)
        except BudgetExhausted as stop:
            return done, str(stop)
        done[case["id"]] = record
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        progress(case["id"])
    return done, None
