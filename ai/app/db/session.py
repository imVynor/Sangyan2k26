"""Database engine and session management for SANGYAN PostgreSQL backend.

Supports:
- AsyncSession for runtime repository access.
- Sync engine for Alembic migrations and administrative scripts.
- Configurable via settings.database_url (defaults to environment variables).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from ai.app.config.settings import settings

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None

_sync_engine: Any | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def get_connection_url(sync: bool = False) -> str:
    """Retrieve database URL from settings, converting driver format if needed."""
    url = settings.database_url
    if not url:
        raise ValueError(
            "DATABASE_URL is not configured. Please set DATABASE_URL environment variable."
        )

    # Normalize driver prefix for psycopg v3
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    
    if sync:
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    else:
        # Async driver with psycopg v3
        if url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            
    return url


def get_async_engine() -> AsyncEngine:
    """Get or create singleton AsyncEngine."""
    global _async_engine, _async_session_factory
    if _async_engine is None:
        url = get_connection_url(sync=False)
        _async_engine = create_async_engine(
            url,
            echo=settings.database_echo,
            future=True,
            pool_pre_ping=True,
        )
        _async_session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_engine


def get_sync_engine() -> Any:
    """Get or create singleton sync Engine for migrations."""
    global _sync_engine, _sync_session_factory
    if _sync_engine is None:
        url = get_connection_url(sync=True)
        _sync_engine = create_engine(
            url,
            echo=settings.database_echo,
            future=True,
            pool_pre_ping=True,
        )
        _sync_session_factory = sessionmaker(
            bind=_sync_engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sync_engine


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide transactional async session scope."""
    get_async_engine()
    assert _async_session_factory is not None
    session: AsyncSession = _async_session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
