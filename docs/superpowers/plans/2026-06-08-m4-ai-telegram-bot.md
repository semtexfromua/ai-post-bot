# M4 AI Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **BEFORE STARTING:** Read the canonical contracts at `docs/superpowers/plans/_contracts.md` and the spec at `docs/superpowers/specs/2026-06-08-m4-ai-telegram-bot-design.md`. All task code adheres to those signatures/paths.

**Goal:** Build an AI news-to-Telegram pipeline that collects news (RSS/sites + public TG channels via Telethon), filters/dedups, generates a punchy post via OpenAI, and publishes to a channel via an aiogram bot — on a 30-min Celery Beat schedule, with a FastAPI `/api/v1` admin API and `/docs`.

**Architecture:** Sync-everywhere (FastAPI + SQLAlchemy 2.0 + Celery), with async quarantined to Telethon (read) and aiogram (publish) via `asyncio.run()` inside Celery tasks. Redis = broker + result backend + dedup + lock. Postgres (compose) / SQLite (local) via `DATABASE_URL`. Idempotent, DB-state-driven pipeline.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, Celery 5.6 + Redis, openai (sync), aiogram 3.2x, Telethon 1.43.x, feedparser/httpx/selectolax/trafilatura, lingua + pymorphy3, structlog, Flower, pytest + respx + fakeredis, ruff.

**Execution rules:** TDD (failing test → run → implement → run → commit). Conventional commits, one logical unit per commit. Mock all external I/O (OpenAI via respx, Telethon/aiogram patched, redis via fakeredis). Run `uv run ruff check` before each commit.

---


## Phase 0 — Scaffolding & Tooling

### Task P0.1: pyproject.toml with uv deps, ruff, pytest config

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/pyproject.toml`

Steps:
- [ ] Create `pyproject.toml` with runtime deps pinned to the contract stack, dev dependency-group, ruff (spec §16), and pytest config:

```toml
[project]
name = "m4-ai-telegram-bot"
version = "0.1.0"
description = "AI news-to-Telegram bot: collect, filter, generate, publish."
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.32,<0.33",
    "sqlalchemy>=2.0,<2.1",
    "alembic>=1.14,<1.15",
    "pydantic>=2.9,<3.0",
    "pydantic-settings>=2.6,<3.0",
    "celery>=5.6,<5.7",
    "redis>=5.2,<6.0",
    "openai>=1.54,<2.0",
    "aiogram>=3.21,<3.22",
    "telethon>=1.43,<1.44",
    "feedparser>=6.0,<7.0",
    "httpx>=0.27,<0.28",
    "selectolax>=0.3,<0.4",
    "trafilatura>=2.0,<3.0",
    "lingua-language-detector>=2.0,<3.0",
    "pymorphy3>=2.0,<3.0",
    "pymorphy3-dicts-uk>=2.4",
    "pymorphy3-dicts-ru>=2.4",
    "structlog>=24.4,<25.0",
    "flower>=2.0,<3.0",
    "psycopg2-binary>=2.9,<3.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9.0",
    "pytest-cov>=6.0,<7.0",
    "respx>=0.21,<0.22",
    "fakeredis>=2.26,<3.0",
    "ruff>=0.8,<0.9",
    "pre-commit>=4.0,<5.0",
]

[tool.ruff]
target-version = "py312"
exclude = ["alembic"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "B904"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
filterwarnings = ["ignore::DeprecationWarning"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] Verify the file parses and deps resolve:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv sync --all-groups
```

Expected: lockfile created, virtualenv populated, no resolution errors.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add pyproject.toml uv.lock && git commit -m "chore: add pyproject.toml with uv deps, ruff and pytest config"
```

### Task P0.2: .env.example with every config key

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/.env.example`

Steps:
- [ ] Create `.env.example` covering every field from the Config contract, each with a placeholder and a one-line comment:

```dotenv
# Environment: "local" (SQLite, FakeGenerator) or "prod" (Postgres, OpenAI)
ENVIRONMENT=local

# SQLAlchemy DB URL; local default SQLite, compose uses postgresql+psycopg2://...
DATABASE_URL=sqlite:///./app.db

# Redis URL — Celery broker + result backend + dedup + locks
REDIS_URL=redis://localhost:6379/0

# OpenAI API key (SecretStr) — get from platform.openai.com
OPENAI_API_KEY=sk-your-openai-key-here
# OpenAI chat model used for post generation
OPENAI_MODEL=gpt-4o-mini
# OpenAI client request timeout in seconds
OPENAI_TIMEOUT=30

# Telegram app api_id (int) from my.telegram.org
TELEGRAM_API_ID=0
# Telegram app api_hash (SecretStr) from my.telegram.org
TELEGRAM_API_HASH=your-telegram-api-hash
# Telethon StringSession (SecretStr) — mint via `python -m scripts.login`
TELETHON_STRING_SESSION=your-telethon-string-session
# Bot API token (SecretStr) from @BotFather; bot must be channel admin
TELEGRAM_BOT_TOKEN=123456:your-bot-token
# Target channel id (int) where posts are published
TELEGRAM_CHANNEL_ID=-1000000000000

# Comma/JSON list of allowed languages for the filter
ALLOWED_LANGUAGES=["uk","ru","en"]
# Dedup Redis TTL in seconds (default 7 days)
DEDUP_TTL_SECONDS=604800
# Keyword match semantics: "any" (OR) or "all" (AND)
KEYWORD_MATCH_MODE=any
# Hard Telegram message length guard (chars)
POST_MAX_LEN=4096
```

- [ ] Verify the file is non-empty and tracked:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && test -s .env.example && git status --short .env.example
```

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add .env.example && git commit -m "chore: add .env.example with all config keys"
```

### Task P0.3: app package skeleton (__init__ files)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/schemas/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/api/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/api/v1/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/api/v1/routers/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/news_parser/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/filter/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/ai/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/telegram/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/tasks/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/scripts/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/__init__.py`

Steps:
- [ ] Create all package `__init__.py` files (each empty) matching the package layout from the contracts:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && mkdir -p app/core app/models app/schemas app/api/v1/routers app/news_parser app/filter app/ai app/telegram app/tasks scripts tests && touch app/__init__.py app/core/__init__.py app/models/__init__.py app/schemas/__init__.py app/api/__init__.py app/api/v1/__init__.py app/api/v1/routers/__init__.py app/news_parser/__init__.py app/filter/__init__.py app/ai/__init__.py app/telegram/__init__.py app/tasks/__init__.py scripts/__init__.py tests/__init__.py
```

- [ ] Verify the package is importable:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run python -c "import app, app.core, app.api.v1.routers, app.tasks; print('ok')"
```

Expected: prints `ok`.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add app scripts tests && git commit -m "chore: scaffold app package skeleton"
```

### Task P0.4: app/core/config.py — Settings

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/config.py`
- Test: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_config.py`

Steps:
- [ ] Write failing test asserting Settings loads from env and types/secrets behave per contract:

```python
# tests/test_config.py
import importlib

import app.core.config as config_module


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db:5432/m4")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("TELEGRAM_API_ID", "424242")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash-abc")
    monkeypatch.setenv("TELETHON_STRING_SESSION", "sess-xyz")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:bot-token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "-1009999")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings()

    assert settings.ENVIRONMENT == "prod"
    assert settings.DATABASE_URL == "postgresql+psycopg2://u:p@db:5432/m4"
    assert settings.REDIS_URL == "redis://redis:6379/1"
    assert settings.OPENAI_API_KEY.get_secret_value() == "sk-test-123"
    assert settings.OPENAI_MODEL == "gpt-4o-mini"
    assert settings.OPENAI_TIMEOUT == 30
    assert settings.TELEGRAM_API_ID == 424242
    assert settings.TELEGRAM_API_HASH.get_secret_value() == "hash-abc"
    assert settings.TELETHON_STRING_SESSION.get_secret_value() == "sess-xyz"
    assert settings.TELEGRAM_BOT_TOKEN.get_secret_value() == "111:bot-token"
    assert settings.TELEGRAM_CHANNEL_ID == -1009999
    assert settings.ALLOWED_LANGUAGES == ["uk", "ru", "en"]
    assert settings.DEDUP_TTL_SECONDS == 604800
    assert settings.KEYWORD_MATCH_MODE == "any"
    assert settings.POST_MAX_LEN == 4096


def test_secrets_are_not_plain_in_repr(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "h")
    monkeypatch.setenv("TELETHON_STRING_SESSION", "s")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "1")

    reloaded = importlib.reload(config_module)
    settings = reloaded.Settings()

    assert "sk-secret" not in repr(settings.OPENAI_API_KEY)
```

- [ ] Run the test — expect FAIL (module/Settings not yet defined):

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_config.py -q
```

Expected: FAIL (ImportError / AttributeError on `Settings`).

- [ ] Implement `app/core/config.py` exactly per the Config contract:

```python
# app/core/config.py
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "prod"] = "local"

    DATABASE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: SecretStr
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 30

    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: SecretStr
    TELETHON_STRING_SESSION: SecretStr
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_CHANNEL_ID: int

    ALLOWED_LANGUAGES: list[str] = ["uk", "ru", "en"]
    DEDUP_TTL_SECONDS: int = 604800
    KEYWORD_MATCH_MODE: Literal["any", "all"] = "any"
    POST_MAX_LEN: int = 4096


settings = Settings()
```

- [ ] Run the test — expect PASS:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_config.py -q
```

Expected: 2 passed.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add app/core/config.py tests/test_config.py && git commit -m "feat: add Settings config (pydantic-settings)"
```

### Task P0.5: app/core/logging.py — configure_logging

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/logging.py`
- Test: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_logging.py`

Steps:
- [ ] Write failing test asserting `configure_logging()` runs and bound context appears in output:

```python
# tests/test_logging.py
import structlog

from app.core.logging import configure_logging


def test_configure_logging_binds_context():
    configure_logging()
    cap = structlog.testing.LogCapture()
    structlog.configure(processors=[cap])

    log = structlog.get_logger().bind(news_id="n-1")
    log.info("parsed")

    assert cap.entries[0]["event"] == "parsed"
    assert cap.entries[0]["news_id"] == "n-1"


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()
    assert structlog.is_configured()
```

- [ ] Run the test — expect FAIL (module missing):

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_logging.py -q
```

Expected: FAIL (ModuleNotFoundError on `app.core.logging`).

- [ ] Implement `app/core/logging.py`:

```python
# app/core/logging.py
import logging

import structlog


def configure_logging() -> None:
    """Configure structlog for JSON output with bound context (news_id/post_id)."""
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] Run the test — expect PASS:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_logging.py -q
```

Expected: 2 passed.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add app/core/logging.py tests/test_logging.py && git commit -m "feat: add structlog configure_logging"
```

### Task P0.6: app/core/db.py — engine, SessionLocal, get_db

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/db.py`
- Test: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_db.py`

Steps:
- [ ] Write failing test asserting `get_db` yields a usable Session and SQLite `check_same_thread` connect-arg is applied:

```python
# tests/test_db.py
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import db


def test_get_db_yields_session():
    gen = db.get_db()
    session = next(gen)
    try:
        assert isinstance(session, Session)
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def test_engine_is_sqlite_with_check_same_thread():
    # local default DATABASE_URL is sqlite -> connect_args includes check_same_thread
    assert db.engine.url.get_backend_name() == "sqlite"
    assert db.engine.dialect.create_connect_args(db.engine.url)[1].get(
        "check_same_thread"
    ) is False
```

- [ ] Run the test — expect FAIL (module missing):

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_db.py -q
```

Expected: FAIL (ModuleNotFoundError on `app.core.db`).

- [ ] Implement `app/core/db.py` per the DB contract:

```python
# app/core/db.py
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as s:
        yield s
```

- [ ] Run the test — expect PASS:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_db.py -q
```

Expected: 2 passed.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add app/core/db.py tests/test_db.py && git commit -m "feat: add db engine, SessionLocal and get_db"
```

### Task P0.7: app/main.py + /health endpoint

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/api/health.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/main.py`
- Test: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_health.py`

Steps:
- [ ] Write failing test for `GET /health`:

```python
# tests/test_health.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] Run the test — expect FAIL (app/health missing):

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_health.py -q
```

Expected: FAIL (ModuleNotFoundError on `app.main`).

- [ ] Implement `app/api/health.py` (health router, outside `/api/v1`):

```python
# app/api/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] Implement `app/main.py` (FastAPI app, configures logging, mounts health; `api_v1_router` to be wired in a later phase):

```python
# app/main.py
from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="M4 AI Telegram Bot")
app.include_router(health_router)
```

- [ ] Run the test — expect PASS:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_health.py -q
```

Expected: 1 passed.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add app/main.py app/api/health.py tests/test_health.py && git commit -m "feat: add FastAPI app with /health endpoint"
```

### Task P0.8: tests/conftest.py — base fixtures (TestClient, get_db override, fakeredis)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/conftest.py`
- Test: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_conftest_fixtures.py`

Steps:
- [ ] Write `tests/conftest.py` with base fixtures: in-memory SQLite session (function-scoped, rollback teardown), `app.dependency_overrides[get_db]`, sync `TestClient`, and a `fakeredis` fixture:

```python
# tests/conftest.py
import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(engine, expire_on_commit=False, class_=Session)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)
```

- [ ] Write a fixture smoke-test:

```python
# tests/test_conftest_fixtures.py
from sqlalchemy import text


