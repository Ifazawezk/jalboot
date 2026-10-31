"""The web server: customer chat, the support desk and the built web app."""

from __future__ import annotations

import asyncio
import secrets
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from jalboot import audit
from jalboot.api import chat, identity, metrics, views
from jalboot.api.errors import ApiError, install_handlers, language_of
from jalboot.api.events import SSE_HEADERS, sse_frame, stream_events
from jalboot.api.guards import BrowserGuards
from jalboot.api.runtime import Runtime, build_runtime
from jalboot.config import Settings, load_settings
from jalboot.db.base import utcnow
from jalboot.db.models import Approval, AuditEvent, Conversation, Message, StaffUser, WebSession
from jalboot.env import load_env_file
from jalboot.llm.client import LLMClient
from jalboot.security import throttle, tokens
from jalboot.security.passwords import DUMMY_HASH, verify_password
from jalboot.tools.approvals import DecisionError, decide
from jalboot.tools.executor import ToolContext, ToolExecutor

COOKIE = "jalboot_desk"
Locale = Literal["en", "ar"]
SHIFT_HOURS = 12
AUDIT_PAGE = 20
ALLOWED_HEADERS = ["Authorization", "Content-Type", "Accept-Language", "Last-Event-ID", "X-CSRF-Token"]


class NewConversation(BaseModel):
    locale: Locale = "en"


class SendMessage(BaseModel):
    clientMessageId: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)
    locale: Locale = "en"


class VerifyStart(BaseModel):
    phone: str = Field(min_length=1, max_length=32)


class VerifyConfirm(BaseModel):
    code: str = Field(min_length=1, max_length=12)


class HandoffRequest(BaseModel):
    reason: str = Field(default="customer_request", max_length=64)


class DeskLogin(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=200)


