"""What the running server holds: database, rules, search, model and clock."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from jalboot.agent.loop import SupportAgent
from jalboot.api.events import Broker
from jalboot.config import ConfigError, Settings
from jalboot.db.base import create_schema, make_engine, make_session_factory
from jalboot.db.models import WorldMeta
from jalboot.kb.store import KnowledgeBase, load_encoder, load_passages
from jalboot.llm.client import LLMClient, client_from_env
from jalboot.llm.mock import MockPlanner
from jalboot.policy.rules import Rules
from jalboot.world.demo import add_demo_customers, add_staff
from jalboot.world.generator import generate_world

log = logging.getLogger("jalboot")
DEV_STAFF_PASSWORD = "jalboot-local-demo"


class WorldClock:
    """Simulated time. It starts at the world's anchor and runs at real speed, so demo
    orders stay fresh however long ago the database was generated."""

    def __init__(self, anchor: datetime):
        self.anchor = anchor
        self.started = time.monotonic()

    def now(self) -> datetime:
        return self.anchor + timedelta(seconds=time.monotonic() - self.started)


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockPlanner()
    client = client_from_env()
    if client is None:
        raise ConfigError("LLM_MODE=llm needs a key. Set LLM_API_KEY, or use LLM_MODE=mock.")
    return client


def seed_if_empty(session: Session, settings: Settings) -> None:
    if session.scalar(select(WorldMeta.id).limit(1)) is not None:
        return
    password = os.environ.get("DEMO_STAFF_PASSWORD", "").strip()
    if settings.is_production and not password:
        raise ConfigError("production needs DEMO_STAFF_PASSWORD to create the first staff accounts")
    scale = settings.world_scale
    meta_counts = generate_world(
        session, seed=settings.seed, customers=max(int(400 * scale), 10), drivers=max(int(80 * scale), 10),
        orders=max(int(3000 * scale), 40), tickets=max(int(600 * scale), 20),
    )
    meta = session.scalar(select(WorldMeta))
    add_demo_customers(session, meta.anchor)
    add_staff(session, password or DEV_STAFF_PASSWORD)
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

    def agent(self) -> SupportAgent:
        return SupportAgent(self.llm, self.knowledge)

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
        anchor = session.scalar(select(WorldMeta)).anchor
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
