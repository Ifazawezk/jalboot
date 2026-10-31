"""Database engine and session handling. SQLite in development, PostgreSQL ready."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


# Columns that a database made by an earlier version may not have.
ADDED_COLUMNS = {
    "login_throttle": {"window_start": "TIMESTAMP"},
    "drivers": {"name_ar": "VARCHAR(120) NOT NULL DEFAULT ''"},
}


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores UTC and always returns an aware datetime, on SQLite and PostgreSQL.

    SQLite drops the offset. Without this, comparing a stored time with an aware
    one raises, and comparing two naive ones hides a wrong time zone.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime passed to the database")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    if parsed.database in (None, "", ":memory:"):
        engine = create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(connection, _record):
        cursor = connection.cursor()
        # Foreign keys are off by default in SQLite. WAL lets the dashboard read
        # while a chat turn writes.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    from jalboot.db import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(engine)
    _upgrade_schema(engine)


def _upgrade_schema(engine: Engine) -> None:
    """create_all adds missing tables but never changes one that exists, so a database
    from an earlier version needs its columns brought up to date here."""
    inspector = inspect(engine)
    missing = [
        f"ALTER TABLE {table} ADD COLUMN {name} {kind}"
        for table, columns in ADDED_COLUMNS.items()
        for name, kind in columns.items()
        if name not in {column["name"] for column in inspector.get_columns(table)}
    ]
    if missing:
        with engine.begin() as connection:
            for statement in missing:
                connection.execute(text(statement))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
