"""What the running server holds: database, rules, search, model and clock."""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from jalboot.agent.loop import SupportAgent
from jalboot.api.events import Broker
from jalboot.config import ConfigError, Settings
from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import Message, StaffUser, WorldMeta
from jalboot.kb.store import KnowledgeBase, load_encoder, load_passages
from jalboot.llm.client import LLMClient, client_from_env
from jalboot.llm.mock import MockPlanner
from jalboot.policy.rules import Rules
from jalboot.security.passwords import hash_password, verify_password
from jalboot.world.demo import add_demo_customers, add_staff
from jalboot.world.generator import generate_world

log = logging.getLogger("jalboot")
DEV_STAFF_PASSWORD = "jalboot-local-demo"
MIN_STAFF_PASSWORD = 12
STAFF_PASSWORD_VARIABLES = {
    "agent": "STAFF_PASSWORD_AGENT",
    "supervisor": "STAFF_PASSWORD_SUPERVISOR",
    "finance_lead": "STAFF_PASSWORD_FINANCE_LEAD",
}


class WorldClock:
    """Simulated time. It starts at the world's anchor and runs at real speed, so demo
    orders stay fresh however long ago the database was generated."""

    def __init__(self, anchor: datetime):
        self.anchor = anchor
        self.started = time.monotonic()

    def now(self) -> datetime:
        return self.anchor + timedelta(seconds=time.monotonic() - self.started)


def _dev_password() -> str:
    return os.environ.get("DEMO_STAFF_PASSWORD", "").strip() or DEV_STAFF_PASSWORD


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockPlanner()
    client = client_from_env()
    if client is None:
        raise ConfigError("LLM_MODE=llm needs a key. Set LLM_API_KEY, or use LLM_MODE=mock.")
    return client


def chosen_staff_passwords(environment: str) -> dict[str, str]:
    """One password per role, so a leak of one does not open the finance lead's account."""
    chosen = {role: os.environ.get(name, "").strip() for role, name in STAFF_PASSWORD_VARIABLES.items()}
    if min(len(password) for password in chosen.values()) < MIN_STAFF_PASSWORD:
        names = ", ".join(STAFF_PASSWORD_VARIABLES.values())
        raise ConfigError(f"{environment} needs {names}, each at least {MIN_STAFF_PASSWORD} characters")
    if len(set(chosen.values())) < len(chosen):
        raise ConfigError("each staff account needs its own password")
    if DEV_STAFF_PASSWORD in chosen.values():
        raise ConfigError("a staff password cannot be the published development password")
    return chosen


def refuse_published_password(session: Session) -> None:
    """Passwords are only read when seeding, so a database seeded for development would
    otherwise keep the password printed in the README after it goes public."""
    for staff in session.scalars(select(StaffUser)):
        if verify_password(DEV_STAFF_PASSWORD, staff.password_hash):
            raise ConfigError("a staff account still has the published development password. Start from a new database.")


def seed_if_empty(session: Session, settings: Settings) -> None:
    if session.scalar(select(WorldMeta.id).limit(1)) is not None:
        return
    chosen = chosen_staff_passwords(settings.environment) if settings.is_public else None
    scale = settings.world_scale
    meta_counts = generate_world(
        session, seed=settings.seed, customers=max(int(400 * scale), 10), drivers=max(int(80 * scale), 10),
        orders=max(int(3000 * scale), 40), tickets=max(int(600 * scale), 20),
        rules=Rules.load(settings.knowledge_dir / "rules.json"),
    )
    meta = session.scalar(select(WorldMeta))
    add_demo_customers(session, meta.anchor)
    # add_staff takes one password, so a public server gives it a throwaway one first.
    add_staff(session, secrets.token_urlsafe(32) if chosen else _dev_password())
    if chosen:
        for staff in session.scalars(select(StaffUser)):
            staff.password_hash = hash_password(chosen[staff.role])
        session.commit()
    log.info("generated a simulated world: %s", meta_counts)


@dataclass
class Runtime:
    settings: Settings
    engine: Engine
    sessions: sessionmaker[Session]
    rules: Rules
    knowledge: KnowledgeBase
    llm: LLMClient
    broker: Broker
    clock: WorldClock
    active_turns: set[str] = field(default_factory=set)
    turns_lock: threading.Lock = field(default_factory=threading.Lock)
    # Errors that should end a turn instead of falling back to a person. A live chat
    # has none. A recording sets this, so a fallback is never saved as the model's reply.
    propagate: tuple[type[BaseException], ...] = ()

    def agent(self, llm: LLMClient | None = None) -> SupportAgent:
        return SupportAgent(llm or self.llm, self.knowledge, propagate=self.propagate)

    @property
    def mode(self) -> str:
        return "mock" if self.llm.provider == "mock" else "live"

    def begin_turn(self, conversation_id: str) -> bool:
        with self.turns_lock:
            if conversation_id in self.active_turns:
                return False
            self.active_turns.add(conversation_id)
            return True

    def end_turn(self, conversation_id: str) -> None:
        with self.turns_lock:
            self.active_turns.discard(conversation_id)


def build_runtime(settings: Settings, llm: LLMClient | None = None) -> Runtime:
    engine = make_engine(settings.database_url)
    create_schema(engine)
    sessions = make_session_factory(engine)
    with sessions() as session:
        seed_if_empty(session, settings)
        if settings.is_public:
            refuse_published_password(session)
        anchor = session.scalar(select(WorldMeta)).anchor
        # active_turns is memory only, so at startup no turn can still be running. Left
        # alone, a turn cut off by a crash would answer turn_in_progress forever. The
        # customer can now send it again, and the action records stop a second payment.
        session.execute(update(Message).where(Message.turn_state == "running").values(turn_state="error"))
        session.commit()
    return Runtime(
        settings=settings,
        engine=engine,
        sessions=sessions,
        rules=Rules.load(settings.knowledge_dir / "rules.json"),
        knowledge=KnowledgeBase(
            load_passages(settings.knowledge_dir), encoder=load_encoder(settings.embeddings),
            cache_dir=settings.index_dir,
        ),
        llm=llm or build_llm(settings),
        broker=Broker(),
        clock=WorldClock(anchor),
    )
