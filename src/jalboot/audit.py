"""The audit log.

Every tool call, every refusal and every staff decision adds a row. Each row
stores a hash of its own content and of the row before it, so changing or removing
any past row breaks the chain from that point on, and verify_chain finds where.

This shows tampering after the fact. It does not stop someone with database access
from rewriting the whole chain, because the hashes carry no secret key.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from jalboot.db.base import utcnow
from jalboot.db.models import AuditEvent

GENESIS = "0" * 64
PG_LOCK_ID = 727001
_write_lock = threading.RLock()


@contextlib.contextmanager
def serial_write(session: Session) -> Iterator[None]:
    """Run a transaction that writes the audit log, with one writer at a time.

    Two transactions that read the same last hash would fork the chain, and two
    refunds on one order could both pass a limit check. A thread lock covers one
    process, and on PostgreSQL an advisory lock covers several.
    """
    with _write_lock:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": PG_LOCK_ID})
        try:
            yield
            session.commit()
        except BaseException:
            session.rollback()
            raise


def _digest(prev_hash: str, at: datetime, fields: dict[str, Any]) -> str:
    body = json.dumps(
        {"prev": prev_hash, "at": at.isoformat(), **fields},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _fields(row: AuditEvent) -> dict[str, Any]:
    return {
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "action": row.action,
        "outcome": row.outcome,
        "conversation_id": row.conversation_id,
        "customer_id": row.customer_id,
        "order_id": row.order_id,
        "detail": row.detail,
    }


def record(
    session: Session,
    *,
    actor_type: str,
    actor_id: str = "",
    action: str,
    outcome: str,
    conversation_id: str | None = None,
    customer_id: str | None = None,
    order_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add one row. The caller commits, normally through serial_write."""
    session.flush()
    previous = session.scalar(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    prev_hash = previous.hash if previous else GENESIS
    at = utcnow()
    row = AuditEvent(
        at=at,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        conversation_id=conversation_id,
        customer_id=customer_id,
        order_id=order_id,
        detail=detail or {},
        prev_hash=prev_hash,
    )
    row.hash = _digest(prev_hash, at, _fields(row))
    session.add(row)
    session.flush()
    return row


def verify_chain(session: Session) -> tuple[bool, int | None]:
    """Walk the whole log. Returns (True, None), or (False, the first bad seq)."""
    expected_prev = GENESIS
    last_seq = 0
    for row in session.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
        if row.seq != last_seq + 1 or row.prev_hash != expected_prev:
            return False, row.seq
        if _digest(row.prev_hash, row.at, _fields(row)) != row.hash:
            return False, row.seq
        expected_prev, last_seq = row.hash, row.seq
    return True, None
