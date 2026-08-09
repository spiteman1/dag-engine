"""
db/base.py - SQLAlchemy async engine, declarative base, and session factory.

This is the foundation that all models and database operations build on.
Nothing in the application touches the database without going through here.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from dag_engine.core.config import settings

# ---------------------------------------------------------------------------
# Async Engine
# ---------------------------------------------------------------------------
# The engine manages the connection pool to PostgreSQL.
# echo=True logs every SQL statement -- useful during development,
# set to False in production via an environment variable.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    # pool_pre_ping=True tests each connection from the pool before use.
    # Prevents "connection was closed" errors after periods of inactivity.
)

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
# async_sessionmaker is a factory that produces AsyncSession instances.
# expire_on_commit=False means SQLAlchemy won't expire loaded attributes
# after a commit -- important for async code where lazy loading doesn't work.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
# All SQLAlchemy ORM models inherit from this class.
# It provides the metadata registry that Alembic reads to generate migrations.
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency: get_db
# ---------------------------------------------------------------------------
# An async generator used as a FastAPI dependency.
# Yields a database session and guarantees it is closed after the request,
# even if an exception is raised.
#
# Usage in a route:
#     async def my_route(db: AsyncSession = Depends(get_db)):
#         ...
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