def test_client_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_db_session_works(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1


def test_fake_redis_set_nx(fake_redis):
    assert fake_redis.set("m4:seen:abc", "1", nx=True, ex=10) is True
    assert fake_redis.set("m4:seen:abc", "1", nx=True, ex=10) is None
```

- [ ] Run the fixture tests — expect PASS:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest tests/test_conftest_fixtures.py -q
```

Expected: 3 passed.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add tests/conftest.py tests/test_conftest_fixtures.py && git commit -m "test: add base conftest fixtures (client, db_session, fake_redis)"
```

### Task P0.9: .pre-commit-config.yaml

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/.pre-commit-config.yaml`

Steps:
- [ ] Create `.pre-commit-config.yaml` with basic hooks + ruff-check (--fix) then ruff-format (order matters, spec §16):

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        name: ruff-check
        args: [--fix]
      - id: ruff-format
```

- [ ] Verify the config is valid and the whole repo is ruff-clean:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pre-commit validate-config .pre-commit-config.yaml && uv run ruff check . && uv run ruff format --check .
```

Expected: config valid; `ruff check` reports "All checks passed!"; format check passes.

- [ ] Commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add .pre-commit-config.yaml && git commit -m "chore: add pre-commit config (basic hooks + ruff)"
```

### Task P0.10: Phase 0 verification — full suite green and ruff clean

**Files:**
- (no new files; gate task)

Steps:
- [ ] Ensure deps are fully synced:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv sync --all-groups
```

Expected: environment up to date, no changes needed.

- [ ] Run the entire test suite:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run pytest -q
```

Expected: all Phase 0 tests pass (config, logging, db, health, conftest fixtures), 0 failures.

- [ ] Run ruff lint + format check across the repo:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && uv run ruff check . && uv run ruff format --check .
```

Expected: "All checks passed!" and format check clean.

- [ ] If anything changed (e.g. lockfile), commit:

```bash
cd /home/jarvis/Programming/ai-post-generated-bot && git add -A && git commit -m "chore: finalize Phase 0 scaffolding (suite green, ruff clean)" || echo "nothing to commit"
```

---


## Phase 1 — Data Layer (models, enums, Alembic)

### Task P1.1: Project bootstrap — pyproject, ruff, package skeleton

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/pyproject.toml`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/__init__.py`

Steps:
- [ ] Create `pyproject.toml` with the minimal dependency slice the data layer needs (SQLAlchemy, Alembic, pydantic-settings, plus dev tools). Full content:

```toml
[project]
name = "m4-ai-telegram-bot"
version = "0.1.0"
description = "AI news-to-Telegram bot (M4 capstone)"
requires-python = ">=3.12"
dependencies = [
    "sqlalchemy>=2.0,<2.1",
    "alembic>=1.13",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]

[tool.ruff]
target-version = "py312"
exclude = ["alembic"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
ignore = ["E501", "B008", "B904"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] Create empty package markers: `app/__init__.py`, `app/core/__init__.py`, `app/models/__init__.py`, `tests/__init__.py` (each an empty file).
- [ ] Initialize the dependency environment and lockfile:
```bash
uv sync
```
- [ ] Verify tooling resolves and config is valid:
```bash
uv run ruff check .
```
Expected: no errors (clean tree; `ruff` reports "All checks passed!").
- [ ] Commit:
```bash
git add pyproject.toml uv.lock app/__init__.py app/core/__init__.py app/models/__init__.py tests/__init__.py
git commit -m "chore: bootstrap project with uv, ruff, and package skeleton

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.2: Settings (config.py) — DATABASE_URL only-what's-needed slice

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/config.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_config.py`

> Note: full `Settings` per contracts §Config has required secrets (no defaults), which would break model/Alembic import in a bare data-layer phase. To keep Phase 1 importable without a populated `.env`, this task defines the contract-named fields but gives the secret/Telegram fields safe defaults; later phases tighten them. `DATABASE_URL` matches the contract default exactly.

Steps:
- [ ] (TDD) Write failing test `tests/test_config.py`:

```python
from app.core.config import Settings, settings


def test_default_database_url_is_sqlite():
    s = Settings(_env_file=None)
    assert s.DATABASE_URL == "sqlite:///./app.db"


def test_database_url_overridable_via_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./other.db")
    s = Settings(_env_file=None)
    assert s.DATABASE_URL == "sqlite:///./other.db"


def test_module_level_settings_instance_exists():
    assert settings.DATABASE_URL
```

- [ ] Run it — expect FAIL (module does not exist):
```bash
uv run pytest tests/test_config.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.core.config'`.

- [ ] Implement `app/core/config.py` (contract-faithful field names; secrets given placeholder defaults so import works in Phase 1):

```python
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "prod"] = "local"

    DATABASE_URL: str = "sqlite:///./app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 30

    TELEGRAM_API_ID: int = 0
    TELEGRAM_API_HASH: SecretStr = SecretStr("")
    TELETHON_STRING_SESSION: SecretStr = SecretStr("")
    TELEGRAM_BOT_TOKEN: SecretStr = SecretStr("")
    TELEGRAM_CHANNEL_ID: int = 0

    ALLOWED_LANGUAGES: list[str] = ["uk", "ru", "en"]
    DEDUP_TTL_SECONDS: int = 604800
    KEYWORD_MATCH_MODE: Literal["any", "all"] = "any"
    POST_MAX_LEN: int = 4096


settings = Settings()
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_config.py -q
```
Expected: 3 passed.

- [ ] Commit:
```bash
git add app/core/config.py tests/test_config.py
git commit -m "feat: add Settings with contract field names and sqlite DATABASE_URL default

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.3: DB engine + SessionLocal + get_db

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/core/db.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_db.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_db.py`:

```python
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, engine, get_db


def test_engine_uses_settings_database_url():
    assert str(engine.url).startswith("sqlite")


def test_get_db_yields_a_session():
    gen = get_db()
    s = next(gen)
    assert isinstance(s, Session)
    assert s.execute(text("select 1")).scalar() == 1
    gen.close()


def test_session_local_creates_session():
    with SessionLocal() as s:
        assert isinstance(s, Session)
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_db.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.core.db'`.

- [ ] Implement `app/core/db.py` (per contract §DB):

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as s:
        yield s
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_db.py -q
```
Expected: 3 passed.

- [ ] Commit:
```bash
git add app/core/db.py tests/test_db.py
git commit -m "feat: add engine, SessionLocal, and get_db dependency

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.4: Base — DeclarativeBase + naming convention + enums

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/base.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_models_base.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_models_base.py`:

```python
from app.models.base import (
    NAMING_CONVENTION,
    Base,
    ErrorStage,
    PostStatus,
    SourceType,
)


def test_naming_convention_keys():
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}
    assert NAMING_CONVENTION["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert NAMING_CONVENTION["fk"] == (
        "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    )
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"


def test_base_metadata_carries_naming_convention():
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_source_type_enum_values():
    assert SourceType.site.value == "site"
    assert SourceType.tg.value == "tg"


def test_post_status_enum_values():
    assert [s.value for s in PostStatus] == [
        "new",
        "generated",
        "published",
        "failed",
    ]


def test_error_stage_enum_values():
    assert [s.value for s in ErrorStage] == ["parse", "generate", "publish"]
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_models_base.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.base'`.

- [ ] Implement `app/models/base.py` (exact per contract §Base / §Enums):

```python
import enum

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class SourceType(str, enum.Enum):
    site = "site"
    tg = "tg"


class PostStatus(str, enum.Enum):
    new = "new"
    generated = "generated"
    published = "published"
    failed = "failed"


class ErrorStage(str, enum.Enum):
    parse = "parse"
    generate = "generate"
    publish = "publish"
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_models_base.py -q
```
Expected: 5 passed.

- [ ] Commit:
```bash
git add app/models/base.py tests/test_models_base.py
git commit -m "feat: add DeclarativeBase, naming convention, and domain enums

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.5: Source model

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/source.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/conftest.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_model_source.py`

> The `conftest.py` here provides the function-scoped in-memory SQLite session fixture that all model tasks (P1.5–P1.9) reuse, per spec §11 / contracts §Tests.

Steps:
- [ ] (TDD) Write `tests/conftest.py` (test DB = in-memory SQLite, tables created from registered metadata):

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  ensures all models register on Base.metadata
from app.models.base import Base


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(engine, expire_on_commit=False, class_=Session)
    with TestSession() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()
```

- [ ] (TDD) Write failing test `tests/test_model_source.py`:

```python
import uuid
from datetime import datetime, timezone

from app.models.base import SourceType
from app.models.source import Source


def test_create_source_row(db):
    src = Source(type=SourceType.tg, name="AI News", url="@ainews", enabled=True)
    db.add(src)
    db.commit()
    db.refresh(src)

    assert isinstance(src.id, uuid.UUID)
    assert src.type is SourceType.tg
    assert src.enabled is True
    assert src.last_seen_msg_id is None
    assert src.etag is None
    assert src.modified is None
    assert src.created_at.tzinfo is not None
    assert src.created_at.utcoffset() == timezone.utc.utcoffset(datetime.now())


def test_source_type_enum_round_trip(db):
    src = Source(type=SourceType.site, name="Blog", url="https://blog.example")
    db.add(src)
    db.commit()
    fetched = db.get(Source, src.id)
    assert fetched.type is SourceType.site


def test_source_enabled_defaults_true(db):
    src = Source(type=SourceType.site, name="Blog", url="https://blog.example")
    db.add(src)
    db.commit()
    db.refresh(src)
    assert src.enabled is True
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_model_source.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.source'`.

- [ ] Implement `app/models/source.py` (exact fields per contract §Models):

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SourceType


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    type: Mapped[SourceType]
    name: Mapped[str]
    url: Mapped[str]
    enabled: Mapped[bool] = mapped_column(default=True)
    last_seen_msg_id: Mapped[int | None]
    etag: Mapped[str | None]
    modified: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_model_source.py -q
```
Expected: 3 passed.

- [ ] Commit:
```bash
git add app/models/source.py tests/conftest.py tests/test_model_source.py
git commit -m "feat: add Source model and test DB session fixture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.6: Keyword model (word unique)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/keyword.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_model_keyword.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_model_keyword.py`:

```python
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.keyword import Keyword


def test_create_keyword_row(db):
    kw = Keyword(word="нейромережа", lang="uk")
    db.add(kw)
    db.commit()
    db.refresh(kw)
    assert isinstance(kw.id, uuid.UUID)
    assert kw.word == "нейромережа"
    assert kw.lang == "uk"


def test_keyword_lang_optional(db):
    kw = Keyword(word="ai")
    db.add(kw)
    db.commit()
    db.refresh(kw)
    assert kw.lang is None


def test_keyword_word_unique_rejects_duplicate(db):
    db.add(Keyword(word="gpt"))
    db.commit()
    db.add(Keyword(word="gpt"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_model_keyword.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.keyword'`.

- [ ] Implement `app/models/keyword.py`:

```python
import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    word: Mapped[str] = mapped_column(unique=True)
    lang: Mapped[str | None]
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_model_keyword.py -q
```
Expected: 3 passed.

- [ ] Commit:
```bash
git add app/models/keyword.py tests/test_model_keyword.py
git commit -m "feat: add Keyword model with unique word constraint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.7: NewsItem model (content_hash unique)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/news_item.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_model_news_item.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_model_news_item.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.news_item import NewsItem


def _item(**kw):
    base = {
        "title": "Big AI release",
        "url": "https://example.com/a",
        "summary": "summary",
        "source": "Example",
        "published_at": datetime(2026, 6, 8, tzinfo=timezone.utc),
        "raw_text": "raw",
        "content_hash": "h1",
    }
    base.update(kw)
    return NewsItem(**base)


def test_create_news_item_row(db):
    item = _item()
    db.add(item)
    db.commit()
    db.refresh(item)
    assert isinstance(item.id, uuid.UUID)
    assert item.content_hash == "h1"
    assert item.created_at.tzinfo is not None


def test_news_item_optional_fields_nullable(db):
    item = _item(url=None, summary=None, raw_text=None, content_hash="h2")
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.url is None
    assert item.summary is None
    assert item.raw_text is None


def test_content_hash_unique_rejects_duplicate(db):
    db.add(_item(content_hash="dup"))
    db.commit()
    db.add(_item(url="https://example.com/b", content_hash="dup"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_model_news_item.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.news_item'`.

- [ ] Implement `app/models/news_item.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str]
    url: Mapped[str | None]
    summary: Mapped[str | None]
    source: Mapped[str]
    published_at: Mapped[datetime]
    raw_text: Mapped[str | None]
    content_hash: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_model_news_item.py -q
```
Expected: 3 passed.

- [ ] Commit:
```bash
git add app/models/news_item.py tests/test_model_news_item.py
git commit -m "feat: add NewsItem model with unique content_hash

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.8: Post model (FK news_id → news_items.id, status default new)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/post.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_model_post.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_model_post.py`:

```python
import uuid
from datetime import datetime, timezone

from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post


def _news(db):
    item = NewsItem(
        title="t",
        url="https://example.com",
        summary=None,
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        raw_text=None,
        content_hash=uuid.uuid4().hex,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_create_post_row_defaults_status_new(db):
    news = _news(db)
    post = Post(news_id=news.id, generated_text="hello")
    db.add(post)
    db.commit()
    db.refresh(post)
    assert isinstance(post.id, uuid.UUID)
    assert post.status is PostStatus.new
    assert post.published_at is None
    assert post.tg_message_id is None
    assert post.error is None
    assert post.created_at.tzinfo is not None


def test_post_status_enum_round_trip(db):
    news = _news(db)
    post = Post(
        news_id=news.id, generated_text="x", status=PostStatus.published
    )
    db.add(post)
    db.commit()
    fetched = db.get(Post, post.id)
    assert fetched.status is PostStatus.published


def test_post_news_relationship(db):
    news = _news(db)
    post = Post(news_id=news.id, generated_text="x")
    db.add(post)
    db.commit()
    db.refresh(post)
    assert post.news is not None
    assert post.news.id == news.id
    assert post in news.posts
```

- [ ] Run it — expect FAIL:
```bash
uv run pytest tests/test_model_post.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.post'`.

- [ ] Implement `app/models/post.py` (FK to `news_items.id`; relationship both directions; status default `new`):

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PostStatus
from app.models.news_item import NewsItem


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    news_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_items.id"))
    generated_text: Mapped[str]
    status: Mapped[PostStatus] = mapped_column(default=PostStatus.new)
    published_at: Mapped[datetime | None]
    tg_message_id: Mapped[int | None]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    news: Mapped[NewsItem] = relationship(back_populates="posts")
```

- [ ] Add the reverse relationship to `NewsItem` (surgical edit — append after `created_at`):
  - In `app/models/news_item.py`, add the import `from sqlalchemy.orm import Mapped, mapped_column, relationship` (extend existing import) and the line:
```python
    posts: Mapped[list["Post"]] = relationship(back_populates="news")
```
  - With a `TYPE_CHECKING` import for `Post` to avoid a circular import at module load:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.post import Post
```
  Final `app/models/news_item.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.post import Post


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str]
    url: Mapped[str | None]
    summary: Mapped[str | None]
    source: Mapped[str]
    published_at: Mapped[datetime]
    raw_text: Mapped[str | None]
    content_hash: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    posts: Mapped[list["Post"]] = relationship(back_populates="news")
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_model_post.py tests/test_model_news_item.py -q
```
Expected: 6 passed.

- [ ] Commit:
```bash
git add app/models/post.py app/models/news_item.py tests/test_model_post.py
git commit -m "feat: add Post model with FK to NewsItem and bidirectional relationship

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.9: ErrorLog model + model registry (`app/models/__init__.py`)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/app/models/error_log.py`
- Modify: `/home/jarvis/Programming/ai-post-generated-bot/app/models/__init__.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_model_error_log.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_models_registry.py`

Steps:
- [ ] (TDD) Write failing test `tests/test_model_error_log.py`:

```python
import uuid
from datetime import datetime, timezone

from app.models.base import ErrorStage
from app.models.error_log import ErrorLog


def test_create_error_log_row(db):
    log = ErrorLog(stage=ErrorStage.generate, message="boom")
    db.add(log)
    db.commit()
    db.refresh(log)
    assert isinstance(log.id, uuid.UUID)
    assert log.stage is ErrorStage.generate
    assert log.message == "boom"
    assert log.source_id is None
    assert log.news_id is None
    assert log.post_id is None
    assert log.traceback is None
    assert log.created_at.tzinfo is not None


def test_error_log_stage_enum_round_trip(db):
    log = ErrorLog(
        stage=ErrorStage.publish,
        message="m",
        post_id=uuid.uuid4(),
        traceback="Traceback...",
    )
    db.add(log)
    db.commit()
    fetched = db.get(ErrorLog, log.id)
    assert fetched.stage is ErrorStage.publish
    assert fetched.traceback == "Traceback..."


def test_error_log_created_at_is_utc(db):
    log = ErrorLog(stage=ErrorStage.parse, message="m")
    db.add(log)
    db.commit()
    db.refresh(log)
    assert log.created_at.utcoffset() == timezone.utc.utcoffset(
        datetime.now()
    )
```

- [ ] (TDD) Write failing test `tests/test_models_registry.py` (every table registered on `Base.metadata` via the package):

```python
import app.models  # noqa: F401
from app.models.base import Base


def test_all_tables_registered():
    tables = set(Base.metadata.tables)
    assert tables == {
        "sources",
        "keywords",
        "news_items",
        "posts",
        "error_logs",
    }


def test_post_fk_targets_news_items():
    post = Base.metadata.tables["posts"]
    fks = list(post.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "news_items"
    assert fks[0].column.name == "id"


def test_fk_constraint_name_follows_convention():
    post = Base.metadata.tables["posts"]
    fk_names = {fk.constraint.name for fk in post.foreign_keys}
    assert "fk_posts_news_id_news_items" in fk_names
```

- [ ] Run both — expect FAIL:
```bash
uv run pytest tests/test_model_error_log.py tests/test_models_registry.py -q
```
Expected: `ModuleNotFoundError: No module named 'app.models.error_log'` (and registry test fails: `error_logs` not yet in metadata).

- [ ] Implement `app/models/error_log.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ErrorStage


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    stage: Mapped[ErrorStage]
    source_id: Mapped[uuid.UUID | None]
    news_id: Mapped[uuid.UUID | None]
    post_id: Mapped[uuid.UUID | None]
    message: Mapped[str]
    traceback: Mapped[str | None]
```

- [ ] Implement the registry `app/models/__init__.py` (importing every model registers it on `Base.metadata`; re-export for convenience):

```python
from app.models.base import (
    Base,
    ErrorStage,
    PostStatus,
    SourceType,
)
from app.models.error_log import ErrorLog
from app.models.keyword import Keyword
from app.models.news_item import NewsItem
from app.models.post import Post
from app.models.source import Source

__all__ = [
    "Base",
    "SourceType",
    "PostStatus",
    "ErrorStage",
    "Source",
    "Keyword",
    "NewsItem",
    "Post",
    "ErrorLog",
]
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_model_error_log.py tests/test_models_registry.py -q
```
Expected: 6 passed.

- [ ] Run the full model suite to confirm no regressions:
```bash
uv run pytest -q
```
Expected: all passed.

- [ ] Commit:
```bash
git add app/models/error_log.py app/models/__init__.py tests/test_model_error_log.py tests/test_models_registry.py
git commit -m "feat: add ErrorLog model and register all models on Base.metadata

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.10: Alembic init + env.py wired to Base.metadata, settings.DATABASE_URL, compare_type, file_template

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic.ini`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic/env.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic/script.py.mako`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic/README`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic/versions/.gitkeep`

> Generate the scaffold with `uv run alembic init`, then replace the generated `env.py` and edit `alembic.ini` so the migration env points at our `Base.metadata` and `settings.DATABASE_URL`, with `compare_type=True` and a slugged `file_template`.

Steps:
- [ ] Generate the Alembic scaffold:
```bash
uv run alembic init alembic
```
- [ ] In `alembic.ini`, set the slugged filename template (find the commented `# file_template` line and replace/add an active one). Set:
```ini
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
```
  And leave `sqlalchemy.url` empty/placeholder (env.py overrides it from settings). The relevant line stays:
```ini
sqlalchemy.url =
```
- [ ] Replace the generated `alembic/env.py` entirely with (offline + online, target_metadata = our Base, url + compare_type from settings):

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.models import Base  # noqa: F401  triggers model registration

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

> `render_as_batch=True` is included because the prod/local split runs on SQLite locally; batch mode keeps future ALTERs portable. `compare_type=True` per the task requirement.

- [ ] Ensure the versions dir is tracked: create empty `alembic/versions/.gitkeep`.
- [ ] Verify Alembic config loads and resolves our metadata (no migrations yet — should report DB not up to date / empty history cleanly):
```bash
uv run alembic check || true
uv run alembic heads
```
Expected: `alembic heads` prints nothing (no revisions yet) and no import/config error; the command exits 0.
- [ ] Verify env import wiring with a direct config check:
```bash
uv run python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config('alembic.ini'); print('ok', ScriptDirectory.from_config(c).dir)"
```
Expected: prints `ok <abs path>/alembic`.
- [ ] Commit:
```bash
git add alembic.ini alembic/env.py alembic/script.py.mako alembic/README alembic/versions/.gitkeep
git commit -m "chore: scaffold Alembic wired to Base.metadata, settings, compare_type, slug template

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P1.11: First migration — autogenerate then review (creates all 5 tables)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/alembic/versions/<slug>_initial_schema.py` (generated)
- Create: `/home/jarvis/Programming/ai-post-generated-bot/tests/test_migration_initial.py`

Steps:
- [ ] Autogenerate the initial migration against a throwaway SQLite URL (so it diffs the full empty DB → all tables):
```bash
DATABASE_URL="sqlite:///./_autogen.db" uv run alembic revision --autogenerate -m "initial schema"
```
Expected: a new file appears under `alembic/versions/` named like `2026_06_08_HHMM-<rev>_initial_schema.py`.
- [ ] REVIEW the generated migration and confirm it contains `op.create_table` for all five tables: `sources`, `keywords`, `news_items`, `posts`, `error_logs`. Verify:
  - `posts` has a FK named `fk_posts_news_id_news_items` to `news_items.id` (naming convention applied).
  - `keywords.word` and `news_items.content_hash` carry unique constraints named `uq_keywords_word` / `uq_news_items_content_hash`.
  - Enum columns render as `sa.Enum(...)` (or `sa.Enum` with the member values) for `type`, `status`, `stage`.
  - Order: `news_items` is created before `posts` (FK dependency). If autogenerate ordered them wrong, reorder the `create_table` calls so the referenced table comes first; fix `downgrade` to drop in reverse.
  Remove any stray autogenerate comments/`# ### end Alembic commands ###` is fine to keep.
- [ ] Delete the throwaway autogen DB:
```bash
rm -f _autogen.db
```
- [ ] (TDD) Write `tests/test_migration_initial.py` — applies the migration to a fresh SQLite file and asserts the schema matches the model metadata:

```python
import pathlib

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.models import Base


def _alembic_config(db_url: str) -> Config:
    root = pathlib.Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_creates_all_tables(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    engine.dispose()


def test_migration_creates_post_fk_to_news_items(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    fks = insp.get_foreign_keys("posts")
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "news_items"
    assert fks[0]["referred_columns"] == ["id"]
    engine.dispose()


def test_migration_unique_constraints_present(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    kw_uniques = {
        tuple(uc["column_names"])
        for uc in insp.get_unique_constraints("keywords")
    }
    news_uniques = {
        tuple(uc["column_names"])
        for uc in insp.get_unique_constraints("news_items")
    }
    assert ("word",) in kw_uniques
    assert ("content_hash",) in news_uniques
    engine.dispose()
```

- [ ] Run — expect PASS:
```bash
uv run pytest tests/test_migration_initial.py -q
```
Expected: 3 passed. If `test_migration_creates_all_tables` fails on table ordering, fix the migration's `create_table` order (Task review step) and re-run.
- [ ] Run the entire suite to confirm the whole data layer is green:
```bash
uv run pytest -q
```
Expected: all passed.
- [ ] Sanity-check downgrade works (drops cleanly):
```bash
uv run alembic upgrade head && uv run alembic downgrade base && rm -f app.db
```
Expected: both commands exit 0.
- [ ] Commit:
```bash
git add alembic/versions/ tests/test_migration_initial.py
git commit -m "feat: add initial Alembic migration creating all data-layer tables

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---


## Phase 2 — REST API (CRUD under /api/v1)

### Task P2.1: Schema base — APIModel and Page[T] envelope

**Files:**
- Create: `app/schemas/base.py`
- Create: `app/schemas/common.py`
- Test: `tests/api/test_schemas_base.py`

Steps:
- [ ] Write failing test `tests/api/test_schemas_base.py`:
```python
from datetime import datetime, timezone
from app.schemas.base import APIModel
from app.schemas.common import Page


class _Sample(APIModel):
    name: str
    when: datetime


class _Obj:
    name = "abc"
    when = datetime(2026, 6, 8, tzinfo=timezone.utc)


def test_apimodel_reads_from_attributes():
    obj = _Obj()
    out = _Sample.model_validate(obj)
    assert out.name == "abc"
    assert out.when == datetime(2026, 6, 8, tzinfo=timezone.utc)


def test_page_generic_envelope():
    page = Page[_Sample](data=[_Sample(name="x", when=_Obj.when)], count=1)
    dumped = page.model_dump()
    assert dumped["count"] == 1
    assert dumped["data"][0]["name"] == "x"
```
- [ ] Run it — expected FAIL (ModuleNotFoundError: app.schemas.base):
```
uv run pytest tests/api/test_schemas_base.py -q
```
- [ ] Create `app/schemas/base.py`:
```python
from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```
- [ ] Create `app/schemas/common.py`:
```python
from typing import Generic, TypeVar

from app.schemas.base import APIModel

T = TypeVar("T")


class Page(APIModel, Generic[T]):
    data: list[T]
    count: int
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_schemas_base.py -q
```
- [ ] Commit:
```
git add app/schemas/base.py app/schemas/common.py tests/api/test_schemas_base.py
git commit -m "feat: add APIModel base and Page[T] list envelope schemas"
```

### Task P2.2: Resource schemas — Source, Keyword, Post, ErrorLog, Generate

**Files:**
- Create: `app/schemas/source.py`
- Create: `app/schemas/keyword.py`
- Create: `app/schemas/post.py`
- Create: `app/schemas/error_log.py`
- Create: `app/schemas/generate.py`
- Test: `tests/api/test_schemas_resources.py`

Steps:
- [ ] Write failing test `tests/api/test_schemas_resources.py`:
```python
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.base import ErrorStage, PostStatus, SourceType
from app.schemas.error_log import ErrorLogRead
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.schemas.keyword import KeywordCreate, KeywordRead, KeywordUpdate
from app.schemas.post import PostRead
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate


def test_source_create_defaults_enabled_true():
    sc = SourceCreate(type=SourceType.site, name="N", url="https://x")
    assert sc.enabled is True


def test_source_update_all_optional():
    su = SourceUpdate()
    assert su.model_dump(exclude_unset=True) == {}


def test_source_read_has_no_server_secret_fields():
    fields = set(SourceRead.model_fields)
    assert fields == {"id", "type", "name", "url", "enabled", "created_at"}
    # last_seen_msg_id / etag / modified are server-internal and not exposed
    assert "etag" not in fields
    assert "last_seen_msg_id" not in fields


def test_keyword_create_default_lang_none():
    kc = KeywordCreate(word="ai")
    assert kc.lang is None


def test_keyword_read_fields():
    assert set(KeywordRead.model_fields) == {"id", "word", "lang"}


def test_post_read_fields():
    assert set(PostRead.model_fields) == {
        "id",
        "news_id",
        "generated_text",
        "status",
        "published_at",
        "tg_message_id",
        "error",
        "created_at",
    }


def test_error_log_read_fields():
    assert set(ErrorLogRead.model_fields) == {
        "id",
        "created_at",
        "stage",
        "source_id",
        "news_id",
        "post_id",
        "message",
    }


def test_generate_request_defaults_none():
    gr = GenerateRequest()
    assert gr.news_id is None
    assert gr.text is None


def test_generate_response_shape():
    pid = uuid.uuid4()
    resp = GenerateResponse(task_id="t-1", post_id=pid)
    assert resp.task_id == "t-1"
    assert resp.post_id == pid


def test_post_read_from_orm_like_object():
    class _P:
        id = uuid.uuid4()
        news_id = uuid.uuid4()
        generated_text = "hi"
        status = PostStatus.generated
        published_at = None
        tg_message_id = None
        error = None
        created_at = datetime.now(timezone.utc)

    read = PostRead.model_validate(_P())
    assert read.status == PostStatus.generated


def test_error_stage_enum_roundtrips():
    class _E:
        id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)
        stage = ErrorStage.publish
        source_id = None
        news_id = None
        post_id = None
        message = "boom"

    read = ErrorLogRead.model_validate(_E())
    assert read.stage == ErrorStage.publish
