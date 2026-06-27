"""
Async SQLAlchemy engine and session factory.

Usage:
    # Application startup
    await init_engine(settings)

    # FastAPI dependency
    async with get_session() as session:
        ...

    # Application shutdown
    await close_engine()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from src.config import Settings

# Module-level singletons; set by init_engine()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    return _session_factory


async def init_engine(settings: Settings) -> None:
    """Create the async engine and session factory. Called once at startup."""
    global _engine, _session_factory

    _engine = create_async_engine(
        str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,         # detect stale connections
        pool_recycle=3600,          # recycle connections after 1 hour
        echo=settings.database_echo_sql,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,     # avoid lazy-load after commit
        autoflush=False,
        autocommit=False,
    )


async def close_engine() -> None:
    """Dispose the engine pool. Called once at shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager that yields a single AsyncSession.
    Commits on clean exit, rolls back on exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency (use via Depends).

    Example:
        @router.get("/")
        async def handler(session: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with get_session() as session:
        yield session


# Alias used in api/deps.py
get_db_session = _get_session_dependency
