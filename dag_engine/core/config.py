"""
core/config.py - Central application configuration.

Loads settings from environment variables or a .env file using pydantic-settings.
All other modules import from here -- connection strings never get hardcoded.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    pydantic-settings automatically reads each field from a matching
    environment variable (case-insensitive). If a .env file exists,
    it reads from there too. Explicit environment variables always
    take priority over .env file values.

    Example .env file:
        DATABASE_URL=postgresql+asyncpg://dag_user:dag_password@localhost:5432/dag_engine
        REDIS_URL=redis://localhost:6379
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+asyncpg://dag_user:dag_password@localhost:5432/dag_engine"
    )
    # The +asyncpg part is SQLAlchemy's dialect prefix. It tells SQLAlchemy
    # to use the asyncpg driver for the underlying TCP connection to Postgres.
    # Swap "localhost" for "postgres" when running inside Docker Compose,
    # since containers reach each other by service name, not localhost.

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379"
    # Local dev default -- workers connect here to pop tasks from the queue.
    # Swap "localhost" for "redis" when running inside Docker Compose.

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    WORKER_ID: str = "worker-1"
    # Identifies which worker instance processed a task.
    # When we run multiple workers in parallel, each gets a unique ID
    # so we can trace which machine handled which task in the database.

    TASK_QUEUE_NAME: str = "task_queue"
    # The Redis list key that workers pop from and the API pushes to.
    # Centralised here so it never gets out of sync between the API
    # and worker if we ever rename it.

    BRPOP_TIMEOUT: int = 5
    # How many seconds BRPOP waits before returning None if the queue
    # is empty. Gives the worker a natural loop point to check for
    # shutdown signals rather than blocking forever (timeout=0).

    WORKER_HEARTBEAT_INTERVAL: int = 10
    # Number of seconds between heartbeat pings sent by the worker to Redis.

    WORKER_HEARTBEAT_TTL: int = 30
    # Time-To-Live (in seconds) for the worker's heartbeat key in Redis.
    # If a worker process abruptly dies (OOM, SIGKILL, hardware failure),
    # Redis will automatically expire the key after this window, signaling
    # to the Reaper that the worker is dead.

    class Config:
        # Tells pydantic-settings to look for a .env file in the
        # current working directory and load values from it.
        env_file = ".env"
        env_file_encoding = "utf-8"
        # extra = "ignore" means unrecognised env vars won't cause errors.
        # Useful when your shell has many env vars set globally.
        extra = "ignore"


# ----------------------------------------------------------------------
# Module-level singleton.
#
# Instantiated once when this module is first imported. Every other
# module does:
#     from dag_engine.core.config import settings
#     print(settings.DATABASE_URL)
#
# This is the Python equivalent of a Spring @Configuration singleton bean.
# ----------------------------------------------------------------------
settings = Settings()