```
- [ ] Run it — expected FAIL (ModuleNotFoundError: app.schemas.source):
```
uv run pytest tests/api/test_schemas_resources.py -q
```
- [ ] Create `app/schemas/source.py`:
```python
import uuid
from datetime import datetime

from app.models.base import SourceType
from app.schemas.base import APIModel


class SourceCreate(APIModel):
    type: SourceType
    name: str
    url: str
    enabled: bool = True


class SourceUpdate(APIModel):
    type: SourceType | None = None
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


class SourceRead(APIModel):
    id: uuid.UUID
    type: SourceType
    name: str
    url: str
    enabled: bool
    created_at: datetime
```
- [ ] Create `app/schemas/keyword.py`:
```python
import uuid

from app.schemas.base import APIModel


class KeywordCreate(APIModel):
    word: str
    lang: str | None = None


class KeywordUpdate(APIModel):
    word: str | None = None
    lang: str | None = None


class KeywordRead(APIModel):
    id: uuid.UUID
    word: str
    lang: str | None
```
- [ ] Create `app/schemas/post.py`:
```python
import uuid
from datetime import datetime

from app.models.base import PostStatus
from app.schemas.base import APIModel


class PostRead(APIModel):
    id: uuid.UUID
    news_id: uuid.UUID
    generated_text: str
    status: PostStatus
    published_at: datetime | None
    tg_message_id: int | None
    error: str | None
    created_at: datetime
```
- [ ] Create `app/schemas/error_log.py`:
```python
import uuid
from datetime import datetime

from app.models.base import ErrorStage
from app.schemas.base import APIModel


class ErrorLogRead(APIModel):
    id: uuid.UUID
    created_at: datetime
    stage: ErrorStage
    source_id: uuid.UUID | None
    news_id: uuid.UUID | None
    post_id: uuid.UUID | None
    message: str
```
- [ ] Create `app/schemas/generate.py`:
```python
import uuid

from app.schemas.base import APIModel


class GenerateRequest(APIModel):
    news_id: uuid.UUID | None = None
    text: str | None = None


class GenerateResponse(APIModel):
    task_id: str
    post_id: uuid.UUID | None = None
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_schemas_resources.py -q
```
- [ ] Commit:
```
git add app/schemas/source.py app/schemas/keyword.py app/schemas/post.py app/schemas/error_log.py app/schemas/generate.py tests/api/test_schemas_resources.py
git commit -m "feat: add Source/Keyword/Post/ErrorLog/Generate API schemas"
```

### Task P2.3: API deps — SessionDep, pagination, fetch-or-404

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/v1/__init__.py`
- Create: `app/api/v1/routers/__init__.py`
- Create: `app/api/v1/deps.py`
- Test: `tests/api/test_deps.py`

Steps:
- [ ] Create empty package markers `app/api/__init__.py`, `app/api/v1/__init__.py`, `app/api/v1/routers/__init__.py` (each empty file).
- [ ] Write failing test `tests/api/test_deps.py`:
```python
import uuid

import pytest
from fastapi import HTTPException

from app.api.v1.deps import Pagination, get_post_or_404, get_source_or_404
from app.models.post import Post
from app.models.source import Source
from app.models.base import SourceType


def test_pagination_defaults():
    p = Pagination()
    assert p.limit == 20
    assert p.offset == 0


def test_pagination_caps_limit():
    p = Pagination(limit=100, offset=5)
    assert p.limit == 100
    assert p.offset == 5


def test_get_source_or_404_found(db_session):
    src = Source(type=SourceType.site, name="N", url="https://x")
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)
    got = get_source_or_404(src.id, db_session)
    assert got.id == src.id


def test_get_source_or_404_missing(db_session):
    with pytest.raises(HTTPException) as exc:
        get_source_or_404(uuid.uuid4(), db_session)
    assert exc.value.status_code == 404


def test_get_post_or_404_missing(db_session):
    with pytest.raises(HTTPException) as exc:
        get_post_or_404(uuid.uuid4(), db_session)
    assert exc.value.status_code == 404
```
- [ ] Run it — expected FAIL (ModuleNotFoundError: app.api.v1.deps):
```
uv run pytest tests/api/test_deps.py -q
```
- [ ] Create `app/api/v1/deps.py`:
```python
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.post import Post
from app.models.source import Source

SessionDep = Annotated[Session, Depends(get_db)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def get_source_or_404(source_id: uuid.UUID, db: SessionDep) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


def get_post_or_404(post_id: uuid.UUID, db: SessionDep) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_deps.py -q
```
- [ ] Commit:
```
git add app/api/__init__.py app/api/v1/__init__.py app/api/v1/routers/__init__.py app/api/v1/deps.py tests/api/test_deps.py
git commit -m "feat: add API v1 deps (SessionDep, Pagination, fetch-or-404)"
```

### Task P2.4: Sources router — full CRUD

**Files:**
- Create: `app/api/v1/routers/sources.py`
- Create: `app/api/v1/router.py`
- Modify: `app/main.py`
- Test: `tests/api/test_sources.py`

Steps:
- [ ] Write failing test `tests/api/test_sources.py`:
```python
def test_create_source_201(client):
    resp = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "Example", "url": "https://example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Example"
    assert body["type"] == "site"
    assert body["enabled"] is True
    assert "id" in body and "created_at" in body
    # Read schema must NOT leak server-internal fields
    assert "etag" not in body
    assert "last_seen_msg_id" not in body


def test_list_sources_envelope(client):
    client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "A", "url": "https://a"},
    )
    client.post(
        "/api/v1/sources",
        json={"type": "tg", "name": "B", "url": "@b"},
    )
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["data"]) == 2


def test_get_source_by_id(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "G", "url": "https://g"},
    ).json()
    resp = client.get(f"/api/v1/sources/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_source_404(client):
    import uuid

    resp = client.get(f"/api/v1/sources/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_update_source_patch(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "Old", "url": "https://old"},
    ).json()
    resp = client.patch(
        f"/api/v1/sources/{created['id']}",
        json={"name": "New", "enabled": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New"
    assert body["enabled"] is False
    assert body["url"] == "https://old"


def test_delete_source_204(client):
    created = client.post(
        "/api/v1/sources",
        json={"type": "site", "name": "D", "url": "https://d"},
    ).json()
    resp = client.delete(f"/api/v1/sources/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/sources/{created['id']}").status_code == 404
```
- [ ] Run it — expected FAIL (404 on routes / ImportError, routes not wired):
```
uv run pytest tests/api/test_sources.py -q
```
- [ ] Create `app/api/v1/routers/sources.py`:
```python
import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.v1.deps import PaginationDep, SessionDep, get_source_or_404
from app.models.source import Source
from app.schemas.common import Page
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=Page[SourceRead])
def list_sources(db: SessionDep, pagination: PaginationDep) -> Page[SourceRead]:
    count = db.scalar(select(Source).with_only_columns(Source.id).order_by(None).count()) if False else None
    total = len(db.scalars(select(Source)).all())
    rows = db.scalars(
        select(Source).order_by(Source.created_at).offset(pagination.offset).limit(pagination.limit)
    ).all()
    return Page[SourceRead](data=rows, count=total)


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: SessionDep) -> Source:
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source: Source = None, *, db: SessionDep, source_id: uuid.UUID) -> Source:
    return get_source_or_404(source_id, db)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(source_id: uuid.UUID, payload: SourceUpdate, db: SessionDep) -> Source:
    source = get_source_or_404(source_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, db: SessionDep) -> None:
    source = get_source_or_404(source_id, db)
    db.delete(source)
    db.commit()
```

> Note for implementer: simplify `list_sources` to use `func.count()` and `get_source` to a plain signature — the cleaned form is below; use it verbatim instead of the sketch above:

```python
import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep, get_source_or_404
from app.models.source import Source
from app.schemas.common import Page
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=Page[SourceRead])
def list_sources(db: SessionDep, pagination: PaginationDep) -> Page[SourceRead]:
    total = db.scalar(select(func.count()).select_from(Source))
    rows = db.scalars(
        select(Source)
        .order_by(Source.created_at)
        .offset(pagination.offset)
        .limit(pagination.limit)
    ).all()
    return Page[SourceRead](data=rows, count=total or 0)


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, db: SessionDep) -> Source:
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, db: SessionDep) -> Source:
    return get_source_or_404(source_id, db)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(source_id: uuid.UUID, payload: SourceUpdate, db: SessionDep) -> Source:
    source = get_source_or_404(source_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, db: SessionDep) -> None:
    source = get_source_or_404(source_id, db)
    db.delete(source)
    db.commit()
```
- [ ] Create `app/api/v1/router.py` (aggregator; keywords/posts/generate/errors added in later tasks):
```python
from fastapi import APIRouter

from app.api.v1.routers import sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
```
- [ ] Modify `app/main.py` to wire the v1 aggregator under `/api/v1` (add the import and include_router; keep existing `/health` wiring intact):
```python
from app.api.v1.router import api_v1_router

app.include_router(api_v1_router, prefix="/api/v1")
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_sources.py -q
```
- [ ] Commit:
```
git add app/api/v1/routers/sources.py app/api/v1/router.py app/main.py tests/api/test_sources.py
git commit -m "feat: add sources CRUD router under /api/v1"
```

### Task P2.5: Keywords router — full CRUD

**Files:**
- Create: `app/api/v1/routers/keywords.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/api/test_keywords.py`

Steps:
- [ ] Write failing test `tests/api/test_keywords.py`:
```python
import uuid


def test_create_keyword_201(client):
    resp = client.post("/api/v1/keywords", json={"word": "ai", "lang": "en"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["word"] == "ai"
    assert body["lang"] == "en"
    assert set(body.keys()) == {"id", "word", "lang"}


def test_create_keyword_default_lang_null(client):
    resp = client.post("/api/v1/keywords", json={"word": "робот"})
    assert resp.status_code == 201
    assert resp.json()["lang"] is None


def test_list_keywords_envelope(client):
    client.post("/api/v1/keywords", json={"word": "a"})
    client.post("/api/v1/keywords", json={"word": "b"})
    resp = client.get("/api/v1/keywords")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["data"]) == 2


def test_update_keyword_patch(client):
    created = client.post("/api/v1/keywords", json={"word": "old"}).json()
    resp = client.patch(f"/api/v1/keywords/{created['id']}", json={"word": "new"})
    assert resp.status_code == 200
    assert resp.json()["word"] == "new"


def test_get_keyword_404(client):
    resp = client.get(f"/api/v1/keywords/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_keyword_204(client):
    created = client.post("/api/v1/keywords", json={"word": "del"}).json()
    resp = client.delete(f"/api/v1/keywords/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/keywords/{created['id']}").status_code == 404
```
- [ ] Run it — expected FAIL (404 on routes / not wired):
```
uv run pytest tests/api/test_keywords.py -q
```
- [ ] Create `app/api/v1/routers/keywords.py` (keywords have no dedicated fetch-or-404 dep per contract → inline 404):
```python
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.keyword import Keyword
from app.schemas.common import Page
from app.schemas.keyword import KeywordCreate, KeywordRead, KeywordUpdate

router = APIRouter(prefix="/keywords", tags=["keywords"])


def _get_or_404(keyword_id: uuid.UUID, db: SessionDep) -> Keyword:
    keyword = db.get(Keyword, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return keyword


@router.get("", response_model=Page[KeywordRead])
def list_keywords(db: SessionDep, pagination: PaginationDep) -> Page[KeywordRead]:
    total = db.scalar(select(func.count()).select_from(Keyword))
    rows = db.scalars(
        select(Keyword).order_by(Keyword.word).offset(pagination.offset).limit(pagination.limit)
    ).all()
    return Page[KeywordRead](data=rows, count=total or 0)


@router.post("", response_model=KeywordRead, status_code=status.HTTP_201_CREATED)
def create_keyword(payload: KeywordCreate, db: SessionDep) -> Keyword:
    keyword = Keyword(**payload.model_dump())
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword


@router.get("/{keyword_id}", response_model=KeywordRead)
def get_keyword(keyword_id: uuid.UUID, db: SessionDep) -> Keyword:
    return _get_or_404(keyword_id, db)


@router.patch("/{keyword_id}", response_model=KeywordRead)
def update_keyword(keyword_id: uuid.UUID, payload: KeywordUpdate, db: SessionDep) -> Keyword:
    keyword = _get_or_404(keyword_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(keyword, field, value)
    db.commit()
    db.refresh(keyword)
    return keyword


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword(keyword_id: uuid.UUID, db: SessionDep) -> None:
    keyword = _get_or_404(keyword_id, db)
    db.delete(keyword)
    db.commit()
```
- [ ] Modify `app/api/v1/router.py` to include keywords:
```python
from fastapi import APIRouter

from app.api.v1.routers import keywords, sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
api_v1_router.include_router(keywords.router)
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_keywords.py -q
```
- [ ] Commit:
```
git add app/api/v1/routers/keywords.py app/api/v1/router.py tests/api/test_keywords.py
git commit -m "feat: add keywords CRUD router under /api/v1"
```

### Task P2.6: Posts router — list with pagination envelope + status filter

**Files:**
- Create: `app/api/v1/routers/posts.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/api/test_posts.py`

Steps:
- [ ] Write failing test `tests/api/test_posts.py` (seeds NewsItem + Posts directly via `db_session`):
```python
import uuid
from datetime import datetime, timezone

from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post


def _seed_news(db):
    news = NewsItem(
        title="T",
        url="https://n",
        summary="s",
        source="src",
        published_at=datetime.now(timezone.utc),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_list_posts_envelope(client, db_session):
    news = _seed_news(db_session)
    for st in (PostStatus.generated, PostStatus.published, PostStatus.failed):
        db_session.add(Post(news_id=news.id, generated_text="x", status=st))
    db_session.commit()

    resp = client.get("/api/v1/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "count"}
    assert body["count"] == 3
    assert len(body["data"]) == 3
    assert "news_id" in body["data"][0]


def test_list_posts_status_filter(client, db_session):
    news = _seed_news(db_session)
    db_session.add(Post(news_id=news.id, generated_text="a", status=PostStatus.failed))
    db_session.add(Post(news_id=news.id, generated_text="b", status=PostStatus.published))
    db_session.commit()

    resp = client.get("/api/v1/posts", params={"status": "failed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["data"][0]["status"] == "failed"


def test_list_posts_pagination_limit_offset(client, db_session):
    news = _seed_news(db_session)
    for _ in range(5):
        db_session.add(Post(news_id=news.id, generated_text="p", status=PostStatus.new))
    db_session.commit()

    resp = client.get("/api/v1/posts", params={"limit": 2, "offset": 0})
    body = resp.json()
    assert body["count"] == 5
    assert len(body["data"]) == 2


def test_list_posts_limit_over_cap_422(client):
    resp = client.get("/api/v1/posts", params={"limit": 1000})
    assert resp.status_code == 422
```
- [ ] Run it — expected FAIL (404 on /api/v1/posts):
```
uv run pytest tests/api/test_posts.py -q
```
- [ ] Create `app/api/v1/routers/posts.py`:
```python
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.base import PostStatus
from app.models.post import Post
from app.schemas.common import Page
from app.schemas.post import PostRead

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=Page[PostRead])
def list_posts(
    db: SessionDep,
    pagination: PaginationDep,
    status: PostStatus | None = None,
) -> Page[PostRead]:
    count_stmt = select(func.count()).select_from(Post)
    rows_stmt = select(Post).order_by(Post.created_at.desc())
    if status is not None:
        count_stmt = count_stmt.where(Post.status == status)
        rows_stmt = rows_stmt.where(Post.status == status)
    total = db.scalar(count_stmt)
    rows = db.scalars(
        rows_stmt.offset(pagination.offset).limit(pagination.limit)
    ).all()
    return Page[PostRead](data=rows, count=total or 0)
```
- [ ] Modify `app/api/v1/router.py` to include posts:
```python
from fastapi import APIRouter

from app.api.v1.routers import keywords, posts, sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
api_v1_router.include_router(keywords.router)
api_v1_router.include_router(posts.router)
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_posts.py -q
```
- [ ] Commit:
```
git add app/api/v1/routers/posts.py app/api/v1/router.py tests/api/test_posts.py
git commit -m "feat: add posts list router with pagination envelope and status filter"
```

### Task P2.7: Generate router — 202 + enqueues celery task

**Files:**
- Create: `app/api/v1/routers/generate.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/api/test_generate.py`

Steps:
- [ ] Write failing test `tests/api/test_generate.py` (patches `generate_post.delay`; asserts 202 + enqueue):
```python
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.news_item import NewsItem


def _seed_news(db):
    news = NewsItem(
        title="T",
        url="https://n",
        summary="s",
        source="src",
        published_at=datetime.now(timezone.utc),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.commit()
    db.refresh(news)
    return news


def test_generate_returns_202_and_enqueues(client, db_session):
    news = _seed_news(db_session)
    fake_result = MagicMock()
    fake_result.id = "task-123"
    with patch(
        "app.api.v1.routers.generate.generate_post.delay",
        return_value=fake_result,
    ) as delay:
        resp = client.post("/api/v1/generate", json={"news_id": str(news.id)})

    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "task-123"
    delay.assert_called_once_with(str(news.id))


def test_generate_news_id_404_when_missing(client):
    with patch("app.api.v1.routers.generate.generate_post.delay") as delay:
        resp = client.post(
            "/api/v1/generate", json={"news_id": str(uuid.uuid4())}
        )
    assert resp.status_code == 404
    delay.assert_not_called()
```
- [ ] Run it — expected FAIL (404 on /api/v1/generate / ImportError):
```
uv run pytest tests/api/test_generate.py -q
```
- [ ] Create `app/api/v1/routers/generate.py` (enqueues `generate_post.delay(news_id)` per contract; validates news exists; ad-hoc text path passes `None` news_id):
```python
from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import SessionDep
from app.models.news_item import NewsItem
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.tasks.pipeline import generate_post

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_generate(payload: GenerateRequest, db: SessionDep) -> GenerateResponse:
    news_id_arg: str | None = None
    if payload.news_id is not None:
        news = db.get(NewsItem, payload.news_id)
        if news is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="NewsItem not found"
            )
        news_id_arg = str(payload.news_id)
    result = generate_post.delay(news_id_arg)
    return GenerateResponse(task_id=result.id, post_id=None)
```
- [ ] Modify `app/api/v1/router.py` to include generate:
```python
from fastapi import APIRouter

from app.api.v1.routers import generate, keywords, posts, sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
api_v1_router.include_router(keywords.router)
api_v1_router.include_router(posts.router)
api_v1_router.include_router(generate.router)
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_generate.py -q
```
- [ ] Commit:
```
git add app/api/v1/routers/generate.py app/api/v1/router.py tests/api/test_generate.py
git commit -m "feat: add generate router that enqueues generate_post task (202)"
```

