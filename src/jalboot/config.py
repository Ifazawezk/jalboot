"""Settings, all read from the environment once at startup.

LLM_MODE picks how replies are produced:
    mock   scripted replies from a rule based planner, no key, no network
    llm    a real model through the OpenAI compatible client

The default is mock, so a fresh clone runs with no key. A real model is only
used when someone asks for it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from jalboot.env import ROOT

DEV_SECRET = "dev-only-secret-change-me"


class ConfigError(ValueError):
    pass


def _flag(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip().rstrip("/") for part in (value or "").split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str = f"sqlite:///{(ROOT / 'var' / 'jalboot.sqlite3').as_posix()}"
    llm_mode: str = "mock"
    secret_key: str = DEV_SECRET
    environment: str = "development"
    # Origins that may call the API with cookies. Same origin needs no entry.
    allowed_origins: tuple[str, ...] = ()
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    seed: int = 2026
    # Shrinks the generated world, for tests and small machines.
    world_scale: float = 1.0
    show_simulated_otp: bool = True
    web_dist: Path = field(default_factory=lambda: ROOT / "web" / "dist")
    knowledge_dir: Path = field(default_factory=lambda: ROOT / "knowledge")
    index_dir: Path = field(default_factory=lambda: ROOT / "var" / "index")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> None:
        if self.llm_mode not in {"mock", "llm"}:
            raise ConfigError("LLM_MODE must be mock or llm")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ConfigError("COOKIE_SAMESITE must be lax, strict or none")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ConfigError("COOKIE_SAMESITE=none needs COOKIE_SECURE=true")
        if "*" in self.allowed_origins:
            raise ConfigError("ALLOWED_ORIGINS cannot be * because the API uses cookies")
        if self.is_production:
            if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
                raise ConfigError("production needs a SECRET_KEY of at least 32 characters")
            if not self.cookie_secure:
                raise ConfigError("production needs COOKIE_SECURE=true")
            if self.show_simulated_otp:
                raise ConfigError("production must set SHOW_SIMULATED_OTP=false")


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    defaults = Settings()
    settings = Settings(
        database_url=env.get("DATABASE_URL", "").strip() or defaults.database_url,
        llm_mode=env.get("LLM_MODE", "").strip().lower() or defaults.llm_mode,
        secret_key=env.get("SECRET_KEY", "").strip() or defaults.secret_key,
        environment=env.get("ENVIRONMENT", "").strip().lower() or defaults.environment,
        allowed_origins=_list(env.get("ALLOWED_ORIGINS")),
        cookie_secure=_flag(env.get("COOKIE_SECURE"), False),
        cookie_samesite=env.get("COOKIE_SAMESITE", "").strip().lower() or defaults.cookie_samesite,
        seed=int(env.get("WORLD_SEED", "").strip() or defaults.seed),
        world_scale=float(env.get("WORLD_SCALE", "").strip() or defaults.world_scale),
        show_simulated_otp=_flag(env.get("SHOW_SIMULATED_OTP"), True),
        web_dist=Path(env.get("WEB_DIST", "").strip() or defaults.web_dist),
        knowledge_dir=Path(env.get("KNOWLEDGE_DIR", "").strip() or defaults.knowledge_dir),
        index_dir=Path(env.get("INDEX_DIR", "").strip() or defaults.index_dir),
    )
    settings.validate()
    return settings
