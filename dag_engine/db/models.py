"""
db/models.py - SQLAlchemy ORM models for the three core database tables.

Defines DagDefinition, TaskDefinition, and TaskRun as Python classes
that map directly to PostgreSQL tables. Also defines the Enum types
that enforce valid status values at the database level.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dag_engine.db.base import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
# Using str + Enum means each member IS a string, so FastAPI serialises
# them directly to JSON without any extra configuration.

class DagStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TaskRunStatus(str, Enum):
    PENDING = "PENDING"    # Created but not yet queued
    QUEUED = "QUEUED"      # Pushed to the Redis task queue
    RUNNING = "RUNNING"    # A worker has claimed this task
    SUCCESS = "SUCCESS"    # Task completed successfully
    FAILED = "FAILED"      # Task encountered an error


# ---------------------------------------------------------------------------
# DagDefinition
# ---------------------------------------------------------------------------
# Represents a DAG blueprint -- the definition of a workflow.
# One DagDefinition can be triggered (run) many times.
class DagDefinition(Base):
    __tablename__ = "dag_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        # uuid4() generates a random UUID on each insert.
        # Using UUIDs instead of sequential integers avoids predictable IDs
        # and is safer for distributed systems where multiple writers exist.
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        # Always store timestamps in UTC. Never local time.
    )
    status: Mapped[DagStatus] = mapped_column(
        String(20),
        default=DagStatus.ACTIVE,
        nullable=False,
    )

    # One DAG has many tasks
    tasks: Mapped[list["TaskDefinition"]] = relationship(
        "TaskDefinition",
        back_populates="dag",
        cascade="all, delete-orphan",
        # cascade="all, delete-orphan" means deleting a DAG automatically
        # deletes all its task definitions. No orphaned rows left behind.
    )

    def __repr__(self) -> str:
        return f"<DagDefinition id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# TaskDefinition
# ---------------------------------------------------------------------------
# Represents a single task within a DAG blueprint.
# Stores what command to run and which other tasks must complete first.
class TaskDefinition(Base):
    __tablename__ = "task_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dag_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    dependencies: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        # Stores a JSON array of task names that must succeed before
        # this task can run. e.g. ["extract_data", "validate_schema"]
        # We use names (strings) not UUIDs here for human readability
        # in the API payload. The worker resolves names to IDs at runtime.
    )

    # Many tasks belong to one DAG
    dag: Mapped["DagDefinition"] = relationship(
        "DagDefinition", back_populates="tasks"
    )

    # One task definition can have many run instances
    runs: Mapped[list["TaskRun"]] = relationship(
        "TaskRun",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TaskDefinition id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# TaskRun
# ---------------------------------------------------------------------------
# Represents a single execution instance of a TaskDefinition.
# Every time a DAG is triggered, a TaskRun is created for each task.
# This is the table that tracks real-time execution state.
class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    dag_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        # A UUID generated at DAG trigger time, shared by all TaskRuns
        # in the same execution. Groups runs together without needing
        # a separate DagRun table.
    )
    status: Mapped[TaskRunStatus] = mapped_column(
        String(20),
        default=TaskRunStatus.PENDING,
        nullable=False,
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        # Populated when a worker claims the task.
        # Tells us which worker instance ran which task.
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Many runs belong to one task definition
    task: Mapped["TaskDefinition"] = relationship(
        "TaskDefinition", back_populates="runs"
    )

    def __repr__(self) -> str:
        return f"<TaskRun id={self.id} status={self.status!r}>"