### Task P2.8: Errors router — error history list

**Files:**
- Create: `app/api/v1/routers/errors.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/api/test_errors.py`

Steps:
- [ ] Write failing test `tests/api/test_errors.py` (seeds ErrorLog rows via `db_session`):
```python
from datetime import datetime, timezone

from app.models.base import ErrorStage
from app.models.error_log import ErrorLog


def test_list_errors_envelope(client, db_session):
    db_session.add(
        ErrorLog(stage=ErrorStage.generate, message="gen boom")
    )
    db_session.add(
        ErrorLog(stage=ErrorStage.publish, message="pub boom")
    )
    db_session.commit()

    resp = client.get("/api/v1/errors")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "count"}
    assert body["count"] == 2
    messages = {e["message"] for e in body["data"]}
    assert messages == {"gen boom", "pub boom"}
    # Read schema excludes traceback
    assert "traceback" not in body["data"][0]


def test_list_errors_stage_filter(client, db_session):
    db_session.add(ErrorLog(stage=ErrorStage.parse, message="parse err"))
    db_session.add(ErrorLog(stage=ErrorStage.publish, message="publish err"))
    db_session.commit()

    resp = client.get("/api/v1/errors", params={"stage": "publish"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["data"][0]["stage"] == "publish"


def test_list_errors_empty(client):
    resp = client.get("/api/v1/errors")
    assert resp.status_code == 200
    assert resp.json() == {"data": [], "count": 0}
```
- [ ] Run it — expected FAIL (404 on /api/v1/errors):
```
uv run pytest tests/api/test_errors.py -q
```
- [ ] Create `app/api/v1/routers/errors.py`:
```python
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.v1.deps import PaginationDep, SessionDep
from app.models.base import ErrorStage
from app.models.error_log import ErrorLog
from app.schemas.common import Page
from app.schemas.error_log import ErrorLogRead

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get("", response_model=Page[ErrorLogRead])
def list_errors(
    db: SessionDep,
    pagination: PaginationDep,
    stage: ErrorStage | None = None,
) -> Page[ErrorLogRead]:
    count_stmt = select(func.count()).select_from(ErrorLog)
    rows_stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc())
    if stage is not None:
        count_stmt = count_stmt.where(ErrorLog.stage == stage)
        rows_stmt = rows_stmt.where(ErrorLog.stage == stage)
    total = db.scalar(count_stmt)
    rows = db.scalars(
        rows_stmt.offset(pagination.offset).limit(pagination.limit)
    ).all()
    return Page[ErrorLogRead](data=rows, count=total or 0)
```
- [ ] Modify `app/api/v1/router.py` to include errors (final aggregator):
```python
from fastapi import APIRouter

from app.api.v1.routers import errors, generate, keywords, posts, sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
api_v1_router.include_router(keywords.router)
api_v1_router.include_router(posts.router)
api_v1_router.include_router(generate.router)
api_v1_router.include_router(errors.router)
```
- [ ] Run it — expected PASS:
```
uv run pytest tests/api/test_errors.py -q
```
- [ ] Commit:
```
git add app/api/v1/routers/errors.py app/api/v1/router.py tests/api/test_errors.py
git commit -m "feat: add errors history router under /api/v1"
```

### Task P2.9: Full API suite green + lint + OpenAPI smoke

**Files:**
- Test: `tests/api/test_openapi_smoke.py`

Steps:
- [ ] Write `tests/api/test_openapi_smoke.py` (verifies all v1 paths registered under `/api/v1`):
```python
def test_openapi_registers_v1_paths(client):
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"].keys())
    assert "/api/v1/sources" in paths
    assert "/api/v1/sources/{source_id}" in paths
    assert "/api/v1/keywords" in paths
    assert "/api/v1/posts" in paths
    assert "/api/v1/generate" in paths
    assert "/api/v1/errors" in paths


def test_generate_path_is_202(client):
    spec = client.get("/openapi.json").json()
    post_op = spec["paths"]["/api/v1/generate"]["post"]
    assert "202" in post_op["responses"]
```
- [ ] Run the full API test suite — expected PASS:
```
uv run pytest tests/api -q
```
- [ ] Run lint — expected clean:
```
uv run ruff check app/api app/schemas
```
- [ ] Commit:
```
git add tests/api/test_openapi_smoke.py
git commit -m "test: add OpenAPI smoke test for /api/v1 router wiring"
```

---


## Phase 3 — Ingestion / Parsers

### Task P3.1: NewsItemData DTO + BaseParser ABC

**Files:**
- Create: `app/news_parser/__init__.py`
- Create: `app/news_parser/base.py`
- Test: `tests/parser/__init__.py`
- Test: `tests/parser/test_base.py`

Steps:
- [ ] Create empty package marker `app/news_parser/__init__.py` (empty file).
- [ ] Create empty package marker `tests/parser/__init__.py` (empty file).
- [ ] Write failing test `tests/parser/test_base.py`:

```python
import inspect
from dataclasses import is_dataclass
from datetime import datetime, timezone

import pytest

from app.news_parser.base import BaseParser, NewsItemData


def test_news_item_data_is_dataclass_with_contract_fields():
    assert is_dataclass(NewsItemData)
    item = NewsItemData(
        title="Hello",
        url="https://example.com/a",
        summary="sum",
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        raw_text="body",
    )
    assert item.title == "Hello"
    assert item.url == "https://example.com/a"
    assert item.summary == "sum"
    assert item.source == "Example"
    assert item.published_at.tzinfo is timezone.utc
    assert item.raw_text == "body"


def test_news_item_data_allows_optional_none():
    item = NewsItemData(
        title="t",
        url=None,
        summary=None,
        source="src",
        published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        raw_text=None,
    )
    assert item.url is None
    assert item.summary is None
    assert item.raw_text is None


def test_base_parser_is_abstract():
    assert inspect.isabstract(BaseParser)
    with pytest.raises(TypeError):
        BaseParser()


def test_base_parser_fetch_signature():
    sig = inspect.signature(BaseParser.fetch)
    assert list(sig.parameters) == ["self", "source"]
```

- [ ] Run it — expect FAIL (module `app.news_parser.base` does not exist):
  `uv run pytest tests/parser/test_base.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.base'` / collection error.
- [ ] Create `app/news_parser/base.py` (minimal implementation):

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.source import Source


@dataclass
class NewsItemData:
    title: str
    url: str | None
    summary: str | None
    source: str
    published_at: datetime
    raw_text: str | None


class BaseParser(ABC):
    @abstractmethod
    def fetch(self, source: Source) -> list[NewsItemData]:
        ...
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_base.py -q`
  Expected: `4 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/base.py tests/parser/test_base.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/__init__.py app/news_parser/base.py tests/parser/__init__.py tests/parser/test_base.py`
  `git commit -m "feat(news_parser): add NewsItemData DTO and BaseParser ABC"`

### Task P3.2: content_hash (stable sha256 dedup key)

**Files:**
- Create: `app/news_parser/hashing.py`
- Test: `tests/parser/test_hashing.py`

Steps:
- [ ] Write failing test `tests/parser/test_hashing.py`:

```python
from app.news_parser.hashing import content_hash


def test_content_hash_is_sha256_hex():
    h = content_hash("Some Title", "https://example.com/a")
    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_content_hash_is_stable():
    assert content_hash("Title", "https://example.com/a") == content_hash(
        "Title", "https://example.com/a"
    )


def test_content_hash_normalizes_title_whitespace_and_case():
    assert content_hash("  Hello   World  ", "https://example.com/a") == content_hash(
        "hello world", "https://example.com/a"
    )


def test_content_hash_differs_on_url():
    assert content_hash("Title", "https://example.com/a") != content_hash(
        "Title", "https://example.com/b"
    )


def test_content_hash_differs_on_title():
    assert content_hash("Title A", "https://example.com/a") != content_hash(
        "Title B", "https://example.com/a"
    )


def test_content_hash_handles_none_url():
    h = content_hash("Title", None)
    assert isinstance(h, str)
    assert len(h) == 64
    # None and "" treated identically (both empty url component)
    assert content_hash("Title", None) == content_hash("Title", "")
```

- [ ] Run — expect FAIL (module missing):
  `uv run pytest tests/parser/test_hashing.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.hashing'`.
- [ ] Create `app/news_parser/hashing.py`:

```python
from __future__ import annotations

import hashlib


def _normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def content_hash(title: str, url: str | None) -> str:
    """Stable sha256 dedup key over normalized title + url.

    Title is casefolded and whitespace-collapsed; url is taken verbatim
    (None treated as empty string). Components joined with a separator that
    cannot occur in a normalized title or a URL.
    """
    norm_title = _normalize_title(title)
    norm_url = url or ""
    payload = f"{norm_title}\x00{norm_url}".encode()
    return hashlib.sha256(payload).hexdigest()
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_hashing.py -q`
  Expected: `6 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/hashing.py tests/parser/test_hashing.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/hashing.py tests/parser/test_hashing.py`
  `git commit -m "feat(news_parser): add stable content_hash dedup key"`

### Task P3.3: FeedParser (feedparser + conditional GET, published_parsed→UTC, bozo→warn)

**Files:**
- Create: `app/news_parser/feed.py`
- Test: `tests/parser/test_feed.py`

Steps:
- [ ] Write failing test `tests/parser/test_feed.py`. It feeds a local RSS string into `feedparser.parse` (no network) and asserts mapping to `NewsItemData` with UTC `published_at`, plus etag/modified persisted back onto the `Source`, plus `bozo` warning:

```python
import time
from datetime import timezone
from unittest.mock import MagicMock, patch

import feedparser

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.feed import FeedParser

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example AI News</title>
    <item>
      <title>GPT released</title>
      <link>https://example.com/gpt</link>
      <description>A new model summary.</description>
      <pubDate>Mon, 08 Jun 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second story</title>
      <link>https://example.com/second</link>
      <description>Another summary.</description>
      <pubDate>Mon, 08 Jun 2026 11:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _make_source():
    src = MagicMock()
    src.type = SourceType.site
    src.url = "https://example.com/rss"
    src.name = "Example AI News"
    src.etag = None
    src.modified = None
    return src


def test_feed_parser_maps_fields_and_utc():
    parsed = feedparser.parse(SAMPLE_FEED)
    src = _make_source()
    with patch("app.news_parser.feed.feedparser.parse", return_value=parsed):
        items = FeedParser().fetch(src)

    assert len(items) == 2
    first = items[0]
    assert isinstance(first, NewsItemData)
    assert first.title == "GPT released"
    assert first.url == "https://example.com/gpt"
    assert first.summary == "A new model summary."
    assert first.source == "Example AI News"
    assert first.published_at.tzinfo == timezone.utc
    assert first.published_at.hour == 10
    assert first.published_at.year == 2026


def test_feed_parser_passes_conditional_get_and_persists_validators():
    src = _make_source()
    src.etag = '"old-etag"'
    src.modified = "Mon, 01 Jun 2026 00:00:00 GMT"

    fake_parsed = feedparser.parse(SAMPLE_FEED)
    fake_parsed.etag = '"new-etag"'
    fake_parsed.modified = "Mon, 08 Jun 2026 10:00:00 GMT"

    with patch(
        "app.news_parser.feed.feedparser.parse", return_value=fake_parsed
    ) as mock_parse:
        FeedParser().fetch(src)

    # conditional GET validators forwarded
    _, kwargs = mock_parse.call_args
    assert kwargs.get("etag") == '"old-etag"'
    assert kwargs.get("modified") == "Mon, 01 Jun 2026 00:00:00 GMT"
    # new validators stored back on source
    assert src.etag == '"new-etag"'
    assert src.modified == "Mon, 08 Jun 2026 10:00:00 GMT"


def test_feed_parser_not_modified_returns_empty():
    src = _make_source()
    not_modified = feedparser.FeedParserDict()
    not_modified.status = 304
    not_modified.entries = []
    with patch("app.news_parser.feed.feedparser.parse", return_value=not_modified):
        items = FeedParser().fetch(src)
    assert items == []


def test_feed_parser_bozo_warns_but_still_parses():
    parsed = feedparser.parse(SAMPLE_FEED)
    parsed.bozo = 1
    parsed.bozo_exception = Exception("malformed")
    src = _make_source()
    with (
        patch("app.news_parser.feed.feedparser.parse", return_value=parsed),
        patch("app.news_parser.feed.logger.warning") as mock_warn,
    ):
        items = FeedParser().fetch(src)
    assert len(items) == 2
    assert mock_warn.called


def test_feed_parser_missing_pubdate_falls_back_to_now(monkeypatch):
    no_date_feed = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>X</title>
    <item><title>No date</title><link>https://example.com/x</link>
    <description>d</description></item></channel></rss>"""
    parsed = feedparser.parse(no_date_feed)
    src = _make_source()
    with patch("app.news_parser.feed.feedparser.parse", return_value=parsed):
        items = FeedParser().fetch(src)
    assert len(items) == 1
    assert items[0].published_at.tzinfo == timezone.utc
```

- [ ] Run — expect FAIL (module missing):
  `uv run pytest tests/parser/test_feed.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.feed'`.
- [ ] Create `app/news_parser/feed.py`:

```python
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import feedparser
import structlog

from app.news_parser.base import BaseParser, NewsItemData

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)


def _struct_time_to_utc(parsed_time) -> datetime | None:
    if not parsed_time:
        return None
    # parsed_time is a time.struct_time in UTC (feedparser normalizes to GMT).
    return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)


class FeedParser(BaseParser):
    """RSS/Atom parser via feedparser with conditional GET support."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        parsed = feedparser.parse(
            source.url,
            etag=source.etag,
            modified=source.modified,
        )

        if getattr(parsed, "bozo", 0):
            logger.warning(
                "feed.bozo",
                url=source.url,
                error=str(getattr(parsed, "bozo_exception", "")),
            )

        if getattr(parsed, "status", None) == 304:
            return []

        # Persist fresh conditional-GET validators back onto the source.
        new_etag = getattr(parsed, "etag", None)
        if new_etag is not None:
            source.etag = new_etag
        new_modified = getattr(parsed, "modified", None)
        if new_modified is not None:
            source.modified = new_modified

        items: list[NewsItemData] = []
        for entry in parsed.entries:
            published_at = _struct_time_to_utc(
                getattr(entry, "published_parsed", None)
            ) or datetime.now(timezone.utc)
            items.append(
                NewsItemData(
                    title=getattr(entry, "title", "") or "",
                    url=getattr(entry, "link", None),
                    summary=getattr(entry, "summary", None),
                    source=source.name,
                    published_at=published_at,
                    raw_text=None,
                )
            )
        return items
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_feed.py -q`
  Expected: `5 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/feed.py tests/parser/test_feed.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/feed.py tests/parser/test_feed.py`
  `git commit -m "feat(news_parser): add FeedParser with conditional GET and UTC mapping"`

### Task P3.4: SiteScraper (httpx + selectolax + trafilatura)

**Files:**
- Create: `app/news_parser/site.py`
- Test: `tests/parser/test_site.py`

Steps:
- [ ] Write failing test `tests/parser/test_site.py`. Mocks the network with `respx`, returns a static HTML page; asserts title via selectolax and body text via a patched `trafilatura.extract`:

```python
from datetime import timezone
from unittest.mock import MagicMock, patch

import httpx
import respx

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.site import SiteScraper

PAGE_HTML = """<!DOCTYPE html>
<html>
  <head><title>Breaking: AI does things</title></head>
  <body>
    <article>
      <h1>Breaking: AI does things</h1>
      <p>The full article body with several sentences of content here.</p>
    </article>
  </body>
</html>
"""


def _make_source():
    src = MagicMock()
    src.type = SourceType.site
    src.url = "https://example.com/article"
    src.name = "Example Site"
    return src


@respx.mock
def test_site_scraper_extracts_title_and_text():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=PAGE_HTML)
    )
    src = _make_source()
    with patch(
        "app.news_parser.site.trafilatura.extract",
        return_value="The full article body with several sentences of content here.",
    ):
        items = SiteScraper().fetch(src)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, NewsItemData)
    assert item.title == "Breaking: AI does things"
    assert item.url == "https://example.com/article"
    assert item.source == "Example Site"
    assert "full article body" in item.raw_text
    assert item.published_at.tzinfo == timezone.utc


@respx.mock
def test_site_scraper_empty_extraction_returns_empty_list():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=PAGE_HTML)
    )
    src = _make_source()
    with patch("app.news_parser.site.trafilatura.extract", return_value=None):
        items = SiteScraper().fetch(src)
    assert items == []


@respx.mock
def test_site_scraper_non_200_returns_empty_list():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(404)
    )
    src = _make_source()
    with patch("app.news_parser.site.logger.warning") as mock_warn:
        items = SiteScraper().fetch(src)
    assert items == []
    assert mock_warn.called
```

- [ ] Run — expect FAIL (module missing):
  `uv run pytest tests/parser/test_site.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.site'`.
- [ ] Create `app/news_parser/site.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
import structlog
import trafilatura
from selectolax.lexbor import LexborHTMLParser

from app.news_parser.base import BaseParser, NewsItemData

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)

_TIMEOUT = 20.0


def _extract_title(tree: LexborHTMLParser) -> str:
    h1 = tree.css_first("article h1") or tree.css_first("h1")
    if h1 is not None:
        text = h1.text(strip=True)
        if text:
            return text
    title_node = tree.css_first("title")
    if title_node is not None:
        return title_node.text(strip=True)
    return ""


class SiteScraper(BaseParser):
    """HTML fallback parser: httpx GET + selectolax title + trafilatura body."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        try:
            response = httpx.get(
                source.url,
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "m4-news-bot/1.0"},
            )
        except httpx.HTTPError as exc:
            logger.warning("site.fetch_error", url=source.url, error=str(exc))
            return []

        if response.status_code != 200:
            logger.warning(
                "site.bad_status", url=source.url, status=response.status_code
            )
            return []

        html = response.text
        tree = LexborHTMLParser(html)
        title = _extract_title(tree)

        body = trafilatura.extract(html)
        if not body:
            logger.warning("site.no_content", url=source.url)
            return []

        return [
            NewsItemData(
                title=title,
                url=source.url,
                summary=None,
                source=source.name,
                published_at=datetime.now(timezone.utc),
                raw_text=body,
            )
        ]
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_site.py -q`
  Expected: `3 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/site.py tests/parser/test_site.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/site.py tests/parser/test_site.py`
  `git commit -m "feat(news_parser): add SiteScraper (httpx + selectolax + trafilatura)"`

### Task P3.5: TelegramReader (Telethon incremental read, resolve+cache, min_id)

**Files:**
- Create: `app/news_parser/telegram_reader.py`
- Test: `tests/parser/test_telegram_reader.py`

Steps:
- [ ] Write failing test `tests/parser/test_telegram_reader.py`. Mocks the Telethon `TelegramClient` so `asyncio.run(_read)` runs against fakes — asserts resolve-once via `get_entity`, `get_messages(min_id=last_seen_msg_id)`, mapping to `NewsItemData`, and that `source.last_seen_msg_id` is bumped to the newest message id:

