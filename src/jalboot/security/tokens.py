"""Random tokens and browser sessions.

The cookie value is a random token. Only its keyed hash goes in the database, so a
leaked copy of the table cannot be replayed as a login.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from jalboot.db.base import utcnow
from jalboot.db.models import WebSession

STAFF_HOURS = 8
CUSTOMER_HOURS = 12


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(secret: str, token: str) -> str:
    return hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session(
    session: Session,
    secret: str,
    kind: str,
    staff_id: str | None = None,
    conversation_id: str | None = None,
) -> tuple[str, WebSession]:
    """Returns the raw token, which is shown once, and the stored row."""
    token = new_token()
    hours = STAFF_HOURS if kind == "staff" else CUSTOMER_HOURS
    row = WebSession(
        token_hash=hash_token(secret, token),
        kind=kind,
        staff_id=staff_id,
        conversation_id=conversation_id,
        csrf_token=secrets.token_urlsafe(24),
        expires_at=utcnow() + timedelta(hours=hours),
    )
    session.add(row)
    session.flush()
    return token, row


def find_session(session: Session, secret: str, token: str | None, kind: str) -> WebSession | None:
    if not token:
        return None
    row = session.scalar(
        select(WebSession).where(
            WebSession.token_hash == hash_token(secret, token), WebSession.kind == kind
        )
    )
    if row is None or row.expires_at <= utcnow():
        return None
    return row


def drop_session(session: Session, secret: str, token: str | None) -> None:
    if token:
        session.execute(delete(WebSession).where(WebSession.token_hash == hash_token(secret, token)))


def csrf_matches(row: WebSession, supplied: str | None) -> bool:
    return bool(supplied) and hmac.compare_digest(row.csrf_token, supplied)
