"""
db/models.py - SQLAlchemy ORM models for the four core database tables.

Defines DagDefinition, DagRun, TaskDefinition, and TaskRun as Python classes
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
    UniqueConstraint,
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


class DagRunStatus(str, Enum):
    RUNNING = "RUNNING"   # DAG is actively executing
    SUCCESS = "SUCCESS"   # All tasks completed successfully
    FAILED = "FAILED"     # At least one task failed


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

    # One DAG definition can have many execution run instances
    runs: Mapped[list["DagRun"]] = relationship(
        "DagRun",
        back_populates="dag",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DagDefinition id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# DagRun
# ---------------------------------------------------------------------------
# Represents a single execution instance of a DagDefinition.
# Every time POST /dags/{id}/run is called, one DagRun row is created.
#
# Previously, dag_run_id was just a bare UUID threaded through TaskRun rows
# with no backing table. This model gives us a single authoritative row to:
#   - Query the overall status of a pipeline execution
#   - Record when the run started and finished
#   - Understand run-level metadata without aggregating TaskRun rows
class DagRun(Base):
    __tablename__ = "dag_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dag_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[DagRunStatus] = mapped_column(
        String(20),
        default=DagRunStatus.RUNNING,
        nullable=False,
        # Starts as RUNNING when triggered.
        # Transitions to SUCCESS when all TaskRuns succeed, or
        # FAILED when any TaskRun fails.
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Each DagRun belongs to one DagDefinition
    dag: Mapped["DagDefinition"] = relationship(
        "DagDefinition", back_populates="runs"
    )

    # Each DagRun has many TaskRun instances (one per task in the DAG)
    task_runs: Mapped[list["TaskRun"]] = relationship(
        "TaskRun",
        back_populates="dag_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DagRun id={self.id} status={self.status!r}>"


# ---------------------------------------------------------------------------
# TaskDefinition
# ---------------------------------------------------------------------------
# Represents a single task within a DAG blueprint.
# Stores what command to run and which other tasks must complete first.
class TaskDefinition(Base):
    __tablename__ = "task_definitions"

    # Compound unique constraint: task names must be unique WITHIN a DAG.
    # Two different DAGs can both have a task called "clean_data", but
    # a single DAG cannot have two tasks sharing the same name.
    #
    # Why this matters: the worker resolves dependencies by matching task
    # names (strings) at runtime. If two tasks in the same DAG share a
    # name, the worker finds multiple matches and the dependency check
    # becomes ambiguous, leading to tasks running prematurely or deadlocking.
    __table_args__ = (
        UniqueConstraint("dag_id", "name", name="uq_task_definition_dag_id_name"),
    )

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
        ForeignKey("dag_runs.id", ondelete="CASCADE"),
        nullable=False,
        # Foreign key to the DagRun row that spawned this TaskRun.
        # Every task in a single pipeline execution shares the same dag_run_id,
        # linking them all back to one authoritative DagRun record.
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
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # Stores the exception message when a task fails.
        # Persisting this in the database means the error survives log rotation
        # and is visible directly in GET /dags/{id}/status API responses.
    )

    # Many runs belong to one task definition
    task: Mapped["TaskDefinition"] = relationship(
        "TaskDefinition", back_populates="runs"
    )

    # Each TaskRun belongs to one DagRun execution instance
    dag_run: Mapped["DagRun"] = relationship(
        "DagRun", back_populates="task_runs"
    )

    def __repr__(self) -> str:
        return f"<TaskRun id={self.id} status={self.status!r}>"