class DeskReply(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class Decision(BaseModel):
    action: Literal["approve", "reject"]
    note: str = Field(default="", max_length=1000)
    version: int


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def get_session(runtime: Runtime = Depends(get_runtime)):
    with runtime.sessions() as session:
        yield session


def customer_auth(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> Conversation:
    """Each conversation has its own token, so knowing an id reaches nothing. Unknown
    ids and wrong tokens get the same answer."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or not token:
        raise ApiError(401, "unauthorized")
    if not secrets.compare_digest(conversation.token_hash, tokens.hash_token(runtime.settings.secret_key, token)):
        raise ApiError(401, "unauthorized")
    return conversation


def desk_session(
    request: Request,
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> WebSession:
    row = tokens.find_session(session, runtime.settings.secret_key, request.cookies.get(COOKIE), "staff")
    if row is None:
        raise ApiError(401, "unauthorized")
    return row


def desk_user(row: WebSession = Depends(desk_session), session: Session = Depends(get_session)) -> StaffUser:
    staff = session.get(StaffUser, row.staff_id)
    if staff is None or not staff.active:
        raise ApiError(401, "unauthorized")
    return staff


def desk_write(
    row: WebSession = Depends(desk_session),
    staff: StaffUser = Depends(desk_user),
    x_csrf_token: str | None = Header(default=None),
) -> StaffUser:
    """The browser attaches the cookie by itself, so every write must also prove that
    the page can read a token no other site can see."""
    if not tokens.csrf_matches(row, x_csrf_token):
        raise ApiError(403, "csrf_failed")
    return staff


def agent_view(staff: StaffUser) -> dict[str, str]:
    return {"id": staff.id, "name": staff.name, "role": staff.role}


api = APIRouter(prefix="/api/v1")


@api.get("/health")
def health(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    return {"status": "ok", "assistant": runtime.mode, "data": "simulated"}


@api.get("/policy")
def policy(runtime: Runtime = Depends(get_runtime)) -> dict[str, Any]:
    rules = runtime.rules
    return {
        "policyVersion": rules.get("meta.policy_version"),
        "currency": rules.get("meta.currency"),
        "assistant": runtime.mode,
        "refund": {
            "automatedLimitQar": rules.get("refunds.approval_limits_qar.automated"),
            "newAccountAutomatedLimitQar": rules.get("refunds.new_account.automated_limit_qar"),
            "agentLimitQar": rules.get("refunds.approval_limits_qar.agent"),
            "cardBusinessDays": rules.get("refunds.timing.card_business_days"),
            "creditMinutes": rules.get("refunds.timing.credit_minutes"),
        },
    }


@api.post("/conversations", status_code=201)
def create_conversation(
    body: NewConversation,
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    token = tokens.new_token()
    now = utcnow()
    conversation = Conversation(
        id=f"cv_{secrets.token_hex(8)}", language=body.locale, created_at=now, updated_at=now,
        token_hash=tokens.hash_token(runtime.settings.secret_key, token),
    )
    session.add(conversation)
    session.commit()
    chat.publish_conversation(runtime, session, conversation)
    chat.publish_summary(runtime, session)
    return {
        "id": conversation.id, "token": token, "locale": body.locale,
        "createdAt": views.iso(now), "verified": False, "assistant": runtime.mode,
    }


@api.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessage,
    conversation: Conversation = Depends(customer_auth),
    runtime: Runtime = Depends(get_runtime),
) -> StreamingResponse:
    plan = await run_in_threadpool(
        chat.prepare_turn, runtime, conversation.id, body.clientMessageId, body.text, body.locale,
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def emit(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def work() -> None:
        try:
            if plan.forwarded:
                emit({"type": "message.start", "messageId": f"m{plan.message_id}"})
                emit({"type": "message.end", "finish": "forwarded"})
            else:
                chat.run_turn(runtime, plan, emit)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    # Runs apart from the response, so a closed page cannot cut a turn in half.
    worker = loop.run_in_executor(None, work)

    async def frames():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield sse_frame(event)
        await worker

    return StreamingResponse(frames(), media_type="text/event-stream", headers=SSE_HEADERS)


@api.post("/conversations/{conversation_id}/verify/start")
def verify_start(
    request: Request,
    body: VerifyStart,
    conversation: Conversation = Depends(customer_auth),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return identity.start(
        session, runtime.rules, runtime.settings.secret_key, conversation, body.phone,
        runtime.settings.show_simulated_otp, request.client.host if request.client else "",
    )


@api.post("/conversations/{conversation_id}/verify/confirm")
def verify_confirm(
    body: VerifyConfirm,
    conversation: Conversation = Depends(customer_auth),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    result = identity.confirm(session, runtime.rules, runtime.settings.secret_key, conversation, body.code)
    chat.publish_conversation(runtime, session, conversation)
    return result


@api.post("/conversations/{conversation_id}/handoff")
def request_handoff(
    body: HandoffRequest,
    conversation: Conversation = Depends(customer_auth),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """A customer can always reach a person, verified or not."""
    mark = chat.last_audit_seq(session)
    context = ToolContext(session=session, conversation=conversation, rules=runtime.rules, now=runtime.clock.now())
    first = session.scalar(
        select(Message.text).where(Message.conversation_id == conversation.id, Message.role == "customer")
        .order_by(Message.id).limit(1)
    )
    summary = f"Reason: customer_request\nAsked first: {first or 'nothing yet'}"
    ToolExecutor(context).execute("handoff_to_human", {"reason": "customer_request", "summary": summary})
    chat.publish_conversation(runtime, session, conversation)
    chat.publish_audit_since(runtime, session, mark)
    chat.publish_summary(runtime, session)
    return views.handoff_view(session, conversation)


def resume_id(last_event_id: str | None) -> int | None:
    try:
        return int(last_event_id) if last_event_id else None
    except ValueError:
        return None


@api.get("/conversations/{conversation_id}/events")
async def conversation_events(
    conversation_id: str,
    conversation: Conversation = Depends(customer_auth),
    last_event_id: str | None = Header(default=None),
    runtime: Runtime = Depends(get_runtime),
) -> StreamingResponse:
    subscription = runtime.broker.subscribe(chat.conversation_topic(conversation.id), resume_id(last_event_id))
    return StreamingResponse(stream_events(subscription), media_type="text/event-stream", headers=SSE_HEADERS)


@api.post("/desk/session")
def desk_login(
    request: Request,
    response: Response,
    body: DeskLogin,
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    now = utcnow()
    settings = runtime.settings
    client = request.client.host if request.client else ""
    keys = [
        tokens.hash_token(settings.secret_key, f"login:{body.email.lower()}"),
        tokens.hash_token(settings.secret_key, f"login-client:{client}"),
    ]
    if any(throttle.is_blocked(session, key, now) for key in keys):
        raise ApiError(429, "too_many_attempts", retryAfterSeconds=throttle.BLOCK_MINUTES * 60)
    staff = session.scalar(select(StaffUser).where(StaffUser.email == body.email.lower()))
    # The hash runs even for an unknown email, so timing does not reveal who has an account.
    good = verify_password(body.password, staff.password_hash if staff else DUMMY_HASH)
    if staff is None or not staff.active or not good:
        for key in keys:
            throttle.note_failure(session, key, now)
        with audit.serial_write(session):
            audit.record(session, actor_type="system", actor_id="desk", action="desk.login_failed", outcome="denied")
        raise ApiError(401, "invalid_credentials")
    for key in keys:
        throttle.note_success(session, key)
    token, row = tokens.create_session(session, settings.secret_key, "staff", staff_id=staff.id)
    session.commit()
    response.set_cookie(
        COOKIE, token, httponly=True, samesite=settings.cookie_samesite, secure=settings.cookie_secure,
        path="/", max_age=tokens.STAFF_HOURS * 3600,
    )
    return {"csrfToken": row.csrf_token, "agent": agent_view(staff)}


@api.get("/desk/me")
def desk_me(row: WebSession = Depends(desk_session), staff: StaffUser = Depends(desk_user)) -> dict[str, Any]:
    return {"agent": agent_view(staff), "csrfToken": row.csrf_token}


@api.post("/desk/logout", status_code=204)
def desk_logout(
    request: Request,
    response: Response,
    _staff: StaffUser = Depends(desk_write),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> Response:
    tokens.drop_session(session, runtime.settings.secret_key, request.cookies.get(COOKIE))
    session.commit()
    result = Response(status_code=204)
    result.delete_cookie(COOKIE, path="/", httponly=True, samesite=runtime.settings.cookie_samesite)
    return result


@api.get("/desk/summary")
def desk_summary(
    _staff: StaffUser = Depends(desk_user),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    return views.desk_summary(session, runtime.clock.now())


@api.get("/desk/conversations")
def desk_conversations(
    _staff: StaffUser = Depends(desk_user), session: Session = Depends(get_session),
) -> dict[str, Any]:
    rows = session.scalars(select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)).all()
    return {"conversations": [views.live_conversation(session, row) for row in rows]}


def _conversation(session: Session, conversation_id: str) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ApiError(404, "not_found")
    return conversation


@api.get("/desk/conversations/{conversation_id}")
def desk_conversation(
    conversation_id: str, _staff: StaffUser = Depends(desk_user), session: Session = Depends(get_session),
) -> dict[str, Any]:
    return views.conversation_detail(session, _conversation(session, conversation_id))


@api.post("/desk/conversations/{conversation_id}/claim")
def desk_claim(
    conversation_id: str,
    staff: StaffUser = Depends(desk_write),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    conversation = _conversation(session, conversation_id)
    mark = chat.last_audit_seq(session)
    with audit.serial_write(session):
        conversation.status = "agent"
        conversation.assigned_staff_id = staff.id
        conversation.updated_at = utcnow()
        audit.record(
            session, actor_type="staff", actor_id=staff.id, action="handoff.joined", outcome="allowed",
            conversation_id=conversation.id, customer_id=conversation.customer_id,
        )
    runtime.broker.publish(chat.conversation_topic(conversation.id), {
        "type": "handoff.update", "handoff": views.handoff_view(session, conversation),
    })
    chat.publish_conversation(runtime, session, conversation)
    chat.publish_audit_since(runtime, session, mark)
    chat.publish_summary(runtime, session)
    return views.live_conversation(session, conversation)


@api.post("/desk/conversations/{conversation_id}/reply", status_code=204)
def desk_reply(
    conversation_id: str,
    body: DeskReply,
    staff: StaffUser = Depends(desk_write),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> Response:
    conversation = _conversation(session, conversation_id)
    mark = chat.last_audit_seq(session)
    now = utcnow()
    message = Message(
        conversation_id=conversation.id, role="agent", text=body.text, language=conversation.language,
        created_at=now, meta={"agent_name": staff.name},
    )
    with audit.serial_write(session):
        session.add(message)
        conversation.updated_at = now
        audit.record(
            session, actor_type="staff", actor_id=staff.id, action="agent.replied", outcome="allowed",
            conversation_id=conversation.id, customer_id=conversation.customer_id,
        )
    runtime.broker.publish(chat.conversation_topic(conversation.id), {
        "type": "agent.message", "messageId": f"a{message.id}", "agentName": staff.name.split()[0],
        "text": body.text, "at": views.iso(now),
    })
    chat.publish_message(runtime, conversation.id, message)
    chat.publish_conversation(runtime, session, conversation)
    chat.publish_audit_since(runtime, session, mark)
    return Response(status_code=204)


@api.get("/desk/refunds")
def desk_refunds(
    request: Request,
    staff: StaffUser = Depends(desk_user),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    now = runtime.clock.now()
    shift_start = now - timedelta(hours=SHIFT_HOURS)
    rows = session.scalars(
        select(Approval).where(
            Approval.kind.in_(("refund", "credit", "address_change")),
            (Approval.status == "pending") | (Approval.decided_at >= shift_start),
        ).order_by(Approval.created_at)
    ).all()
    language = language_of(request)
    return {"refunds": [views.refund_view(session, runtime.rules, row, staff, now, language) for row in rows]}


@api.post("/desk/refunds/{approval_id}/decision")
def desk_decision(
    request: Request,
    approval_id: str,
    body: Decision,
    staff: StaffUser = Depends(desk_write),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if body.action == "reject" and len(body.note.strip()) < 8:
        raise ApiError(422, "validation_error")
    mark = chat.last_audit_seq(session)
    now = runtime.clock.now()
    try:
        outcome = decide(session, approval_id, staff, body.action, body.note, body.version, now, runtime.rules)
    except DecisionError as failed:
        status = {"not_found": 404, "approval_limit_exceeded": 403}.get(failed.code, 409)
        raise ApiError(status, failed.code) from None
    approval = outcome.approval
    if approval.conversation_id:
        runtime.broker.publish(chat.conversation_topic(approval.conversation_id), {
            "type": "refund.update", "refund": views.refund_summary(approval, staff.name.split()[0]),
        })
    chat.publish_refund(runtime, session, approval, "refund.updated")
    chat.publish_audit_since(runtime, session, mark)
    chat.publish_summary(runtime, session)
    return views.refund_view(session, runtime.rules, approval, staff, now, language_of(request))


@api.get("/desk/audit")
def desk_audit(
    filter: Literal["all", "bot", "agent", "guardrail"] = "all",
    cursor: str | None = None,
    _staff: StaffUser = Depends(desk_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(AUDIT_PAGE + 1)
    if cursor and cursor.isdigit():
        query = query.where(AuditEvent.seq < int(cursor))
    if filter == "bot":
        query = query.where(AuditEvent.actor_type == "bot", AuditEvent.action != "guardrail.blocked")
    elif filter == "agent":
        query = query.where(AuditEvent.actor_type == "staff")
    elif filter == "guardrail":
        query = query.where(AuditEvent.action == "guardrail.blocked")
    rows = session.scalars(query).all()
    page = rows[:AUDIT_PAGE]
    return {
        "entries": [views.audit_entry(session, row) for row in page],
        "nextCursor": str(page[-1].seq) if len(rows) > AUDIT_PAGE else None,
    }


@api.get("/desk/audit/verify")
def desk_audit_verify(
    _staff: StaffUser = Depends(desk_user), session: Session = Depends(get_session),
) -> dict[str, Any]:
    good, first_bad = audit.verify_chain(session)
    return {"intact": good, "firstBadEntry": first_bad}


def window_days(windowDays: int = Query(default=7)) -> int:
    """A query value arrives as text, which a Literal of integers would always refuse."""
    if windowDays not in (7, 14, 30):
        raise ApiError(422, "validation_error")
    return windowDays


@api.get("/desk/metrics/top-issues")
def desk_top_issues(
    request: Request,
    window: int = Depends(window_days),
    _staff: StaffUser = Depends(desk_user),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return {"issues": metrics.top_issues(session, runtime.clock.now(), window, language_of(request))}


@api.get("/desk/metrics/quality")
def desk_quality(
    request: Request,
    window: int = Depends(window_days),
    _staff: StaffUser = Depends(desk_user),
    runtime: Runtime = Depends(get_runtime),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return metrics.quality_report(session, runtime.clock.now(), window, language_of(request))


@api.get("/desk/events")
async def desk_events(
    request: Request,
    staff: StaffUser = Depends(desk_user),
    last_event_id: str | None = Header(default=None),
    runtime: Runtime = Depends(get_runtime),
) -> StreamingResponse:
    topic = chat.desk_topic(staff.role, language_of(request))
    subscription = runtime.broker.subscribe(topic, resume_id(last_event_id))
    return StreamingResponse(stream_events(subscription), media_type="text/event-stream", headers=SSE_HEADERS)


class WebApp(StaticFiles):
    """Serves the built page, and sends any page route to index.html."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as missing:
            if missing.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    load_env_file()
    settings = settings or load_settings()
    app = FastAPI(title="Jalboot support", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = build_runtime(settings, llm)
    install_handlers(app)
    app.include_router(api)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=ALLOWED_HEADERS,
        expose_headers=["Retry-After"],
    )
    app.add_middleware(BrowserGuards, allowed_origins=settings.allowed_origins, https=settings.cookie_secure)
    if settings.web_dist.exists():
        app.mount("/", WebApp(directory=settings.web_dist, html=True), name="web")
    return app