```python
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.base import SourceType
from app.news_parser.base import NewsItemData
from app.news_parser.telegram_reader import TelegramReader


def _make_source(last_seen=100):
    src = MagicMock()
    src.type = SourceType.tg
    src.url = "@ai_channel"
    src.name = "AI Channel"
    src.last_seen_msg_id = last_seen
    return src


def _make_message(msg_id: int, text: str):
    return SimpleNamespace(
        id=msg_id,
        message=text,
        date=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
    )


def _make_fake_client(entity, messages):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get_entity = AsyncMock(return_value=entity)
    client.get_messages = AsyncMock(return_value=messages)
    return client


def test_telegram_reader_incremental_resolve_and_min_id():
    entity = SimpleNamespace(id=555, title="AI Channel")
    messages = [_make_message(102, "newest"), _make_message(101, "older")]
    fake_client = _make_fake_client(entity, messages)
    src = _make_source(last_seen=100)

    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)

    # resolve once
    fake_client.get_entity.assert_awaited_once_with("@ai_channel")
    # incremental min_id read off the resolved entity
    _, kwargs = fake_client.get_messages.call_args
    assert kwargs["min_id"] == 100
    assert kwargs["entity"] == entity or fake_client.get_messages.call_args.args[0] == entity

    assert len(items) == 2
    assert all(isinstance(i, NewsItemData) for i in items)
    titles = {i.title for i in items}
    assert "newest" in titles
    # last_seen_msg_id bumped to newest id
    assert src.last_seen_msg_id == 102
    assert items[0].published_at.tzinfo == timezone.utc
    assert items[0].source == "AI Channel"


def test_telegram_reader_no_new_messages_keeps_last_seen():
    entity = SimpleNamespace(id=555, title="AI Channel")
    fake_client = _make_fake_client(entity, [])
    src = _make_source(last_seen=100)
    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)
    assert items == []
    assert src.last_seen_msg_id == 100


def test_telegram_reader_skips_empty_message_text():
    entity = SimpleNamespace(id=555, title="AI Channel")
    messages = [_make_message(103, "has text"), _make_message(104, "")]
    fake_client = _make_fake_client(entity, messages)
    src = _make_source(last_seen=100)
    with patch(
        "app.news_parser.telegram_reader._build_client", return_value=fake_client
    ):
        items = TelegramReader().fetch(src)
    assert len(items) == 1
    assert items[0].title == "has text"
    # last_seen still tracks newest message id even if it had no text
    assert src.last_seen_msg_id == 104
```

- [ ] Run — expect FAIL (module missing):
  `uv run pytest tests/parser/test_telegram_reader.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.telegram_reader'`.
- [ ] Create `app/news_parser/telegram_reader.py`:

```python
from __future__ import annotations

import asyncio
from datetime import timezone
from typing import TYPE_CHECKING

import structlog
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.core.config import settings
from app.news_parser.base import BaseParser, NewsItemData

if TYPE_CHECKING:
    from app.models.source import Source

logger = structlog.get_logger(__name__)

# Resolved-entity cache: keep @username → entity across calls within a process
# so we never re-resolve every tick (FloodWait protection).
_entity_cache: dict[str, object] = {}


def _build_client() -> TelegramClient:
    return TelegramClient(
        StringSession(settings.TELETHON_STRING_SESSION.get_secret_value()),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH.get_secret_value(),
    )


def _title_from(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:200]


async def _read(source: Source) -> list[NewsItemData]:
    client = _build_client()
    async with client:
        entity = _entity_cache.get(source.url)
        if entity is None:
            entity = await client.get_entity(source.url)
            _entity_cache[source.url] = entity

        messages = await client.get_messages(
            entity,
            min_id=source.last_seen_msg_id or 0,
            limit=100,
        )

    items: list[NewsItemData] = []
    max_id = source.last_seen_msg_id or 0
    for msg in messages:
        max_id = max(max_id, msg.id)
        text = (getattr(msg, "message", None) or "").strip()
        if not text:
            continue
        published_at = msg.date
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        items.append(
            NewsItemData(
                title=_title_from(text),
                url=None,
                summary=None,
                source=source.name,
                published_at=published_at,
                raw_text=text,
            )
        )

    if max_id > (source.last_seen_msg_id or 0):
        source.last_seen_msg_id = max_id
    return items


class TelegramReader(BaseParser):
    """Read-only incremental Telethon reader (resolve-once + cache, min_id)."""

    def fetch(self, source: Source) -> list[NewsItemData]:
        return asyncio.run(_read(source))
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_telegram_reader.py -q`
  Expected: `3 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/telegram_reader.py tests/parser/test_telegram_reader.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/telegram_reader.py tests/parser/test_telegram_reader.py`
  `git commit -m "feat(news_parser): add incremental Telethon TelegramReader"`

### Task P3.6: Parser factory (get_parser by source.type)

**Files:**
- Create: `app/news_parser/factory.py`
- Test: `tests/parser/test_factory.py`

Steps:
- [ ] Write failing test `tests/parser/test_factory.py`. A `tg` source returns `TelegramReader`; a `site` source whose URL looks like a feed returns `FeedParser`, otherwise `SiteScraper`:

```python
from unittest.mock import MagicMock

from app.models.base import SourceType
from app.news_parser.factory import get_parser
from app.news_parser.feed import FeedParser
from app.news_parser.site import SiteScraper
from app.news_parser.telegram_reader import TelegramReader


def _source(type_, url):
    src = MagicMock()
    src.type = type_
    src.url = url
    return src


def test_get_parser_tg_returns_telegram_reader():
    assert isinstance(get_parser(_source(SourceType.tg, "@chan")), TelegramReader)


def test_get_parser_site_feed_url_returns_feed_parser():
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/feed.xml")),
        FeedParser,
    )
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/rss")),
        FeedParser,
    )


def test_get_parser_site_plain_url_returns_site_scraper():
    assert isinstance(
        get_parser(_source(SourceType.site, "https://example.com/article")),
        SiteScraper,
    )
```

- [ ] Run — expect FAIL (module missing):
  `uv run pytest tests/parser/test_factory.py -q`
  Expected: `ModuleNotFoundError: No module named 'app.news_parser.factory'`.
- [ ] Create `app/news_parser/factory.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.base import SourceType
from app.news_parser.base import BaseParser
from app.news_parser.feed import FeedParser
from app.news_parser.site import SiteScraper
from app.news_parser.telegram_reader import TelegramReader

if TYPE_CHECKING:
    from app.models.source import Source

_FEED_HINTS = ("rss", "feed", "atom", ".xml")


def _looks_like_feed(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _FEED_HINTS)


def get_parser(source: Source) -> BaseParser:
    if source.type == SourceType.tg:
        return TelegramReader()
    if _looks_like_feed(source.url):
        return FeedParser()
    return SiteScraper()
```

- [ ] Run — expect PASS:
  `uv run pytest tests/parser/test_factory.py -q`
  Expected: `3 passed`.
- [ ] Lint: `uv run ruff check app/news_parser/factory.py tests/parser/test_factory.py` (expected: no errors).
- [ ] Commit:
  `git add app/news_parser/factory.py tests/parser/test_factory.py`
  `git commit -m "feat(news_parser): add get_parser factory by source type"`

### Task P3.7: parse_source task (persist NewsItem, dedup by content_hash, enqueue chain)

**Files:**
- Modify: `app/tasks/pipeline.py`
- Test: `tests/tasks/__init__.py`
- Test: `tests/tasks/test_parse_source.py`

Steps:
- [ ] Create empty package marker `tests/tasks/__init__.py` (empty file).
- [ ] Write failing test `tests/tasks/test_parse_source.py`. Uses the function-scoped DB session from `conftest.py`, patches `get_parser` to return a fake parser yielding `NewsItemData`, patches the Celery `chain` so wiring can be asserted, and verifies: NewsItem rows are inserted with computed `content_hash`; a duplicate `content_hash` on re-run is a no-op (no new rows, no chain for the dup); and a `chain(filter_item.s(news_id) | generate_post.s() | publish_post.s())` is enqueued per NEW item:

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.news_item import NewsItem
from app.models.source import Source
from app.news_parser.base import NewsItemData
from app.news_parser.hashing import content_hash
from app.tasks import pipeline


def _seed_source(db) -> Source:
    src = Source(type="site", name="Example", url="https://example.com/rss")
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def _news_data(title, url):
    return NewsItemData(
        title=title,
        url=url,
        summary="sum",
        source="Example",
        published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
        raw_text="body",
    )


def test_parse_source_persists_new_items_and_enqueues_chain(db_session):
    src = _seed_source(db_session)
    fake_parser = MagicMock()
    fake_parser.fetch.return_value = [
        _news_data("First", "https://example.com/1"),
        _news_data("Second", "https://example.com/2"),
    ]

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
        patch.object(pipeline, "filter_item"),
        patch.object(pipeline, "generate_post"),
        patch.object(pipeline, "publish_post"),
    ):
        pipeline.parse_source(str(src.id))

    rows = db_session.query(NewsItem).all()
    assert len(rows) == 2
    hashes = {r.content_hash for r in rows}
    assert content_hash("First", "https://example.com/1") in hashes
    assert content_hash("Second", "https://example.com/2") in hashes
    # one chain enqueued per new item
    assert mock_chain.call_count == 2
    assert mock_chain.return_value.delay.call_count == 2


def test_parse_source_is_noop_on_duplicate_content_hash(db_session):
    src = _seed_source(db_session)
    # pre-existing row with the same hash the parser will produce
    existing_hash = content_hash("First", "https://example.com/1")
    db_session.add(
        NewsItem(
            title="First",
            url="https://example.com/1",
            summary="sum",
            source="Example",
            published_at=datetime(2026, 6, 8, tzinfo=timezone.utc),
            raw_text="body",
            content_hash=existing_hash,
        )
    )
    db_session.commit()

    fake_parser = MagicMock()
    fake_parser.fetch.return_value = [_news_data("First", "https://example.com/1")]

    with (
        patch.object(pipeline, "SessionLocal", return_value=db_session),
        patch.object(pipeline, "get_parser", return_value=fake_parser),
        patch.object(pipeline, "chain") as mock_chain,
        patch.object(pipeline, "filter_item"),
        patch.object(pipeline, "generate_post"),
        patch.object(pipeline, "publish_post"),
    ):
        pipeline.parse_source(str(src.id))

    rows = db_session.query(NewsItem).filter_by(content_hash=existing_hash).all()
    assert len(rows) == 1  # no duplicate inserted
    mock_chain.assert_not_called()  # no chain for the duplicate
```

- [ ] Run — expect FAIL (`parse_source` not yet defined / `chain` symbol absent in `pipeline`):
  `uv run pytest tests/tasks/test_parse_source.py -q`
  Expected: `AttributeError`/`ImportError` around `pipeline.parse_source` or `pipeline.chain`.
- [ ] Read existing `app/tasks/pipeline.py` to integrate without clobbering sibling tasks:
  `uv run python -c "print(open('app/tasks/pipeline.py').read())"` (reference only; do not rely on echo for edits).
- [ ] Add/implement `parse_source` in `app/tasks/pipeline.py` (keep existing `collect_sources`/`filter_item`/`generate_post`/`publish_post`; add the imports and this task). Insert the imports near the top and the task body alongside the others:

```python
# --- imports (add if missing, near existing imports) ---
from celery import chain

from app.core.db import SessionLocal
from app.models.news_item import NewsItem
from app.models.source import Source
from app.news_parser.factory import get_parser
from app.news_parser.hashing import content_hash


@celery_app.task(name="app.tasks.pipeline.parse_source")
def parse_source(source_id: str) -> None:
    """Fetch a source, persist new NewsItems (dedup by content_hash),
    and enqueue a per-item chain(filter_item | generate_post | publish_post)
    for each newly-inserted item. Duplicate content_hash is a no-op.
    """
    with SessionLocal() as db:
        source = db.get(Source, uuid.UUID(source_id))
        if source is None or not source.enabled:
            return

        parser = get_parser(source)
        items = parser.fetch(source)

        new_ids: list[str] = []
        for data in items:
            chash = content_hash(data.title, data.url)
            exists = (
                db.query(NewsItem)
                .filter(NewsItem.content_hash == chash)
                .first()
            )
            if exists is not None:
                continue
            news = NewsItem(
                title=data.title,
                url=data.url,
                summary=data.summary,
                source=data.source,
                published_at=data.published_at,
                raw_text=data.raw_text,
                content_hash=chash,
            )
            db.add(news)
            db.flush()
            new_ids.append(str(news.id))

        # persist conditional-GET validators / last_seen_msg_id mutated by parser
        db.commit()

    for news_id in new_ids:
        chain(
            filter_item.s(news_id) | generate_post.s() | publish_post.s()
        ).delay()
```

  Note: if `import uuid` is not already at the top of `pipeline.py`, add it. Do not duplicate any import that already exists.
- [ ] Run — expect PASS:
  `uv run pytest tests/tasks/test_parse_source.py -q`
  Expected: `2 passed`.
- [ ] Full parser + parse_source regression:
  `uv run pytest tests/parser tests/tasks/test_parse_source.py -q`
  Expected: all green.
- [ ] Lint: `uv run ruff check app/tasks/pipeline.py tests/tasks/test_parse_source.py` (expected: no errors).
- [ ] Commit:
  `git add app/tasks/pipeline.py tests/tasks/__init__.py tests/tasks/test_parse_source.py`
  `git commit -m "feat(tasks): parse_source persists NewsItem with content_hash dedup and enqueues chain"`

---


## Phase 4 — Filter + AI Generation

### Task P4.1: Filter normalize (casefold/NFC/strip-url-emoji/collapse-ws)

**Files:**
- Create: `app/filter/__init__.py`
- Create: `app/filter/normalize.py`
- Test: `tests/filter/__init__.py`, `tests/filter/test_normalize.py`

- [ ] Create `app/filter/__init__.py` (empty package marker) and `tests/filter/__init__.py` (empty).
- [ ] Write failing test `tests/filter/test_normalize.py`:

```python
from app.filter.normalize import normalize


def test_normalize_casefolds_and_collapses_whitespace():
    assert normalize("  Вибори   В   Україні  ") == "вибори в україні"


def test_normalize_strips_urls():
    out = normalize("Новина тут https://example.com/path?x=1 кінець")
    assert "http" not in out
    assert "вибори" not in out  # sanity
    assert out == "новина тут кінець"


def test_normalize_strips_emoji():
    assert normalize("Перемога 🎉🔥 сьогодні") == "перемога сьогодні"


def test_normalize_nfc_composes_combining_marks():
    # "й" as base "и" + combining breve U+0306 must normalise to single NFC codepoint
    decomposed = "и\u0306"
    composed = "\u0439"
    assert normalize(decomposed) == normalize(composed)
```

- [ ] Run — expect FAIL (module/function missing):

```
uv run pytest tests/filter/test_normalize.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.filter.normalize'` (collection error / FAIL).

- [ ] Implement `app/filter/normalize.py`:

```python
import re
import unicodedata

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WS_RE = re.compile(r"\s+")

# Emoji / pictographic / symbol ranges to strip.
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # symbols, pictographs, emoji
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U00002190-\U000021ff"  # arrows
    "\U00002b00-\U00002bff"  # misc symbols and arrows
    "\U0000200d"             # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def normalize(text: str) -> str:
    """casefold + NFC + strip URLs/emoji + collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = _URL_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    text = text.casefold()
    text = _WS_RE.sub(" ", text)
    return text.strip()
```

- [ ] Run — expect PASS:

```
uv run pytest tests/filter/test_normalize.py -q
```

Expected: `4 passed`.

- [ ] Verify lint:

```
uv run ruff check app/filter/normalize.py tests/filter/test_normalize.py
```

- [ ] Commit:

```
git add app/filter/__init__.py app/filter/normalize.py tests/filter/__init__.py tests/filter/test_normalize.py
git commit -m "feat: add filter normalize (casefold/NFC/strip-url-emoji)"
```

### Task P4.2: Language detection (lingua, restricted to ALLOWED_LANGUAGES, soft)

**Files:**
- Create: `app/filter/language.py`
- Test: `tests/filter/test_language.py`

- [ ] Write failing test `tests/filter/test_language.py`:

```python
from app.filter.language import detect_language


def test_detects_english():
    assert detect_language("The government announced a new election today.") == "en"


def test_detects_ukrainian():
    assert detect_language("Сьогодні уряд оголосив про нові вибори в країні.") == "uk"


def test_short_or_ambiguous_returns_none():
    # too little signal to be confident -> soft None
    assert detect_language("ok") is None


def test_disallowed_language_returns_none():
    # confident but not in ALLOWED_LANGUAGES (uk/ru/en) -> None
    out = detect_language("Das ist eine deutsche Nachricht über die Regierung heute.")
    assert out is None
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/filter/test_language.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.filter.language'`.

- [ ] Implement `app/filter/language.py`:

```python
from lingua import IsoCode639_1, Language, LanguageDetectorBuilder

from app.core.config import settings

# Map our ISO-639-1 codes to lingua Language enum members.
# "uk" -> Ukrainian, "ru" -> Russian, "en" -> English (extend as needed).
_ISO_TO_LANGUAGE = {
    "uk": Language.UKRAINIAN,
    "ru": Language.RUSSIAN,
    "en": Language.ENGLISH,
}

# Build a detector over ALL languages so we can recognise (and reject) a confident
# non-allowed language, but only accept results whose code is in ALLOWED_LANGUAGES.
_detector = LanguageDetectorBuilder.from_all_languages().with_preloaded_language_models().build()

_ALLOWED = set(settings.ALLOWED_LANGUAGES)

# Minimum confidence to treat a detection as reliable ("soft": below this -> None).
_MIN_CONFIDENCE = 0.65


def detect_language(text: str) -> str | None:
    """lingua detection restricted to ALLOWED_LANGUAGES.

    Returns the ISO-639-1 code if confidently one of the allowed languages,
    otherwise None (soft signal: do not drop on uncertainty).
    """
    if not text or not text.strip():
        return None
    values = _detector.compute_language_confidence_values(text)
    if not values:
        return None
    top = values[0]
    if top.value < _MIN_CONFIDENCE:
        return None
    iso: IsoCode639_1 = top.language.iso_code_639_1
    code = iso.name.lower()
    if code not in _ALLOWED:
        return None
    return code
```

- [ ] Run — expect PASS:

```
uv run pytest tests/filter/test_language.py -q
```

Expected: `4 passed`.

- [ ] Verify lint:

```
uv run ruff check app/filter/language.py tests/filter/test_language.py
```

- [ ] Commit:

```
git add app/filter/language.py tests/filter/test_language.py
git commit -m "feat: add lingua language detection restricted to allowed langs"
```

### Task P4.3: Keyword matching (pymorphy3 lemma, whole-word, any/all)

**Files:**
- Create: `app/filter/keywords.py`
- Test: `tests/filter/test_keywords.py`

- [ ] Write failing test `tests/filter/test_keywords.py` (covers the acceptance criterion: keyword `вибори` matches inflected `виборів`):

```python
from app.filter.keywords import matches_keywords
from app.models.keyword import Keyword


def _kw(word: str, lang: str | None = None) -> Keyword:
    return Keyword(word=word, lang=lang)


def test_matches_inflected_form_via_lemma():
    # keyword "вибори" must match the inflected genitive "виборів"
    kws = [_kw("вибори")]
    assert matches_keywords("сьогодні відбулося багато виборів у регіоні", kws, "any") is True


def test_no_match_when_keyword_absent():
    kws = [_kw("економіка")]
    assert matches_keywords("сьогодні відбулося багато виборів", kws, "any") is False


def test_whole_word_only_no_substring_match():
    # "вибори" must NOT match inside an unrelated longer token
    kws = [_kw("вибори")]
    assert matches_keywords("розвиборимось колись", kws, "any") is False


def test_mode_all_requires_every_keyword():
    kws = [_kw("вибори"), _kw("президент")]
    text = "вибори президента відбулися"
    assert matches_keywords(text, kws, "all") is True
    assert matches_keywords("лише вибори без іншого", kws, "all") is False


def test_empty_keywords_returns_true():
    # no keywords configured -> nothing to filter on -> pass
    assert matches_keywords("будь-який текст", [], "any") is True
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/filter/test_keywords.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.filter.keywords'`.

- [ ] Implement `app/filter/keywords.py`:

```python
import re

import pymorphy3

from app.models.keyword import Keyword

# Module-level singletons (init once per worker).
_morph_uk = pymorphy3.MorphAnalyzer(lang="uk")
_morph_ru = pymorphy3.MorphAnalyzer(lang="ru")

# Token = run of word characters (letters/digits/underscore), Unicode-aware.
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _lemmatize(token: str) -> set[str]:
    """All normal forms (lemmas) of a token across uk and ru analyzers."""
    lemmas: set[str] = {token}
    for morph in (_morph_uk, _morph_ru):
        parsed = morph.parse(token)
        if parsed:
            lemmas.add(parsed[0].normal_form)
    return lemmas


def _text_lemmas(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text.casefold()):
        out |= _lemmatize(tok)
    return out


def _keyword_lemma(word: str) -> str:
    tokens = _TOKEN_RE.findall(word.casefold())
    if not tokens:
        return word.casefold()
    # single-word keyword: take its lemma (prefer uk, fall back to ru/raw)
    first = tokens[0]
    return next(iter(sorted(_lemmatize(first))[:1]), first) if False else _morph_uk.parse(first)[0].normal_form


def matches_keywords(text: str, keywords: list[Keyword], mode: str) -> bool:
    """Whole-word, lemma-based keyword match.

    mode "any" -> at least one keyword present; "all" -> every keyword present.
    Empty keyword list -> True (nothing to filter on).
    """
    if not keywords:
        return True
    haystack = _text_lemmas(text)
    results = [_keyword_lemma(kw.word) in haystack for kw in keywords]
    if mode == "all":
        return all(results)
    return any(results)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/filter/test_keywords.py -q
```

