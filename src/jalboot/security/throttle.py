"""Slows down guessing, with one counter per key. Keys are hashes, so this table holds
no email address, phone number or client address."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from jalboot.db.models import LoginThrottle

MAX_FAILURES = 5
BLOCK_MINUTES = 15


def is_blocked(session: Session, key: str, now: datetime) -> bool:
    row = session.get(LoginThrottle, key)
    return bool(row and row.blocked_until and row.blocked_until > now)


def note_failure(
    session: Session, key: str, now: datetime, limit: int = MAX_FAILURES, minutes: int = BLOCK_MINUTES,
) -> None:
    row = session.get(LoginThrottle, key)
    if row is None:
        row = LoginThrottle(key=key, failures=0)
        session.add(row)
    row.failures += 1
    if row.failures >= limit:
        row.blocked_until = now + timedelta(minutes=minutes)
        row.failures = 0


def note_success(session: Session, key: str) -> None:
    row = session.get(LoginThrottle, key)
    if row is not None:
        session.delete(row)
