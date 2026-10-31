"""One support turn, from a customer message to a checked reply.

    triage        code decides whether this message must go to a person
    retrieve      search the knowledge base in the customer's language
    plan          the model picks tools; the tool layer decides what is allowed
    check         the reply is tested against the sources and the tool results
    repair        one chance to fix a reply that failed
    fall back     a safe fixed reply and a handoff, never an unchecked answer

The model never receives a customer id and never decides who the customer is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

from jalboot.agent import checks, prompts, replies
from jalboot.agent.triage import triage_message
from jalboot.llm.client import LLMClient, LLMError, ToolCall

Emit = Callable[[dict[str, Any]], None]
MAX_FAILED_ATTEMPTS = 2  # ESC-02, escalation.handoff_after_failed_attempts in rules.json
# A passage that shares too little of the question's meaning is dropped before the model
# sees it. With nothing relevant to cite, the honest answer is the only one left. Tuned
# on the development questions only.
MIN_COVERAGE = 0.25
MAX_STEPS = 6
MAX_TOOL_CALLS = 8
HISTORY_TURNS = 8


class Knowledge(Protocol):
    def search(self, query: str, language: str, k: int = 4) -> list[dict[str, Any]]: ...


class Tools(Protocol):
    def specs(self) -> list[dict[str, Any]]: ...

    def execute(self, name: str, arguments: dict[str, Any], *, malformed: bool = False) -> dict[str, Any]: ...

    def allowed_contacts(self) -> list[str]: ...


@dataclass
class TurnResult:
    reply: str
    language: str
    mode: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    handoff: dict[str, Any] | None = None
    confidence: float = 0.0
    flags: list[str] = field(default_factory=list)
    finish: str = "complete"
    # True when this turn did not help, which counts toward ESC-02's two attempts.
    failed: bool = False


def _no_emit(_event: dict[str, Any]) -> None:
    return None


class SupportAgent:
    def __init__(self, llm: LLMClient, knowledge: Knowledge, *, propagate: tuple[type[BaseException], ...] = ()):
        self.llm = llm
        self.knowledge = knowledge
        # Evaluation passes its budget error here: a stopped run must stop, not
        # degrade into a fallback that would be scored as a real answer.
        self.propagate = propagate
        self.canary = prompts.new_canary()

    @property
    def mode(self) -> str:
        return "mock" if self.llm.provider == "mock" else f"{self.llm.provider}/{self.llm.model}"

    def respond(
        self,
        text: str,
        tools: Tools,
        history: Sequence[dict[str, str]] = (),
        language: str = "en",
        customer_label: str = "",
        emit: Emit = _no_emit,
        failures: int = 0,
    ) -> TurnResult:
        triage = triage_message(text, default_language=language)
        result = TurnResult(reply="", language=triage.language, mode=self.mode, flags=list(triage.signals))
        if triage.handoff_reason:
            self._close_with_handoff(result, triage.handoff_reason, text, tools, history, customer_label, emit)
            return result
        if failures >= MAX_FAILED_ATTEMPTS:
            self._close_with_handoff(result, "repeated_failure", text, tools, history, customer_label, emit)
            return result

        passages = [p for p in self.knowledge.search(text, triage.language, k=4) if p["confidence"] >= MIN_COVERAGE]
        self._plan(result, text, tools, history, passages, customer_label, emit)
        return result

    def _close_with_handoff(self, result, reason, text, tools, history, customer_label, emit) -> None:
        """A handoff decided by code. The reply is fixed text, so no model is involved."""
        summary = replies.handoff_summary(reason, text, history, result.tool_log, customer_label, result.language)
        outcome = self._run_tool(result, tools, ToolCall("handoff", "handoff_to_human", {
            "reason": reason, "summary": summary,
        }), emit)
        if outcome.get("ok"):
            result.handoff = {"reason": reason, "summary": summary, "priority": outcome.get("priority", "P4")}
        result.reply = self._handoff_text(result, reason)
        result.finish = "handoff"
        result.confidence = 1.0

    def _handoff_text(self, result: TurnResult, reason: str) -> str:
        return " ".join([
            *replies.action_lines(result.tool_log, result.language), replies.handoff_reply(reason, result.language),
        ])

    def _run_tool(self, result: TurnResult, tools: Tools, call: ToolCall, emit: Emit) -> dict[str, Any]:
        emit({"type": "tool.start", "id": call.id, "tool": call.name, "arguments": call.arguments})
        outcome = tools.execute(call.name, call.arguments, malformed=call.malformed)
        result.tool_log.append({"tool": call.name, "arguments": call.arguments, "result": outcome})
        emit({"type": "tool.end", "id": call.id, "tool": call.name, "result": outcome})
        return outcome

    def _plan(self, result, text, tools, history, passages, customer_label, emit) -> None:
        system = prompts.system_prompt(result.language, self.canary)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for turn in list(history)[-HISTORY_TURNS:]:
            messages.append({
                "role": "assistant" if turn["role"] == "bot" else "user",
                "content": turn["text"] if turn["role"] == "bot" else prompts.data_block("CUSTOMER_MESSAGE", turn["text"]),
            })
        messages.append({"role": "user", "content": prompts.customer_turn(text, passages)})

        repaired = False
        calls_made = 0
        for _step in range(MAX_STEPS):
            try:
                reply = self.llm.chat(messages, tools.specs())
            except self.propagate:
                raise
            except LLMError as error:
                result.flags.append(f"llm_error: {error}")
                self._fall_back(result, text, tools, history, customer_label, emit)
                return

            if reply.tool_calls:
                messages.append(_assistant_message(reply.content, reply.tool_calls))
                for call in reply.tool_calls:
                    calls_made += 1
                    if calls_made > MAX_TOOL_CALLS:
                        result.flags.append("too_many_tool_calls")
                        self._fall_back(result, text, tools, history, customer_label, emit)
                        return
                    outcome = self._run_tool(result, tools, call, emit)
                    messages.append(prompts.tool_result_message(call.id, call.name, outcome))
                    if outcome.get("error") == "identity_required":
                        result.reply = replies.identity_reply(result.language)
                        result.finish = "identity_required"
                        result.flags.append("identity_required")
                        return
                    if outcome.get("handoff_required"):
                        reason = outcome["handoff_required"]
                        self._close_with_handoff(result, reason, text, tools, history, customer_label, emit)
                        return
                if any(entry["tool"] == "handoff_to_human" and entry["result"].get("ok") for entry in result.tool_log):
                    self._model_handoff(result)
                    return
                continue

            content = checks.tidy_reply(reply.content)
            verdict = self._check(content, passages, result, tools, system)
            if verdict.ok:
                self._accept(result, content, verdict, passages, text, emit)
                return
            result.flags.extend(f"check_failed: {problem}" for problem in verdict.problems)
            if repaired:
                break
            repaired = True
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": prompts.repair_note(verdict.problems)})
        self._fall_back(result, text, tools, history, customer_label, emit)

    def _model_handoff(self, result: TurnResult) -> None:
        entry = next(e for e in reversed(result.tool_log) if e["tool"] == "handoff_to_human")
        arguments = entry["arguments"]
        reason = str(arguments.get("reason") or "low_confidence")
        result.handoff = {"reason": reason, "summary": arguments.get("summary", ""), "priority": entry["result"].get("priority", "P4")}
        result.reply = self._handoff_text(result, reason)
        result.finish = "handoff"
        result.confidence = 0.5

    def _check(self, reply, passages, result, tools, system) -> checks.CheckResult:
        effects = checks.effects_of(result.tool_log)
        return checks.check_reply(
            reply,
            source_count=len(passages),
            evidence=[p["text"] for p in passages],
            tool_results=[entry["result"] for entry in result.tool_log],
            done=effects.done,
            offered=effects.offered,
            amounts=effects.amounts,
            allowed_contacts=tools.allowed_contacts(),
            system_prompt=system,
            canary=self.canary,
            used_tools=any(entry["result"].get("ok") for entry in result.tool_log),
        )

    def _accept(self, result, reply, verdict, passages, text, emit) -> None:
        unsaid = replies.action_lines(result.tool_log, result.language, skip=checks.claimed_actions(reply))
        result.reply = " ".join([reply.strip(), *unsaid])
        for number in verdict.citations:
            passage = passages[number - 1]
            citation = {"n": number, **{k: passage[k] for k in ("id", "title", "text") if k in passage}}
            result.citations.append(citation)
            emit({"type": "citation", "citation": citation})
        used_tools = any(entry["result"].get("ok") for entry in result.tool_log)
        best = max((p.get("confidence", 0.0) for p in passages), default=0.0)
        result.confidence = 0.9 if used_tools else (best if verdict.citations else 0.3)
        result.failed = not used_tools and not verdict.citations and len(text.split()) > 3

    def _fall_back(self, result, text, tools, history, customer_label, emit) -> None:
        """Nothing unchecked reaches the customer, so the conversation goes to a person."""
        result.citations = []
        self._close_with_handoff(result, "low_confidence", text, tools, history, customer_label, emit)
        result.confidence = 0.0


def _assistant_message(content: str, calls: Sequence[ToolCall]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
            }
            for call in calls
        ],
    }
