"""The identity check. It runs outside the chat, so a phone number or a code never
enters a message, the conversation history or a model's context.

verify/start answers the same way whether or not the number has an account, so it
cannot be used to find customers. Failures count per phone number, not per
conversation, so opening a new chat does not give an attacker more guesses. They also
count per client, so spreading guesses across many numbers does not either.

Each limit is read and counted under the write lock. Otherwise a burst of requests all
read the same count, and every guess in it gets compared.

With SHOW_SIMULATED_OTP on, the code is returned to the page so the demo works with no
SMS provider. Anyone who knows a phone number can then pass, which is why production
settings refuse to start with it on.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from jalboot import audit
from jalboot.api.errors import ApiError
from jalboot.db.base import utcnow
from jalboot.db.models import Conversation, Customer, OtpChallenge
from jalboot.policy.rules import Rules
from jalboot.security import throttle
from jalboot.text.normalize import DIGITS

PHONE = re.compile(r"^\+974\d{8}$")
CODE = re.compile(r"^\d{6}$")
EXPIRES_SECONDS = 300
RESEND_SECONDS = 30
SEND_LIMIT = 5
SEND_WINDOW_MINUTES = 15
CONFIRM_CLIENT_LIMIT = 20


def _key(secret: str, *parts: str) -> str:
    return hmac.new(secret.encode(), "|".join(parts).encode(), hashlib.sha256).hexdigest()


def stored_phone(digits: str) -> str:
    """+97401001001 to the stored form, +974 0100 1001."""
    return f"{digits[:4]} {digits[4:8]} {digits[8:]}"


def mask(phone: str) -> str:
    return f"+974 •••• {phone[-4:]}"


def _failures_limit(rules: Rules) -> tuple[int, int]:
    return int(rules.get("account.otp.max_failures")), int(rules.get("account.otp.lock_minutes"))


def _seconds_left(session: Session, key: str, now: datetime) -> int:
    row = session.get(throttle.LoginThrottle, key)
    if row is None or row.blocked_until is None:
        return 0
    return max(int((row.blocked_until - now).total_seconds()), 1)


def start(
    session: Session, rules: Rules, secret: str, conversation: Conversation, phone: str, reveal: bool, client: str,
) -> dict:
    phone = phone.strip().translate(DIGITS)
    if not PHONE.match(phone):
        raise ApiError(422, "invalid_phone")
    now = utcnow()
    phone_key = _key(secret, "otp", phone)
    send_key = _key(secret, "otp-send", phone)
    client_key = _key(secret, "otp-client", client)
    with audit.serial_write(session):
        session.expire_all()
        for key in (phone_key, send_key, client_key):
            if throttle.is_blocked(session, key, now):
                left = _seconds_left(session, key, now)
                raise ApiError(429, "too_many_attempts", retryAfterSeconds=left)

        customer = session.scalar(select(Customer).where(Customer.phone == stored_phone(phone)))
        session.execute(
            update(OtpChallenge).where(
                OtpChallenge.conversation_id == conversation.id, OtpChallenge.consumed_at.is_(None)
            ).values(consumed_at=now)
        )
        code = f"{secrets.randbelow(1_000_000):06d}"
        session.add(OtpChallenge(
            conversation_id=conversation.id,
            customer_id=customer.id if customer else None,
            code_hash=_key(secret, conversation.id, code),
            phone_key=phone_key,
            expires_at=now + timedelta(seconds=EXPIRES_SECONDS),
        ))
        # Limits how many messages one number can be sent. It also stops this endpoint
        # being used to flood a stranger's phone.
        throttle.note_failure(session, send_key, now, SEND_LIMIT, SEND_WINDOW_MINUTES)
        throttle.note_failure(session, client_key, now, SEND_LIMIT * 4, SEND_WINDOW_MINUTES)
    return {
        "status": "code_sent",
        "maskedPhone": mask(phone),
        "expiresInSeconds": EXPIRES_SECONDS,
        "resendInSeconds": RESEND_SECONDS,
        "simulatedCode": code if reveal else None,
    }


def open_challenge(session: Session, conversation_id: str) -> OtpChallenge | None:
    return session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.conversation_id == conversation_id, OtpChallenge.consumed_at.is_(None)
        ).order_by(OtpChallenge.id.desc()).limit(1)
    )


def code_check(secret: str, challenge: OtpChallenge | None) -> Callable[[str], bool] | None:
    """Tells whether some digits are the open code, so chat text can be searched for it
    while only its keyed hash is ever stored."""
    if challenge is None:
        return None
    return lambda digits: hmac.compare_digest(_key(secret, challenge.conversation_id, digits), challenge.code_hash)


def _try_code(
    session: Session, rules: Rules, secret: str, conversation: Conversation, code: str, client_key: str, now: datetime,
) -> ApiError | Customer:
    """Runs under the write lock. A refused guess is never compared. This returns an
    error rather than raising one, because raising would roll back the count."""
    challenge = open_challenge(session, conversation.id)
    if challenge is None:
        return ApiError(410, "code_expired")
    for key in (challenge.phone_key, client_key):
        if throttle.is_blocked(session, key, now):
            return ApiError(429, "too_many_attempts", retryAfterSeconds=_seconds_left(session, key, now))
    if challenge.expires_at <= now:
        challenge.consumed_at = now
        return ApiError(410, "code_expired")

    max_failures, lock_minutes = _failures_limit(rules)
    expected = _key(secret, conversation.id, code)
    good = CODE.match(code) is not None and hmac.compare_digest(expected, challenge.code_hash)
    if not good or challenge.customer_id is None:
        challenge.attempts += 1
        throttle.note_failure(session, challenge.phone_key, now, max_failures, lock_minutes)
        throttle.note_failure(session, client_key, now, CONFIRM_CLIENT_LIMIT, lock_minutes)
        audit.record(
            session, actor_type="system", actor_id="identity", action="identity.failed", outcome="denied",
            conversation_id=conversation.id, detail={"attempt": challenge.attempts},
        )
        if throttle.is_blocked(session, challenge.phone_key, now):
            return ApiError(429, "too_many_attempts", retryAfterSeconds=lock_minutes * 60)
        return ApiError(400, "invalid_code", retryable=True, attemptsLeft=max(max_failures - challenge.attempts, 0))

    customer = session.get(Customer, challenge.customer_id)
    challenge.consumed_at = now
    # The client count stays. Clearing it would let one real account reset its guesses.
    throttle.note_success(session, challenge.phone_key)
    conversation.customer_id = customer.id
    conversation.verified_at = now
    audit.record(
        session, actor_type="system", actor_id="identity", action="identity.verified", outcome="allowed",
        conversation_id=conversation.id, customer_id=customer.id,
    )
    return customer


def confirm(
    session: Session, rules: Rules, secret: str, conversation: Conversation, code: str, client: str,
) -> dict:
    code = code.strip().translate(DIGITS)
    now = utcnow()
    client_key = _key(secret, "otp-confirm-client", client)
    with audit.serial_write(session):
        session.expire_all()
        outcome = _try_code(session, rules, secret, conversation, code, client_key, now)
    if isinstance(outcome, ApiError):
        raise outcome
    arabic = conversation.language == "ar" and outcome.name_ar
    return {"verified": True, "customerName": (outcome.name_ar if arabic else outcome.name).split()[0]}