Expected: `5 passed`.

- [ ] Verify lint:

```
uv run ruff check app/filter/keywords.py tests/filter/test_keywords.py
```

- [ ] Commit:

```
git add app/filter/keywords.py tests/filter/test_keywords.py
git commit -m "feat: add pymorphy3 lemma whole-word keyword matching"
```

### Task P4.4: Redis dedup (SET NX EX, fakeredis in tests)

**Files:**
- Create: `app/filter/dedup.py`
- Test: `tests/filter/test_dedup.py`

- [ ] Write failing test `tests/filter/test_dedup.py` (uses the `fakeredis` fixture from conftest; falls back to a local fakeredis instance if the fixture is named differently — here we instantiate directly to keep the test self-contained):

```python
import fakeredis

from app.filter.dedup import is_duplicate


def test_first_seen_is_not_duplicate_then_subsequent_is():
    r = fakeredis.FakeStrictRedis()
    h = "abc123hash"
    assert is_duplicate(h, r) is False  # first time -> stored, not a dup
    assert is_duplicate(h, r) is True   # second time -> already seen -> dup


def test_distinct_hashes_independent():
    r = fakeredis.FakeStrictRedis()
    assert is_duplicate("hash-a", r) is False
    assert is_duplicate("hash-b", r) is False


def test_key_has_ttl_set():
    r = fakeredis.FakeStrictRedis()
    is_duplicate("ttl-hash", r)
    assert r.ttl("m4:seen:ttl-hash") > 0
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/filter/test_dedup.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.filter.dedup'`.

- [ ] Implement `app/filter/dedup.py`:

```python
from app.core.config import settings

_KEY_PREFIX = "m4:seen:"


def is_duplicate(content_hash: str, redis_client) -> bool:
    """Atomic exact-dedup via Redis SET NX EX.

    Returns True if the hash was already present (duplicate), False if this call
    recorded it for the first time. TTL = settings.DEDUP_TTL_SECONDS.
    """
    key = f"{_KEY_PREFIX}{content_hash}"
    stored = redis_client.set(key, "1", nx=True, ex=settings.DEDUP_TTL_SECONDS)
    # set() returns True when the key was newly set, None/False when it already existed.
    return not stored
```

- [ ] Run — expect PASS:

```
uv run pytest tests/filter/test_dedup.py -q
```

Expected: `3 passed`.

- [ ] Verify lint:

```
uv run ruff check app/filter/dedup.py tests/filter/test_dedup.py
```

- [ ] Commit:

```
git add app/filter/dedup.py tests/filter/test_dedup.py
git commit -m "feat: add redis SET NX EX exact dedup"
```

### Task P4.5: Filter service (passes_filters order dedup→language→keywords)

**Files:**
- Create: `app/filter/service.py`
- Test: `tests/filter/test_service.py`

- [ ] Write failing test `tests/filter/test_service.py`:

```python
from datetime import datetime, timezone

import fakeredis

from app.core.config import settings
from app.filter.service import passes_filters
from app.models.keyword import Keyword
from app.models.news_item import NewsItem


def _news(title: str, summary: str | None = None) -> NewsItem:
    return NewsItem(
        title=title,
        url="https://example.com/a",
        summary=summary,
        source="Example",
        published_at=datetime.now(timezone.utc),
        raw_text=summary or title,
        content_hash="hash-" + title[:8],
    )


def _kw(word: str) -> Keyword:
    return Keyword(word=word)


def test_passes_when_allowed_lang_and_keyword_hits_inflected():
    r = fakeredis.FakeStrictRedis()
    item = _news("Сьогодні відбулося багато виборів у країні")
    assert passes_filters(item, [_kw("вибори")], r, settings) is True


def test_dropped_when_duplicate():
    r = fakeredis.FakeStrictRedis()
    item = _news("Сьогодні відбулося багато виборів у країні")
    assert passes_filters(item, [_kw("вибори")], r, settings) is True
    # same content_hash second time -> dedup drop
    assert passes_filters(item, [_kw("вибори")], r, settings) is False


def test_dropped_when_keyword_absent():
    r = fakeredis.FakeStrictRedis()
    item = _news("Сьогодні гарна погода в місті")
    assert passes_filters(item, [_kw("вибори")], r, settings) is False


def test_dropped_on_confident_disallowed_language():
    r = fakeredis.FakeStrictRedis()
    item = _news("Das ist eine lange deutsche Nachricht über die Regierung heute Abend.")
    assert passes_filters(item, [], r, settings) is False
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/filter/test_service.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.filter.service'`.

- [ ] Implement `app/filter/service.py`:

```python
from app.filter.dedup import is_duplicate
from app.filter.keywords import matches_keywords
from app.filter.language import detect_language
from app.filter.normalize import normalize
from app.models.keyword import Keyword
from app.models.news_item import NewsItem


def _searchable_text(item: NewsItem) -> str:
    parts = [item.title, item.summary or "", item.raw_text or ""]
    return " ".join(p for p in parts if p)


def passes_filters(item: NewsItem, keywords: list[Keyword], redis_client, settings) -> bool:
    """Filter gate. Order: dedup -> language (soft) -> keywords.

    Returns True if the item should continue down the pipeline.
    """
    # 1) dedup (records the hash atomically; True means already seen)
    if is_duplicate(item.content_hash, redis_client):
        return False

    text = normalize(_searchable_text(item))

    # 2) language: soft signal. Drop only on a confident DISALLOWED language.
    lang = detect_language(_searchable_text(item))
    # detect_language returns a code only when it is an allowed language;
    # to distinguish "confident-but-disallowed" from "uncertain" we re-check raw.
    if lang is None and _is_confidently_disallowed(_searchable_text(item), settings):
        return False

    # 3) keywords (whole-word lemma match)
    return matches_keywords(text, keywords, settings.KEYWORD_MATCH_MODE)


def _is_confidently_disallowed(text: str, settings) -> bool:
    """True when lingua is confident the text is a non-allowed language."""
    from app.filter.language import _MIN_CONFIDENCE, _detector

    if not text or not text.strip():
        return False
    values = _detector.compute_language_confidence_values(text)
    if not values:
        return False
    top = values[0]
    if top.value < _MIN_CONFIDENCE:
        return False
    code = top.language.iso_code_639_1.name.lower()
    return code not in set(settings.ALLOWED_LANGUAGES)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/filter/test_service.py -q
```

Expected: `4 passed`.

- [ ] Verify lint:

```
uv run ruff check app/filter/service.py tests/filter/test_service.py
```

- [ ] Commit:

```
git add app/filter/service.py tests/filter/test_service.py
git commit -m "feat: add passes_filters gate (dedup->language->keywords)"
```

### Task P4.6: AI PostDraft schema

**Files:**
- Create: `app/ai/__init__.py`
- Create: `app/ai/schemas.py`
- Test: `tests/ai/__init__.py`, `tests/ai/test_schemas.py`

- [ ] Create `app/ai/__init__.py` (empty) and `tests/ai/__init__.py` (empty).
- [ ] Write failing test `tests/ai/test_schemas.py`:

```python
from app.ai.schemas import PostDraft


def test_postdraft_defaults_hashtags_to_empty_list():
    draft = PostDraft(text="Привіт світ", language="uk")
    assert draft.text == "Привіт світ"
    assert draft.language == "uk"
    assert draft.hashtags == []


def test_postdraft_accepts_hashtags():
    draft = PostDraft(text="t", language="en", hashtags=["#ai", "#news"])
    assert draft.hashtags == ["#ai", "#news"]
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/ai/test_schemas.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.ai.schemas'`.

- [ ] Implement `app/ai/schemas.py`:

```python
from pydantic import BaseModel


class PostDraft(BaseModel):
    text: str
    language: str
    hashtags: list[str] = []
```

- [ ] Run — expect PASS:

```
uv run pytest tests/ai/test_schemas.py -q
```

Expected: `2 passed`.

- [ ] Verify lint:

```
uv run ruff check app/ai/schemas.py tests/ai/test_schemas.py
```

- [ ] Commit:

```
git add app/ai/__init__.py app/ai/schemas.py tests/ai/__init__.py tests/ai/test_schemas.py
git commit -m "feat: add PostDraft AI schema"
```

### Task P4.7: AI moderation gate (is_flagged)

**Files:**
- Create: `app/ai/moderation.py`
- Test: `tests/ai/test_moderation.py`

- [ ] Write failing test `tests/ai/test_moderation.py` (mock OpenAI moderation via respx):

```python
import httpx
import respx

from app.ai.moderation import is_flagged


@respx.mock
def test_is_flagged_true_when_api_flags():
    respx.post("https://api.openai.com/v1/moderations").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "modr-1",
                "model": "omni-moderation-latest",
                "results": [{"flagged": True, "categories": {}, "category_scores": {}}],
            },
        )
    )
    assert is_flagged("щось погане") is True


@respx.mock
def test_is_flagged_false_when_clean():
    respx.post("https://api.openai.com/v1/moderations").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "modr-2",
                "model": "omni-moderation-latest",
                "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
            },
        )
    )
    assert is_flagged("звичайна новина про вибори") is False
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/ai/test_moderation.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.ai.moderation'`.

- [ ] Implement `app/ai/moderation.py`:

```python
from openai import OpenAI

from app.core.config import settings

_MODERATION_MODEL = "omni-moderation-latest"

# Module-level client (one per worker).
_client = OpenAI(
    api_key=settings.OPENAI_API_KEY.get_secret_value(),
    timeout=settings.OPENAI_TIMEOUT,
)


def is_flagged(text: str) -> bool:
    """Return True if the moderation endpoint flags the text."""
    resp = _client.moderations.create(model=_MODERATION_MODEL, input=text)
    return bool(resp.results[0].flagged)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/ai/test_moderation.py -q
```

Expected: `2 passed`.

- [ ] Verify lint:

```
uv run ruff check app/ai/moderation.py tests/ai/test_moderation.py
```

- [ ] Commit:

```
git add app/ai/moderation.py tests/ai/test_moderation.py
git commit -m "feat: add OpenAI moderation gate is_flagged"
```

### Task P4.8: AI generator (Protocol, OpenAIGenerator via .parse, FakeGenerator, build_generator)

**Files:**
- Create: `app/ai/generator.py`
- Test: `tests/ai/test_generator.py`

- [ ] Write failing test `tests/ai/test_generator.py` (FakeGenerator pure; OpenAIGenerator via respx-mocked `chat.completions.parse` structured-output response; build_generator switch via env):

```python
import json
from datetime import datetime, timezone

import httpx
import respx

from app.ai.generator import FakeGenerator, OpenAIGenerator, build_generator
from app.ai.schemas import PostDraft
from app.models.news_item import NewsItem


def _news() -> NewsItem:
    return NewsItem(
        title="Уряд оголосив нові вибори",
        url="https://example.com/a",
        summary="Деталі про дату та умови проведення виборів.",
        source="Example",
        published_at=datetime.now(timezone.utc),
        raw_text="Повний текст новини про вибори.",
        content_hash="hash-gen-1",
    )


def test_fake_generator_returns_postdraft():
    draft = FakeGenerator().generate(_news())
    assert isinstance(draft, PostDraft)
    assert draft.text
    assert draft.language


@respx.mock
def test_openai_generator_parses_structured_output():
    parsed = PostDraft(
        text="🗳️ Уряд оголосив нові вибори! Стежте за оновленнями.",
        language="uk",
        hashtags=["#вибори"],
    )
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": parsed.model_dump_json(),
                            "refusal": None,
                            "parsed": json.loads(parsed.model_dump_json()),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )
    draft = OpenAIGenerator().generate(_news())
    assert isinstance(draft, PostDraft)
    assert draft.language == "uk"
    assert "вибори" in draft.text.casefold()


def test_build_generator_returns_fake_when_flagged(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AI", "1")
    gen = build_generator()
    assert isinstance(gen, FakeGenerator)
```

- [ ] Run — expect FAIL:

```
uv run pytest tests/ai/test_generator.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.ai.generator'`.

- [ ] Implement `app/ai/generator.py`:

```python
import os
from typing import Protocol

from openai import OpenAI

from app.ai.schemas import PostDraft
from app.core.config import settings
from app.models.news_item import NewsItem

_SYSTEM_PROMPT = (
    "Ти — редактор Telegram-каналу новин. На основі новини напиши лаконічний пост "
    "мовою джерела (uk/ru/en, тією ж, що й новина). Додай доречні емодзі та короткий "
    f"call-to-action. Довжина суворо не більше {settings.POST_MAX_LEN} символів. "
    "Поверни структуру: text (готовий пост), language (код мови), hashtags (список)."
)

# Module-level client (one per worker).
_client = OpenAI(
    api_key=settings.OPENAI_API_KEY.get_secret_value(),
    timeout=settings.OPENAI_TIMEOUT,
)


def _user_prompt(news: NewsItem) -> str:
    return (
        f"Заголовок: {news.title}\n"
        f"Опис: {news.summary or ''}\n"
        f"Текст: {news.raw_text or ''}\n"
        f"Джерело: {news.source}\n"
        f"URL: {news.url or ''}"
    )


class PostGenerator(Protocol):
    def generate(self, news: NewsItem) -> PostDraft: ...


class OpenAIGenerator:
    """Structured-output generator via openai chat.completions.parse."""

    def generate(self, news: NewsItem) -> PostDraft:
        completion = _client.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            temperature=0.75,
            max_completion_tokens=280,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(news)},
            ],
            response_format=PostDraft,
        )
        message = completion.choices[0].message
        if getattr(message, "refusal", None) or message.parsed is None:
            raise ValueError("OpenAI refused or returned no parsed output")
        return message.parsed


class FakeGenerator:
    """Deterministic generator for tests / offline mode (no network)."""

    def generate(self, news: NewsItem) -> PostDraft:
        return PostDraft(
            text=f"📰 {news.title}. Деталі за посиланням. Підписуйтесь!",
            language="uk",
            hashtags=[],
        )


def build_generator() -> PostGenerator:
    """Select generator: FakeGenerator when USE_FAKE_AI is set, else OpenAIGenerator."""
    if os.getenv("USE_FAKE_AI") == "1":
        return FakeGenerator()
    return OpenAIGenerator()
```

- [ ] Run — expect PASS:

```
uv run pytest tests/ai/test_generator.py -q
```

Expected: `3 passed`.

- [ ] Verify lint:

```
uv run ruff check app/ai/generator.py tests/ai/test_generator.py
```

- [ ] Commit:

```
git add app/ai/generator.py tests/ai/test_generator.py
git commit -m "feat: add PostGenerator protocol + OpenAI/Fake generators"
```

### Task P4.9: Pipeline task filter_item (passes_filters → news_id | None)

**Files:**
- Modify: `app/tasks/pipeline.py`
- Test: `tests/tasks/__init__.py`, `tests/tasks/test_filter_item.py`

- [ ] Create `tests/tasks/__init__.py` (empty).
- [ ] Write failing test `tests/tasks/test_filter_item.py` (DB session fixture `db` from conftest; patch redis + keywords lookup at the pipeline boundary):

```python
from datetime import datetime, timezone

import fakeredis

from app.models.news_item import NewsItem
from app.tasks import pipeline


def _persist_news(db, title: str, content_hash: str) -> NewsItem:
    item = NewsItem(
        title=title,
        url="https://example.com/a",
        summary=title,
        source="Example",
        published_at=datetime.now(timezone.utc),
        raw_text=title,
        content_hash=content_hash,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_filter_item_passes_returns_news_id(db, monkeypatch):
    item = _persist_news(db, "Сьогодні відбулося багато виборів", "h-pass")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out == str(item.id)


def test_filter_item_dropped_returns_none(db, monkeypatch):
    item = _persist_news(db, "Сьогодні гарна погода в місті", "h-drop")
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(pipeline, "_redis", lambda: fakeredis.FakeStrictRedis())
    monkeypatch.setattr(pipeline, "_load_keywords", lambda s: [_FakeKw("вибори")])

    out = pipeline.filter_item.run(str(item.id))
    assert out is None


class _FakeKw:
    def __init__(self, word: str, lang: str | None = None):
        self.word = word
        self.lang = lang


class db_ctx:
    """Wrap a test Session so `with SessionLocal() as s:` yields it without closing."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False
```

- [ ] Run — expect FAIL (filter_item not yet defined / `pipeline` module missing helpers):

```
uv run pytest tests/tasks/test_filter_item.py -q
```

Expected: `AttributeError`/`ModuleNotFoundError` (FAIL).

- [ ] Implement/extend `app/tasks/pipeline.py` — add the dedup/keywords helpers and `filter_item`. (This task adds only the filter portion; `generate_post` is added in P4.10. If `pipeline.py` does not yet exist, create it with the imports below; the `collect_sources`/`parse_source`/`publish_post` stubs are owned by other phases — only add what this phase requires and leave existing tasks untouched.)

```python
import redis as redis_lib
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.filter.service import passes_filters
from app.models.keyword import Keyword
from app.models.news_item import NewsItem
from app.tasks.celery_app import celery_app


def _redis() -> redis_lib.Redis:
    return redis_lib.Redis.from_url(settings.REDIS_URL)


def _load_keywords(session) -> list[Keyword]:
    return list(session.execute(select(Keyword)).scalars().all())


@celery_app.task(name="app.tasks.pipeline.filter_item")
def filter_item(news_id: str) -> str | None:
    """Run filter gate. Returns news_id to continue the chain, or None to stop."""
    with SessionLocal() as session:
        item = session.get(NewsItem, news_id)
        if item is None:
            return None
        keywords = _load_keywords(session)
        ok = passes_filters(item, keywords, _redis(), settings)
        return news_id if ok else None
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_filter_item.py -q
```

Expected: `2 passed`.

- [ ] Verify lint:

```
uv run ruff check app/tasks/pipeline.py tests/tasks/test_filter_item.py
```

- [ ] Commit:

```
git add app/tasks/pipeline.py tests/tasks/__init__.py tests/tasks/test_filter_item.py
git commit -m "feat: add filter_item pipeline task"
```

### Task P4.10: Pipeline task generate_post (generate→moderation→Post(generated); flag→failed+ErrorLog)

**Files:**
- Modify: `app/tasks/pipeline.py`
- Test: `tests/tasks/test_generate_post.py`

- [ ] Write failing test `tests/tasks/test_generate_post.py` (mock `build_generator` + `is_flagged` + length guard; assert Post(generated) on clean path, and Post(failed)+ErrorLog on moderation flag):

```python
from datetime import datetime, timezone

from app.ai.schemas import PostDraft
from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline


class db_ctx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


def _persist_news(db) -> NewsItem:
    item = NewsItem(
        title="Уряд оголосив нові вибори",
        url="https://example.com/a",
        summary="Деталі.",
        source="Example",
        published_at=datetime.now(timezone.utc),
        raw_text="Повний текст.",
        content_hash="h-gen",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class _Gen:
    def __init__(self, draft):
        self._draft = draft

    def generate(self, news):
        return self._draft


def test_generate_post_creates_generated(db, monkeypatch):
    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline, "build_generator",
        lambda: _Gen(PostDraft(text="🗳️ Нові вибори! Підписуйтесь.", language="uk")),
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: False)

    post_id = pipeline.generate_post.run(str(item.id))

    post = db.get(Post, post_id)
    assert post is not None
    assert post.status == PostStatus.generated
    assert post.generated_text


def test_generate_post_moderation_flag_marks_failed_and_logs(db, monkeypatch):
    item = _persist_news(db)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    monkeypatch.setattr(
        pipeline, "build_generator",
        lambda: _Gen(PostDraft(text="заборонений зміст", language="uk")),
    )
    monkeypatch.setattr(pipeline, "is_flagged", lambda text: True)

    post_id = pipeline.generate_post.run(str(item.id))

    post = db.get(Post, post_id)
    assert post.status == PostStatus.failed
    logs = db.query(ErrorLog).filter_by(stage=ErrorStage.generate, news_id=item.id).all()
    assert len(logs) == 1


def test_generate_post_none_input_skips(db, monkeypatch):
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_ctx(db))
    assert pipeline.generate_post.run(None) is None
```

