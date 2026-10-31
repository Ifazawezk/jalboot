"""Runs one customer turn and turns it into stream events.

A turn runs on a worker thread with its own database session. If the customer closes
the page halfway, the turn still finishes and is saved, so a refund can never be half
recorded. Live events only go out after the database commit, so the desk can never be
told about a row it cannot read yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from jalboot.api import identity, views
from jalboot.api.errors import ApiError, error_body
from jalboot.api.runtime import Runtime
from jalboot.db.base import utcnow
from jalboot.db.models import Approval, AuditEvent, Conversation, Customer, Message, Order
from jalboot.policy.engine import ROLES
from jalboot.security.redact import redact
from jalboot.tools.executor import ToolContext, ToolExecutor

Emit = Callable[[dict[str, Any]], None]
CHUNK = 28
TOOLS_WITH_ORDER = {"track_order", "get_order_details", "explain_delay"}
NO_CODES_IN_CHAT = {
    "en": "For your safety, please do not type a code in the chat. Use the secure form instead.",
    "ar": "حفاظا على أمانك، لا تكتب الرمز في المحادثة. استخدم النموذج الآمن.",
}
LANGUAGES = ("en", "ar")


@dataclass
class TurnPlan:
    conversation_id: str
    message_id: int
    text: str
    language: str
    forwarded: bool = False
    canned: str | None = None


def desk_topic(role: str, language: str) -> str:
    return f"desk:{role}:{language}"


def conversation_topic(conversation_id: str) -> str:
    return f"conversation:{conversation_id}"


def publish_desk(runtime: Runtime, build: Callable[[SimpleNamespace, str], dict[str, Any]]) -> None:
    """Refund views depend on who is reading, so each role and language has its own stream."""
    for role in ROLES:
        viewer = SimpleNamespace(role=role)
        for language in LANGUAGES:
            runtime.broker.publish(desk_topic(role, language), build(viewer, language))


def publish_conversation(runtime: Runtime, session: Session, conversation: Conversation) -> None:
    view = views.live_conversation(session, conversation)
    publish_desk(runtime, lambda _viewer, _language: {"type": "conversation.updated", "conversation": view})


def publish_summary(runtime: Runtime, session: Session) -> None:
    summary = views.desk_summary(session, runtime.clock.now())
    publish_desk(runtime, lambda _viewer, _language: {"type": "summary.updated", "summary": summary})


def publish_audit_since(runtime: Runtime, session: Session, after_seq: int) -> None:
    rows = session.scalars(select(AuditEvent).where(AuditEvent.seq > after_seq).order_by(AuditEvent.seq)).all()
    for row in rows:
        entry = views.audit_entry(session, row)
        publish_desk(runtime, lambda _viewer, _language, entry=entry: {"type": "audit.appended", "entry": entry})


def publish_message(runtime: Runtime, conversation_id: str, message: Message) -> None:
    entry = views.transcript_entry(message)
    publish_desk(runtime, lambda _viewer, _language: {
        "type": "conversation.message", "conversationId": conversation_id, "entry": entry,
    })


def publish_refund(runtime: Runtime, session: Session, approval: Approval, event: str) -> None:
    now = runtime.clock.now()
    publish_desk(runtime, lambda viewer, language: {
        "type": event, "refund": views.refund_view(session, runtime.rules, approval, viewer, now, language),
    })


def last_audit_seq(session: Session) -> int:
    return session.scalar(select(AuditEvent.seq).order_by(AuditEvent.seq.desc()).limit(1)) or 0


def prepare_turn(runtime: Runtime, conversation_id: str, client_id: str, text: str, locale: str) -> TurnPlan:
    """Runs before the stream opens, so these failures can still be plain HTTP errors."""
    with runtime.sessions() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise ApiError(404, "not_found")
        if conversation.status == "closed":
            raise ApiError(409, "conversation_closed")

        existing = session.scalar(
            select(Message).where(Message.conversation_id == conversation_id, Message.client_id == client_id)
        )
        if existing is not None and existing.turn_state not in {"identity_required", "error"}:
            code = "turn_in_progress" if existing.turn_state == "running" else "duplicate_message"
            raise ApiError(409, code)
        if not runtime.begin_turn(conversation_id):
            raise ApiError(409, "turn_in_progress")

        try:
            conversation.language = locale
            conversation.updated_at = utcnow()
            code_expected = identity.open_challenge(session, conversation_id) is not None
            clean, removed = redact(text, code_expected=code_expected)
            if existing is None:
                existing = Message(
                    conversation_id=conversation_id, role="customer", text=clean, client_id=client_id,
                    turn_state="running", language=locale, meta={"redacted": removed},
                )
                session.add(existing)
            else:
                existing.turn_state = "running"
            session.flush()
            plan = TurnPlan(conversation_id, existing.id, existing.text, locale)
            if conversation.status in {"waiting", "agent"}:
                plan.forwarded = True
                existing.turn_state = "forwarded"
            elif "code" in removed:
                # The rule holds even if a page or a script skips the locked chat box.
                plan.canned = NO_CODES_IN_CHAT.get(locale, NO_CODES_IN_CHAT["en"])
            session.commit()
            if plan.forwarded:
                publish_message(runtime, conversation_id, existing)
                publish_conversation(runtime, session, conversation)
                runtime.end_turn(conversation_id)
            return plan
        except BaseException:
            runtime.end_turn(conversation_id)
            raise


def _history(session: Session, conversation_id: str, before_id: int) -> list[dict[str, str]]:
    rows = session.scalars(
        select(Message).where(
            Message.conversation_id == conversation_id, Message.id < before_id,
            Message.role.in_(("customer", "bot")),
        ).order_by(Message.id)
    ).all()
    return [{"role": row.role, "text": row.text} for row in rows]


def _customer_label(session: Session, conversation: Conversation) -> str:
    customer = session.get(Customer, conversation.customer_id) if conversation.customer_id else None
    return f"{customer.name} ({customer.id})" if customer and conversation.verified_at else ""


def run_turn(runtime: Runtime, plan: TurnPlan, emit: Emit) -> None:
    """Worker thread. Emits the stream events, and always ends the stream."""
    session = runtime.sessions()
    try:
        _run(runtime, session, plan, emit)
    except Exception:  # noqa: BLE001  (the customer gets a clean error, never a trace)
        session.rollback()
        message = session.get(Message, plan.message_id)
        if message is not None:
            message.turn_state = "error"
            session.commit()
        emit({"type": "error", **error_body("internal_error", plan.language, True)})
    finally:
        session.close()
        runtime.end_turn(plan.conversation_id)


def _text_events(text: str, emit: Emit) -> None:
    for start in range(0, len(text), CHUNK):
        emit({"type": "text.delta", "delta": text[start:start + CHUNK]})


def _run(runtime: Runtime, session: Session, plan: TurnPlan, emit: Emit) -> None:
    conversation = session.get(Conversation, plan.conversation_id)
    message = session.get(Message, plan.message_id)
    language = plan.language
    audit_mark = last_audit_seq(session)
    emit({"type": "message.start", "messageId": f"m{plan.message_id}"})

    if plan.canned is not None:
        _text_events(plan.canned, emit)
        session.add(Message(conversation_id=conversation.id, role="bot", text=plan.canned, language=language))
        message.turn_state = "complete"
        session.commit()
        emit({"type": "message.end", "finish": "complete"})
        return

    labels: list[str] = []
    pending_approvals: list[str] = []
    counter = {"n": 0}
    ids: dict[str, str] = {}

    def on_tool_publish(event: dict[str, Any]) -> None:
        if event["type"] == "approval.created":
            pending_approvals.append(event["approvalId"])
        else:
            emit(event)

    def translate(event: dict[str, Any]) -> None:
        kind = event["type"]
        if kind == "tool.start":
            counter["n"] += 1
            ids[event["id"]] = f"t{counter['n']}"
            emit({
                "type": "tool.start", "toolCallId": ids[event["id"]], "tool": event["tool"],
                "label": views.tool_label(event["tool"], 0, language),
            })
        elif kind == "tool.end":
            result = event["result"]
            good = bool(result.get("ok"))
            label = views.tool_label(event["tool"], 1, language) if good else views.pick(views.TOOL_FAILED, language)
            labels.append(label)
            emit({"type": "tool.end", "toolCallId": ids.get(event["id"], "t0"),
                  "status": "ok" if good else "error", "label": label})
            if good and event["tool"] in TOOLS_WITH_ORDER and result.get("order_id"):
                order = session.get(Order, result["order_id"])
                if order is not None:
                    emit({"type": "order.card", "order": views.order_card(order, language)})
        elif kind == "citation":
            emit({"type": "citation", "citation": views.citation_view(event["citation"])})

    context = ToolContext(
        session=session, conversation=conversation, rules=runtime.rules, now=runtime.clock.now(),
        knowledge=runtime.knowledge, publish=on_tool_publish, turn_id=str(plan.message_id),
    )
    result = runtime.agent().respond(
        plan.text, ToolExecutor(context), _history(session, conversation.id, plan.message_id), language,
        customer_label=_customer_label(session, conversation), emit=translate, failures=conversation.failures,
    )

    if result.finish == "identity_required":
        emit({"type": "identity.required", "reason": "order_tools"})
    _text_events(result.reply, emit)

    bot = Message(
        conversation_id=conversation.id, role="bot", text=result.reply, language=result.language,
        citations=result.citations,
        meta={
            "tools": labels, "sources": [c.get("doc_title", "") for c in result.citations],
            "confidence": result.confidence, "flags": result.flags, "mode": result.mode,
        },
    )
    session.add(bot)
    message.turn_state = "identity_required" if result.finish == "identity_required" else "complete"
    if result.finish != "identity_required":
        conversation.failures = conversation.failures + 1 if result.failed else 0
    useful = any(entry["result"].get("ok") for entry in result.tool_log) or result.citations
    if result.finish == "complete" and useful:
        conversation.resolved_by = "bot"
    conversation.updated_at = utcnow()
    session.commit()

    publish_message(runtime, conversation.id, message)
    publish_message(runtime, conversation.id, bot)
    publish_conversation(runtime, session, conversation)
    for approval_id in pending_approvals:
        approval = session.get(Approval, approval_id)
        if approval is not None:
            publish_refund(runtime, session, approval, "refund.created")
    publish_audit_since(runtime, session, audit_mark)
    publish_summary(runtime, session)

    finish = {"handoff": "handoff", "identity_required": "identity_required"}.get(result.finish, "complete")
    emit({"type": "message.end", "finish": finish})
