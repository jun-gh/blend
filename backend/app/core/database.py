"""Async database engine and session management.

Local dev  → SQLite via aiosqlite
Production → Neon Serverless Postgres via asyncpg

The module auto-detects the driver from the DATABASE_URL scheme.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_db_url = settings.database_url
_engine_kwargs: dict = {"echo": settings.debug}

if _db_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif "asyncpg" in _db_url:
    # asyncpg does not support libpq query parameters like channel_binding, sslmode, etc.
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(_db_url)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        # asyncpg recognizes ssl (or sslmode transformed to ssl)
        clean_params = {}
        for k, v in query_params.items():
            if k in ("sslmode", "ssl"):
                clean_params["ssl"] = ["require" if "require" in v[0] else v[0]]
            elif k not in ("channel_binding", "target_session_attrs", "options"):
                clean_params[k] = v
        _db_url = urlunparse(parsed._replace(query=urlencode(clean_params, doseq=True)))

engine = create_async_engine(_db_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Base ORM class
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Create all tables on startup (idempotent)."""
    # Import models so they are registered with Base.metadata
    from app.models import orm  # noqa: F401  – side-effect import

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            from sqlalchemy import text
            await conn.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                    USING fts5(content, content='chunks', content_rowid='id')
                    """
                )
            )
    log.info("Database initialised.")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a DB session per request."""
    async with async_session_factory() as session:
        yield session