- [ ] Run — expect FAIL (`generate_post`, `mark_generated`, `mark_failed` not yet wired):

```
uv run pytest tests/tasks/test_generate_post.py -q
```

Expected: `AttributeError` (FAIL).

- [ ] Extend `app/tasks/pipeline.py` — add `generate_post` (imports for state helpers + generator + moderation). Append these imports/task to the file created in P4.9; `state.mark_generated`/`mark_failed` are provided by the tasks-state phase, imported here.

```python
from app.ai.generator import build_generator
from app.ai.moderation import is_flagged
from app.models.post import Post
from app.tasks.state import mark_failed, mark_generated
from app.models.base import ErrorStage


@celery_app.task(name="app.tasks.pipeline.generate_post")
def generate_post(news_id: str | None) -> str | None:
    """Generate a post for a NewsItem.

    None input -> early return (chain stopped upstream).
    Happy path: generate -> moderation -> length guard -> Post(status=generated).
    On any failure: Post(status=failed) + ErrorLog(stage=generate). Returns post_id.
    """
    if news_id is None:
        return None

    with SessionLocal() as session:
        item = session.get(NewsItem, news_id)
        if item is None:
            return None

        post = Post(news_id=item.id, generated_text="", status=None)
        session.add(post)
        session.flush()  # assign post.id for FK/ErrorLog wiring

        try:
            draft = build_generator().generate(item)
            text = draft.text
            if is_flagged(text):
                raise ValueError("moderation flagged generated text")
            if not text or len(text) > settings.POST_MAX_LEN:
                raise ValueError("generated text empty or exceeds POST_MAX_LEN")
            mark_generated(session, post, text)
        except Exception as exc:  # noqa: BLE001 — log every failure, never raise out
            mark_failed(
                session,
                post=post,
                stage=ErrorStage.generate,
                message=str(exc),
                news_id=item.id,
            )
        session.commit()
        return str(post.id)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_generate_post.py -q
```

Expected: `3 passed`.

- [ ] Run the full Phase-4 suite to confirm no regressions:

```
uv run pytest tests/filter tests/ai tests/tasks -q
```

Expected: all green.

- [ ] Verify lint:

```
uv run ruff check app/tasks/pipeline.py tests/tasks/test_generate_post.py
```

- [ ] Commit:

```
git add app/tasks/pipeline.py tests/tasks/test_generate_post.py
git commit -m "feat: add generate_post task with moderation + length guard"
```

---


## Phase 5 — Publish + Celery Pipeline

### Task P5.1: Telegram publisher (`_publish` async + `publish` sync wrapper)

**Files:**
- Create: `app/telegram/__init__.py`
- Create: `app/telegram/publisher.py`
- Test: `tests/telegram/__init__.py`
- Test: `tests/telegram/test_publisher.py`

Steps:

- [ ] Create empty package marker `app/telegram/__init__.py` (empty file) and `tests/telegram/__init__.py` (empty file).
- [ ] Write the failing test `tests/telegram/test_publisher.py`. We patch the aiogram `Bot` so no network is hit; `publish` must call `asyncio.run(_publish(...))`, enter `async with Bot(...)`, call `send_message(chat_id=..., text=...)`, and return the resulting `message_id`.

```python
from unittest.mock import AsyncMock, MagicMock, patch

from app.telegram import publisher


def _fake_bot_cm(send_message_mock):
    """Build a Bot() return value that works as an async context manager."""
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=False)
    bot.send_message = send_message_mock
    return bot


def test_publish_sends_and_returns_message_id():
    sent = MagicMock()
    sent.message_id = 4242
    send_message = AsyncMock(return_value=sent)
    bot = _fake_bot_cm(send_message)

    with patch.object(publisher, "Bot", return_value=bot) as bot_cls:
        result = publisher.publish(-1009999, "<b>hi</b>")

    assert result == 4242
    # Bot constructed with the token (positional) inside the coroutine
    assert bot_cls.call_count == 1
    send_message.assert_awaited_once()
    kwargs = send_message.await_args.kwargs
    assert kwargs["chat_id"] == -1009999
    assert kwargs["text"] == "<b>hi</b>"


def test_publish_propagates_send_errors():
    send_message = AsyncMock(side_effect=RuntimeError("boom"))
    bot = _fake_bot_cm(send_message)

    with patch.object(publisher, "Bot", return_value=bot):
        try:
            publisher.publish(-100123, "x")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("expected RuntimeError to propagate")
```

- [ ] Run it — expect FAIL (module `app.telegram.publisher` does not yet exist / `AttributeError`):

```
uv run pytest tests/telegram/test_publisher.py -q
```

Expected: collection/import error or failures (no `publisher.publish`).

- [ ] Minimal implementation `app/telegram/publisher.py`. Bot is created **inside the coroutine** (aiohttp session bound to the loop), `async with` to avoid "Unclosed session"; sync wrapper uses `asyncio.run`.

```python
import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings


async def _publish(channel_id: int, text: str) -> int:
    bot = Bot(
        settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    async with bot:
        message = await bot.send_message(chat_id=channel_id, text=text)
    return message.message_id


def publish(channel_id: int, text: str) -> int:
    return asyncio.run(_publish(channel_id, text))
```

- [ ] Run — expect PASS:

```
uv run pytest tests/telegram/test_publisher.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/telegram tests/telegram
git add app/telegram tests/telegram
git commit -m "feat: add write-only aiogram telegram publisher"
```

### Task P5.2: Post state-machine (`mark_generated` / `mark_published` / `mark_failed` + ErrorLog)

**Files:**
- Create: `app/tasks/__init__.py`
- Create: `app/tasks/state.py`
- Test: `tests/tasks/__init__.py`
- Test: `tests/tasks/test_state.py`

Steps:

- [ ] Create empty `app/tasks/__init__.py` and `tests/tasks/__init__.py`.
- [ ] Write failing test `tests/tasks/test_state.py`. It uses the function-scoped `db` session fixture from `conftest.py`. Covers: `mark_generated` sets text + status; `mark_published` sets status, `tg_message_id`, `published_at`; `mark_failed` sets `Post.status=failed`, `error`, and inserts an `ErrorLog` row with the right `stage`/ids.

```python
import uuid
from datetime import datetime, timezone

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import state


def _make_post(db) -> Post:
    news = NewsItem(
        title="t",
        url="https://e.com/a",
        summary="s",
        source="src",
        published_at=datetime.now(timezone.utc),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.flush()
    post = Post(news_id=news.id, generated_text="", status=PostStatus.new)
    db.add(post)
    db.flush()
    return post


def test_mark_generated_sets_text_and_status(db):
    post = _make_post(db)
    state.mark_generated(db, post, "hello world")
    db.refresh(post)
    assert post.status == PostStatus.generated
    assert post.generated_text == "hello world"


def test_mark_published_sets_message_id_and_timestamp(db):
    post = _make_post(db)
    state.mark_generated(db, post, "hello")
    state.mark_published(db, post, 9988)
    db.refresh(post)
    assert post.status == PostStatus.published
    assert post.tg_message_id == 9988
    assert post.published_at is not None


def test_mark_failed_sets_status_and_writes_error_log(db):
    post = _make_post(db)
    state.mark_failed(
        db,
        post=post,
        stage=ErrorStage.publish,
        message="forbidden",
        tb="trace...",
        news_id=post.news_id,
    )
    db.refresh(post)
    assert post.status == PostStatus.failed
    assert post.error == "forbidden"

    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
    assert logs[0].message == "forbidden"
    assert logs[0].traceback == "trace..."
    assert logs[0].post_id == post.id
    assert logs[0].news_id == post.news_id


def test_mark_failed_without_post_only_logs(db):
    state.mark_failed(
        db,
        stage=ErrorStage.parse,
        message="parse boom",
        source_id=uuid.uuid4(),
    )
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.parse
    assert logs[0].post_id is None
```

- [ ] Run it — expect FAIL (no `app.tasks.state`):

```
uv run pytest tests/tasks/test_state.py -q
```

- [ ] Implement `app/tasks/state.py`. All status changes live here (single state-machine module per spec §9). Each mutates the passed `Post` and commits; `mark_failed` always writes an `ErrorLog` row and, if a `post` is given, flips it to `failed` with `error` in the same transaction.

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.post import Post


def mark_generated(db: Session, post: Post, text: str) -> None:
    post.generated_text = text
    post.status = PostStatus.generated
    db.commit()


def mark_published(db: Session, post: Post, message_id: int) -> None:
    post.tg_message_id = message_id
    post.status = PostStatus.published
    post.published_at = datetime.now(timezone.utc)
    db.commit()


def mark_failed(
    db: Session,
    *,
    post: Post | None = None,
    stage: ErrorStage,
    message: str,
    tb: str | None = None,
    source_id=None,
    news_id=None,
) -> None:
    if post is not None:
        post.status = PostStatus.failed
        post.error = message
        if news_id is None:
            news_id = post.news_id
    log = ErrorLog(
        stage=stage,
        source_id=source_id,
        news_id=news_id,
        post_id=post.id if post is not None else None,
        message=message,
        traceback=tb,
    )
    db.add(log)
    db.commit()
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_state.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/tasks/state.py tests/tasks/test_state.py
git add app/tasks/__init__.py app/tasks/state.py tests/tasks/__init__.py tests/tasks/test_state.py
git commit -m "feat: add post state-machine with error-log writes"
```

### Task P5.3: Celery app + full configuration (`app/tasks/celery_app.py`)

**Files:**
- Create: `app/tasks/celery_app.py`
- Test: `tests/tasks/test_celery_app.py`

Steps:

- [ ] Write failing test `tests/tasks/test_celery_app.py`. Asserts the exact conf required by the contract: json serializers, UTC, `task_ignore_result`, `acks_late`, prefetch=1, soft/hard time limits, `visibility_timeout` (> hard limit, invariant §4.2), `task_routes` for the `tg` queue, and the `*/30` beat schedule.

```python
from app.tasks.celery_app import celery_app


def test_serialization_and_utc():
    conf = celery_app.conf
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"
    assert "json" in conf.accept_content
    assert conf.timezone == "UTC"
    assert conf.enable_utc is True


def test_reliability_flags():
    conf = celery_app.conf
    assert conf.task_ignore_result is True
    assert conf.task_acks_late is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.broker_connection_retry_on_startup is True


def test_time_limits_and_visibility_timeout():
    conf = celery_app.conf
    assert conf.task_soft_time_limit == 120
    assert conf.task_time_limit == 150
    vis = conf.broker_transport_options["visibility_timeout"]
    # invariant: visibility_timeout > longest hard time limit
    assert vis > conf.task_time_limit
    assert vis == 3600


def test_publish_post_routed_to_tg_queue():
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.pipeline.publish_post"] == {"queue": "tg"}


def test_beat_schedule_every_30_minutes():
    sched = celery_app.conf.beat_schedule
    entry = sched["collect"]
    assert entry["task"] == "app.tasks.pipeline.collect_sources"
    crontab = entry["schedule"]
    assert crontab.minute == {0, 30}
    assert "app.tasks.pipeline" in set(celery_app.conf.include)
```

- [ ] Run it — expect FAIL (no `app.tasks.celery_app`):

```
uv run pytest tests/tasks/test_celery_app.py -q
```

- [ ] Implement `app/tasks/celery_app.py`. Standalone Celery app (worker does not import FastAPI). `include` points at `pipeline` so tasks register. `visibility_timeout=3600` > `task_time_limit=150` (invariant §4.2).

```python
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "m4",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=120,
    task_time_limit=150,
    broker_transport_options={"visibility_timeout": 3600},
    task_routes={
        # publish_post always on the tg queue (single-client constraint).
        # parse_source is routed per-source at CALL time by collect_sources
        # (queue="tg" for tg sources), so it needs no static route here.
        "app.tasks.pipeline.publish_post": {"queue": "tg"},
    },
    beat_schedule={
        "collect": {
            "task": "app.tasks.pipeline.collect_sources",
            "schedule": crontab(minute="*/30"),
        },
    },
)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_celery_app.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/tasks/celery_app.py tests/tasks/test_celery_app.py
git add app/tasks/celery_app.py tests/tasks/test_celery_app.py
git commit -m "feat: add standalone celery app with full reliability conf"
```

### Task P5.4: `publish_post` task — idempotent publish + error mapping (acceptance §13 #8)

**Files:**
- Create: `app/tasks/pipeline.py`
- Test: `tests/tasks/test_publish_post.py`

> Note: this task creates `pipeline.py` with only the `publish_post` task plus a short-circuit-safe stub for the chain neighbours. P5.5 adds `collect_sources`. (`parse_source`, `filter_item`, `generate_post` come from earlier phases; if `pipeline.py` already exists from a prior phase, ADD `publish_post` to it instead of recreating — keep the existing tasks intact.)

Steps:

- [ ] Write failing test `tests/tasks/test_publish_post.py`. Three cases per acceptance #8: (a) `status==generated` → publishes once, stores `tg_message_id`, status `published`; (b) idempotent — second run on an already-`published` Post is a **no-op** (`publish` patched, asserted called exactly once total across both runs); (c) `TelegramForbidden` → `status=failed` + one `ErrorLog`, no retry. `publish_post` reads the post id and re-opens its own session, so the test patches `SessionLocal` in the pipeline module to hand back the test session.

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.models.base import ErrorStage, PostStatus
from app.models.error_log import ErrorLog
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline


@pytest.fixture
def generated_post(db):
    news = NewsItem(
        title="t",
        url="https://e.com/a",
        summary="s",
        source="src",
        published_at=datetime.now(timezone.utc),
        raw_text="r",
        content_hash=uuid.uuid4().hex,
    )
    db.add(news)
    db.flush()
    post = Post(news_id=news.id, generated_text="ready text", status=PostStatus.generated)
    db.add(post)
    db.commit()
    return post


def _patch_session(db):
    """Make pipeline.SessionLocal() yield the test session (no real close)."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_publish_post_publishes_generated(generated_post, db):
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", return_value=7777
    ) as pub:
        pipeline.publish_post.run(str(generated_post.id))

    pub.assert_called_once()
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.published
    assert generated_post.tg_message_id == 7777


def test_publish_post_is_idempotent(generated_post, db):
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", return_value=7777
    ) as pub:
        pipeline.publish_post.run(str(generated_post.id))
        pipeline.publish_post.run(str(generated_post.id))  # second run = no-op

    pub.assert_called_once()  # published exactly once total
    db.refresh(generated_post)
    assert generated_post.status == PostStatus.published
    assert generated_post.tg_message_id == 7777


def test_publish_post_none_is_skip(db):
    with _patch_session(db), patch.object(pipeline.publisher, "publish") as pub:
        pipeline.publish_post.run(None)
    pub.assert_not_called()


def test_publish_post_forbidden_marks_failed_and_logs(generated_post, db):
    err = TelegramForbiddenError(method=MagicMock(), message="bot kicked")
    with _patch_session(db), patch.object(
        pipeline.publisher, "publish", side_effect=err
    ):
        pipeline.publish_post.run(str(generated_post.id))

    db.refresh(generated_post)
    assert generated_post.status == PostStatus.failed
    logs = db.query(ErrorLog).all()
    assert len(logs) == 1
    assert logs[0].stage == ErrorStage.publish
    assert logs[0].post_id == generated_post.id
```

- [ ] Run it — expect FAIL (no `app.tasks.pipeline` / no `publish_post`):

```
uv run pytest tests/tasks/test_publish_post.py -q
```

- [ ] Implement `app/tasks/pipeline.py` with `publish_post`. IDEMPOTENT: re-reads the Post in its own session, publishes **only** when `status == generated`, persists `tg_message_id` in the same transaction (invariant §4.1). `TelegramForbiddenError`/`TelegramBadRequest` → `mark_failed` (no retry); `TelegramRetryAfter`/`TelegramServerError` → re-raise into Celery retry. `None` arg short-circuits (chain stop).

```python
import traceback

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramServerError,
)

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.base import ErrorStage, PostStatus
from app.models.post import Post
from app.tasks import state
from app.tasks.celery_app import celery_app
from app.telegram import publisher


@celery_app.task(
    bind=True,
    autoretry_for=(TelegramRetryAfter, TelegramServerError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def publish_post(self, post_id: str | None) -> None:
    if post_id is None:
        return
    with SessionLocal() as db:
        post = db.get(Post, post_id)
        if post is None or post.status != PostStatus.generated:
            return  # idempotent: only publish a generated post
        try:
            message_id = publisher.publish(
                settings.TELEGRAM_CHANNEL_ID, post.generated_text
            )
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            state.mark_failed(
                db,
                post=post,
                stage=ErrorStage.publish,
                message=str(exc),
                tb=traceback.format_exc(),
            )
            return
        state.mark_published(db, post, message_id)
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_publish_post.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/tasks/pipeline.py tests/tasks/test_publish_post.py
git add app/tasks/pipeline.py tests/tasks/test_publish_post.py
git commit -m "feat: add idempotent publish_post celery task with error mapping"
```

### Task P5.5: `collect_sources` task — Redis lock + per-source enqueue

**Files:**
- Modify: `app/tasks/pipeline.py`
- Test: `tests/tasks/test_collect_sources.py`

Steps:

- [ ] Write failing test `tests/tasks/test_collect_sources.py`. Uses `fakeredis` for the lock and patches `parse_source.apply_async`. Asserts: lock key `m4:lock:collect` is acquired with `nx=True, ex=...`, `parse_source.apply_async` is called once per **enabled** Source (disabled skipped) with `queue="tg"` for tg sources and `queue="default"` otherwise, and a second run while the lock is held is a no-op.

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from app.models.base import SourceType
from app.models.source import Source
from app.tasks import pipeline


@pytest.fixture
def mixed_sources(db):
    rows = [
        Source(type=SourceType.site, name="a", url="https://a.com/rss", enabled=True),
        Source(type=SourceType.tg, name="b", url="@b", enabled=True),
        Source(type=SourceType.site, name="c", url="https://c.com/rss", enabled=False),
    ]
    db.add_all(rows)
    db.commit()
    return rows


def _patch_session(db):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_collect_sources_locks_and_routes_per_type(mixed_sources, db):
    fake = fakeredis.FakeStrictRedis()
    with _patch_session(db), patch.object(
        pipeline, "get_redis", return_value=fake
    ), patch.object(pipeline.parse_source, "apply_async") as enq:
        pipeline.collect_sources.run()

    assert enq.call_count == 2  # only enabled sources
    routed = {c.args[0][0]: c.kwargs["queue"] for c in enq.call_args_list}
    by_id = {str(s.id): s for s in mixed_sources}
    assert set(routed) == {sid for sid, s in by_id.items() if s.enabled}
    for sid, queue in routed.items():
        expected = "tg" if by_id[sid].type == SourceType.tg else "default"
        assert queue == expected  # tg sources -> single-client tg queue


def test_collect_sources_noop_when_lock_held(mixed_sources, db):
    fake = fakeredis.FakeStrictRedis()
    fake.set("m4:lock:collect", "1", nx=True, ex=300)  # pre-acquire
    with _patch_session(db), patch.object(
        pipeline, "get_redis", return_value=fake
    ), patch.object(pipeline.parse_source, "apply_async") as enq:
        pipeline.collect_sources.run()

    enq.assert_not_called()  # lock held → no enqueue
```

- [ ] Run it — expect FAIL (no `collect_sources` / no `get_redis` / no `parse_source` in pipeline):

```
uv run pytest tests/tasks/test_collect_sources.py -q
```

- [ ] Add to `app/tasks/pipeline.py`: a `get_redis()` helper, the `LOCK_KEY` constant, and the `collect_sources` task. **Acquires `m4:lock:collect` via `SET NX EX`** (invariant §4: lock against overlapping cycles); only when acquired does it enqueue `parse_source.apply_async((source_id,), queue=...)` for each enabled Source (tg→`tg` queue, else `default`). Add these imports/helpers at the top of the module and the task at the end.

Add to the imports block:

```python
import redis as redis_lib
from sqlalchemy import select

