"""
alembic/env.py - Alembic migration environment configured for async SQLAlchemy.

Standard Alembic env.py uses synchronous database connections.
We override it here to use asyncio + asyncpg, matching our application stack.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Import our models so Alembic's autogenerate can detect them
# ---------------------------------------------------------------------------
# This import must happen before target_metadata is set.
# Alembic inspects Base.metadata to know what tables should exist.
from dag_engine.core.config import settings
from dag_engine.db.base import Base
from dag_engine.db import models  # noqa: F401 -- registers models on Base.metadata

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

# Dynamically override the database URL using application settings.
# This prevents Alembic from falling back to hardcoded localhost:5432 in alembic.ini
# when running inside Docker containers or different deployment environments.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object that contains our table definitions
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode -- generates SQL without a live DB.
    Useful for reviewing what Alembic would do, or for DBAs who apply
    migrations manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Synchronous migration runner -- called from the async wrapper."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using an async engine.
    This is the async equivalent of the default synchronous approach.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # NullPool disables connection pooling for migrations -- each migration
        # gets a fresh connection and closes it immediately after. Safe for
        # one-off schema operations.
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations -- wraps the async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
