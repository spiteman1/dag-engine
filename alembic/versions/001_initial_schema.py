"""Initial schema -- creates dag_definitions, task_definitions, and task_runs tables.

Revision ID: 001
Revises: 
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- dag_definitions ---
    op.create_table(
        "dag_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
    )

    # --- task_definitions ---
    op.create_table(
        "task_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dag_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False, server_default="[]"),
    )

    # --- task_runs ---
    op.create_table(
        "task_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("task_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dag_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("worker_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes for common query patterns
    op.create_index("ix_task_runs_dag_run_id", "task_runs", ["dag_run_id"])
    op.create_index("ix_task_runs_status", "task_runs", ["status"])
    op.create_index("ix_task_definitions_dag_id", "task_definitions", ["dag_id"])


def downgrade() -> None:
    op.drop_table("task_runs")
    op.drop_table("task_definitions")
    op.drop_table("dag_definitions")
