"""Alembic migration environment — async SQLAlchemy with autogenerate support.

Run migrations:
    alembic upgrade head

Create a new revision:
    alembic revision --autogenerate -m "describe_change"
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the backend package root (parent of this alembic/ dir) is on sys.path
# so that `from src.*` imports work regardless of the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base so all ORM models are registered before autogenerate introspects.
from src.infrastructure.database.base import Base
import src.infrastructure.database.models  # noqa: F401 — registers all models

config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """
    Prefer DATABASE_URL from environment (set by CI / docker-compose).
    Falls back to alembic.ini sqlalchemy.url.
    """
    import os
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    # Alembic's sync runner needs the sync driver
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def run_migrations_offline() -> None:
    """Run in 'offline' mode — output SQL without connecting."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (online mode)."""
    import os
    configuration = config.get_section(config.config_ini_section, {})
    # Use the raw async URL — _get_url() strips +asyncpg which breaks async_engine_from_config
    configuration["sqlalchemy.url"] = (
        os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    )
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