from app.models.base import SourceType
from app.models.source import Source
```

Add the lock constant + redis helper (after the imports):

```python
LOCK_KEY = "m4:lock:collect"
LOCK_TTL_SECONDS = 25 * 60  # < beat interval (30m), > a full cycle


def get_redis():
    return redis_lib.Redis.from_url(settings.REDIS_URL)
```

Add the task:

```python
@celery_app.task
def collect_sources() -> None:
    r = get_redis()
    acquired = r.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS)
    if not acquired:
        return  # previous cycle still running
    with SessionLocal() as db:
        sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
        for source in sources:
            # tg sources MUST run on the single-concurrency tg worker (Telethon
            # single-client constraint); site/RSS sources go to the default queue.
            queue = "tg" if source.type == SourceType.tg else "default"
            parse_source.apply_async((str(source.id),), queue=queue)
```

> `parse_source` is defined in the parser phase. If it is not yet present when this phase runs standalone, add a minimal stub task `@celery_app.task def parse_source(source_id: str) -> None: ...` to keep the module importable; the real body comes from the parser phase. The test patches `parse_source.apply_async`, so the body is irrelevant to this test.

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_collect_sources.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/tasks/pipeline.py tests/tasks/test_collect_sources.py
git add app/tasks/pipeline.py tests/tasks/test_collect_sources.py
git commit -m "feat: add collect_sources orchestrator with redis lock"
```

### Task P5.6: Chain short-circuit on None — `filter_item | generate_post | publish_post`

**Files:**
- Modify: `app/tasks/pipeline.py`
- Test: `tests/tasks/test_chain_shortcircuit.py`

> This task guarantees the contract: a `None` return from any task makes the next task early-return so the chain dies. `publish_post`'s `None` guard already exists (P5.4). Here we ensure `generate_post` also early-returns on `None` (filter dropped the item). If `generate_post` is owned by an earlier phase, this task only ADDS the `if news_id is None: return None` guard at its top and the wiring test; do not rewrite its body.

Steps:

- [ ] Write failing test `tests/tasks/test_chain_shortcircuit.py`. Verifies the `None` propagation directly at task level (no broker): `filter_item` returning `None` → `generate_post(None)` returns `None` without generating → `publish_post(None)` is a no-op.

```python
from unittest.mock import patch

from app.tasks import pipeline


def test_generate_post_skips_on_none():
    # generate_post must not touch the DB or generator when fed None
    with patch.object(pipeline, "SessionLocal") as sl:
        result = pipeline.generate_post.run(None)
    assert result is None
    sl.assert_not_called()


def test_chain_dies_when_filter_returns_none():
    # simulate the chain hand-off: filter -> None -> generate -> None -> publish
    gen_out = pipeline.generate_post.run(None)
    assert gen_out is None
    with patch.object(pipeline.publisher, "publish") as pub:
        pub_out = pipeline.publish_post.run(gen_out)
    assert pub_out is None
    pub.assert_not_called()
```

- [ ] Run it — expect FAIL if `generate_post` lacks the `None` guard (it would hit `SessionLocal`), otherwise it pins behaviour:

```
uv run pytest tests/tasks/test_chain_shortcircuit.py -q
```

- [ ] Ensure `generate_post` early-returns on `None`. The guard must be the **first** statement of the task body (before any session/generator use):

```python
@celery_app.task
def generate_post(news_id: str | None) -> str | None:
    if news_id is None:
        return None  # filter dropped the item: short-circuit the chain
    # ... existing generation body (owned by the AI/generate phase) ...
```

> If `generate_post` does not yet exist in this repo when Phase 5 runs, add a minimal version that satisfies the short-circuit only — the full generation body is delivered by the generate phase and must keep this guard at the top:

```python
@celery_app.task
def generate_post(news_id: str | None) -> str | None:
    if news_id is None:
        return None
    raise NotImplementedError  # real body provided by the generate phase
```

- [ ] Run — expect PASS:

```
uv run pytest tests/tasks/test_chain_shortcircuit.py -q
```

- [ ] Lint + commit:

```
uv run ruff check app/tasks/pipeline.py tests/tasks/test_chain_shortcircuit.py
git add app/tasks/pipeline.py tests/tasks/test_chain_shortcircuit.py
git commit -m "feat: short-circuit pipeline chain on None propagation"
```

### Task P5.7: Eager end-to-end pipeline wiring (acceptance §13 #9)

**Files:**
- Test: `tests/tasks/test_pipeline_eager.py`

> Pure test task — verifies the full `chain(filter_item | generate_post | publish_post)` runs end-to-end under `task_always_eager` on fakes, from a real `NewsItem` through to a `published` Post with a stored `tg_message_id`. No network: generator is `FakeGenerator`, moderation patched to pass, redis is `fakeredis`, `publisher.publish` patched.

Steps:

- [ ] Write the test `tests/tasks/test_pipeline_eager.py`. Sets `task_always_eager=True` + `task_eager_propagates=True` for the duration; patches `SessionLocal`, the generator builder, moderation, redis, and `publisher.publish`. Drives a Celery `chain` and asserts the Post ends `published` with the fake message id.

```python
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from celery import chain

from app.ai.generator import FakeGenerator
from app.models.base import PostStatus
from app.models.news_item import NewsItem
from app.models.post import Post
from app.tasks import pipeline
from app.tasks.celery_app import celery_app


@pytest.fixture
def eager():
    prev = celery_app.conf.task_always_eager, celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager, celery_app.conf.task_eager_propagates = prev


@pytest.fixture
def news(db):
    item = NewsItem(
        title="OpenAI ships thing",
        url="https://e.com/openai",
        summary="A summary with the keyword python in it",
        source="src",
        published_at=datetime.now(timezone.utc),
        raw_text="full text about python and ai",
        content_hash=uuid.uuid4().hex,
    )
    db.add(item)
    db.commit()
    return item


def _patch_session(db):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db)
    cm.__exit__ = MagicMock(return_value=False)
    return patch.object(pipeline, "SessionLocal", return_value=cm)


def test_eager_chain_news_to_published(eager, news, db):
    import fakeredis

    fake = fakeredis.FakeStrictRedis()

    with _patch_session(db), \
        patch.object(pipeline, "get_redis", return_value=fake), \
        patch.object(pipeline, "passes_filters", return_value=True), \
        patch.object(pipeline, "build_generator", return_value=FakeGenerator()), \
        patch.object(pipeline, "is_flagged", return_value=False), \
        patch.object(pipeline.publisher, "publish", return_value=5150) as pub:

        flow = chain(
            pipeline.filter_item.s(str(news.id)),
            pipeline.generate_post.s(),
            pipeline.publish_post.s(),
        )
        flow.apply()  # eager, in-process

    pub.assert_called_once()
    post = db.query(Post).filter(Post.news_id == news.id).one()
    assert post.status == PostStatus.published
    assert post.tg_message_id == 5150
    assert post.generated_text  # non-empty
```

- [ ] Run it — expect FAIL until `filter_item` + `generate_post` are fully wired (these bodies belong to the filter/generate phases). In a standalone Phase 5 run the test documents the required end-state and will pass once those phases land:

```
uv run pytest tests/tasks/test_pipeline_eager.py -q
```

Expected (standalone): FAIL/ERROR on missing `passes_filters`/`build_generator`/`is_flagged` symbols imported into `pipeline.py`. Expected (full plan): PASS.

- [ ] Ensure `pipeline.py` imports the collaborators referenced by the test so they are patchable on the module (these are the names the filter/generate phases provide). Confirm the import block of `app/tasks/pipeline.py` includes:

```python
from app.ai.generator import build_generator
from app.ai.moderation import is_flagged
from app.filter.service import passes_filters
```

- [ ] Run — expect PASS (under the full plan):

```
uv run pytest tests/tasks/test_pipeline_eager.py -q
```

- [ ] Verify the whole tasks suite together, then commit:

```
uv run pytest tests/tasks -q
uv run ruff check tests/tasks/test_pipeline_eager.py
git add tests/tasks/test_pipeline_eager.py
git commit -m "test: eager end-to-end pipeline wiring from news to published"
```

---


## Phase 6 — Ops, Docker, CI

### Task P6.1: Multi-stage Dockerfile (uv, python:3.12-slim, non-root)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/Dockerfile`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/.dockerignore`

Steps:
- [ ] Create `.dockerignore` to keep the build context small and prevent secrets/venv leaking into the image:

```
.git
.gitignore
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.ruff_cache
.mypy_cache
.env
*.session
*.session-journal
app.db
tests
docs
.github
README.md
```

- [ ] Create `Dockerfile` — single multi-stage uv image, `python:3.12-slim`, non-root, `UV_COMPILE_BYTECODE=1`, cache-mounted `uv sync --frozen`. The same image is reused by api/worker/beat/flower via a different `command:` in compose:

```dockerfile
# syntax=docker/dockerfile:1

#############################
# Builder: resolve + install deps with uv
#############################
FROM python:3.12-slim AS builder

# uv binary (pinned tag for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached layer): only lockfile + manifest.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project source and install the project itself.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

#############################
# Runtime: slim, non-root
#############################
FROM python:3.12-slim AS runtime

# Non-root user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Copy the resolved virtualenv and the application code from the builder.
COPY --from=builder --chown=app:app /app /app

# Make the venv the default interpreter; bytecode already compiled.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

# Default command runs the API; compose overrides for worker/beat/flower.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] Verify the Dockerfile parses (syntax + stage graph) without performing a full build:

```bash
docker build --check -f Dockerfile .
```

- [ ] Commit:

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add multi-stage uv Dockerfile and dockerignore

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P6.2: docker-compose.yml (db, redis, migrate, api, workers, beat, flower)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/docker-compose.yml`

Steps:
- [ ] Create `docker-compose.yml`. All services share the one image built from the Dockerfile (`build: .`) and differ only by `command:`. `db`/`redis` carry healthchecks; `migrate` is a one-shot `alembic upgrade head`; everything depending on stateful services waits on `service_healthy`; `migrate` is awaited via `service_completed_successfully`. Queues follow the contract: `worker-default` serves `default`, `worker-tg` serves `tg` with `concurrency=1`:

```yaml
name: m4

x-app-image: &app-image
  build:
    context: .
    dockerfile: Dockerfile
  image: m4-app:latest

x-app-env: &app-env
  ENVIRONMENT: prod
  DATABASE_URL: postgresql+psycopg://m4:m4@db:5432/m4
  REDIS_URL: redis://redis:6379/0
  OPENAI_API_KEY: ${OPENAI_API_KEY}
  OPENAI_MODEL: ${OPENAI_MODEL:-gpt-4o-mini}
  TELEGRAM_API_ID: ${TELEGRAM_API_ID}
  TELEGRAM_API_HASH: ${TELEGRAM_API_HASH}
  TELETHON_STRING_SESSION: ${TELETHON_STRING_SESSION}
  TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
  TELEGRAM_CHANNEL_ID: ${TELEGRAM_CHANNEL_ID}

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: m4
      POSTGRES_PASSWORD: m4
      POSTGRES_DB: m4
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U m4 -d m4"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "6379:6379"

  migrate:
    <<: *app-image
    command: ["alembic", "upgrade", "head"]
    environment:
      <<: *app-env
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  api:
    <<: *app-image
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    environment:
      <<: *app-env
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health').status==200 else sys.exit(1)"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully

  worker-default:
    <<: *app-image
    command: ["celery", "-A", "app.tasks.celery_app", "worker", "-Q", "default", "-c", "4", "-l", "info"]
    environment:
      <<: *app-env
    depends_on:
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully

  worker-tg:
    <<: *app-image
    command: ["celery", "-A", "app.tasks.celery_app", "worker", "-Q", "tg", "-c", "1", "-l", "info"]
    environment:
      <<: *app-env
    depends_on:
      redis:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully

  beat:
    <<: *app-image
    command: ["celery", "-A", "app.tasks.celery_app", "beat", "-l", "info"]
    environment:
      <<: *app-env
    depends_on:
      redis:
        condition: service_healthy

  flower:
    <<: *app-image
    command: ["celery", "-A", "app.tasks.celery_app", "flower", "--port=5555"]
    environment:
      <<: *app-env
    ports:
      - "5555:5555"
    depends_on:
      redis:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] Verify compose is structurally valid (interpolates and resolves the full config). Provide dummy env so required `${...}` vars interpolate:

```bash
OPENAI_API_KEY=x TELEGRAM_API_ID=1 TELEGRAM_API_HASH=x TELETHON_STRING_SESSION=x TELEGRAM_BOT_TOKEN=x TELEGRAM_CHANNEL_ID=1 docker compose config >/dev/null && echo OK
```

- [ ] Commit:

```bash
git add docker-compose.yml
git commit -m "chore: add docker-compose with db/redis/migrate/api/workers/beat/flower

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P6.3: scripts/login.py — Telethon StringSession minting

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/scripts/login.py`
- Create: `/home/jarvis/Programming/ai-post-generated-bot/scripts/__init__.py`

Steps:
- [ ] Create `scripts/__init__.py` (empty package marker so `python -m scripts.login` works):

```python
```

- [ ] Create `scripts/login.py` — interactive one-shot that authenticates an interactive Telethon login and prints the resulting `StringSession` string for pasting into `.env` as `TELETHON_STRING_SESSION`. It reads `api_id`/`api_hash` from env (falling back to prompts) and never persists the session to disk:

```python
"""Mint a Telethon StringSession interactively.

Usage:
    uv run python -m scripts.login

Reads TELEGRAM_API_ID / TELEGRAM_API_HASH from the environment (or .env via
the running shell); prompts for the phone number + login code (and 2FA
password if enabled), then prints the StringSession to stdout. Copy it into
your .env as TELETHON_STRING_SESSION. The session is never written to disk.
"""

from __future__ import annotations

import os

from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> None:
    api_id_raw = os.environ.get("TELEGRAM_API_ID") or input("api_id: ").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH") or input("api_hash: ").strip()
    api_id = int(api_id_raw)

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()

    print("\n=== TELETHON_STRING_SESSION (paste into .env, keep secret) ===")
    print(session_string)


if __name__ == "__main__":
    main()
```

- [ ] Verify the script imports and exposes `main` without launching the interactive flow:

```bash
uv run python -c "import scripts.login as m; assert callable(m.main); print('OK')"
```

- [ ] Lint the new files:

```bash
uv run ruff check scripts/
```

- [ ] Commit:

```bash
git add scripts/__init__.py scripts/login.py
git commit -m "feat: add scripts/login.py for interactive Telethon StringSession minting

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P6.4: GitHub Actions CI (ruff + pytest with postgres/redis + docker build smoke)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/.github/workflows/ci.yml`

Steps:
- [ ] Create `.github/workflows/ci.yml`. Three jobs: `lint` (ruff check + format check), `test` (pytest with postgres + redis service containers and the env the test suite needs), and `docker` (build smoke of the image). All use `uv` via the official `astral-sh/setup-uv` action with caching:

```yaml
name: ci

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --frozen
      - name: ruff check
        run: uv run ruff check .
      - name: ruff format --check
        run: uv run ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: m4
          POSTGRES_PASSWORD: m4
          POSTGRES_DB: m4
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U m4 -d m4"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgresql+psycopg://m4:m4@localhost:5432/m4
      REDIS_URL: redis://localhost:6379/0
      OPENAI_API_KEY: test
      TELEGRAM_API_ID: "1"
      TELEGRAM_API_HASH: test
      TELETHON_STRING_SESSION: test
      TELEGRAM_BOT_TOKEN: test
      TELEGRAM_CHANNEL_ID: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --frozen
      - name: alembic upgrade head
        run: uv run alembic upgrade head
      - name: pytest
        run: uv run pytest -q

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: docker build smoke
        uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: m4-app:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] Verify the workflow is valid YAML and parses:

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"
```

- [ ] Commit:

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add ruff + pytest (postgres/redis) + docker build smoke workflow

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task P6.5: README.md stub (skeleton, filled after implementation)

**Files:**
- Create: `/home/jarvis/Programming/ai-post-generated-bot/README.md`

Steps:
- [ ] Create `README.md` as a stub: title + an explicit "filled after implementation" note + the section skeleton (overview, why-sync note placeholder, quickstart, env table, API examples, checklist mapping, architecture). The body is intentionally left as placeholders to be completed in the post-implementation documentation pass:

```markdown
# M4 — AI-генератор постів для Telegram

> **СТАТУС:** заповнюється після реалізації. Це структурний кістяк README;
> розділи нижче доповнюються фінальним текстом, прикладами та командами на
> завершальному кроці плану (post-implementation docs pass).

## Огляд

<!-- TODO(після реалізації): що це за сервіс, що робить за розкладом, як збирає
новини, фільтрує, генерує AI-пост і публікує в Telegram-канал. Керування через REST. -->

## Чому sync-стек (нотатка)

<!-- TODO(після реалізації): пояснити свідомий вибір sync SQLAlchemy/FastAPI def-роутів
+ sync OpenAI у Celery-тасках; чому async тут не дає виграшу і ускладнює. -->

## Швидкий старт

<!-- TODO(після реалізації):
1. cp .env.example .env та заповнити секрети
2. uv run python -m scripts.login → TELETHON_STRING_SESSION у .env
3. docker compose up --build
4. відкрити http://localhost:8000/docs та http://localhost:5555 (flower)
-->

## Змінні середовища

<!-- TODO(після реалізації): таблиця env-змінних. -->

| Змінна | Тип | За замовчуванням | Опис |
|---|---|---|---|
| `ENVIRONMENT` | `local`/`prod` | `local` | режим |
| `DATABASE_URL` | str | `sqlite:///./app.db` | БД (postgres у compose) |
| `REDIS_URL` | str | `redis://localhost:6379/0` | брокер/стор/дедуп/lock |
| `OPENAI_API_KEY` | secret | — | ключ OpenAI |
| `OPENAI_MODEL` | str | `gpt-4o-mini` | модель |
| `OPENAI_TIMEOUT` | int | `30` | таймаут OpenAI, сек |
| `TELEGRAM_API_ID` | int | — | Telethon api_id |
| `TELEGRAM_API_HASH` | secret | — | Telethon api_hash |
| `TELETHON_STRING_SESSION` | secret | — | сесія читача (scripts/login.py) |
| `TELEGRAM_BOT_TOKEN` | secret | — | BotFather-токен паблішера |
| `TELEGRAM_CHANNEL_ID` | int | — | цільовий канал публікації |
| `ALLOWED_LANGUAGES` | list | `["uk","ru","en"]` | мовний фільтр |
| `DEDUP_TTL_SECONDS` | int | `604800` | TTL seen-set, сек |
| `KEYWORD_MATCH_MODE` | `any`/`all` | `any` | семантика keyword-фільтра |
| `POST_MAX_LEN` | int | `4096` | ліміт довжини поста |

## Приклади API

<!-- TODO(після реалізації): curl-приклади для
- POST /api/v1/sources, GET /api/v1/sources
- POST /api/v1/keywords
- GET /api/v1/posts?status=failed
- POST /api/v1/generate
- GET /api/v1/errors
- GET /health
-->

## Відповідність acceptance-критеріям (§13 спеки)

<!-- TODO(після реалізації): таблиця 1..11 критерій → тест(и), що його покривають. -->

| # | Критерій | Тести |
|---|---|---|
| 1 | Sources CRUD | TODO |
| 2 | Keywords CRUD | TODO |
| 3 | GET /api/posts envelope + ?status | TODO |
| 4 | POST /api/generate 202 + Post | TODO |
| 5 | Parse RSS + UNIQUE content_hash | TODO |
| 6 | Filter (dedup/мова/keyword-лема) | TODO |
| 7 | Generate → Post(generated)/moderation→failed | TODO |
| 8 | Publish idempotent + tg_message_id | TODO |
| 9 | Pipeline wiring (eager) | TODO |
| 10 | Telethon reader resolve+cache/min_id | TODO |
| 11 | Error history GET /api/errors | TODO |

## Архітектура

<!-- TODO(після реалізації): діаграма процесів (api, worker-default, worker-tg,
beat, redis, db, flower), Celery-canvas пайплайн, поділ Telethon(read)/aiogram(publish),
жорсткі інваріанти ідемпотентності. -->
```

- [ ] Verify the README exists and is non-empty:

```bash
test -s README.md && echo OK
```

- [ ] Commit:

```bash
git add README.md
git commit -m "docs: add README stub skeleton (filled after implementation)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---
