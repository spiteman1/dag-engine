"""add_dagrun_table_and_error_columns

Revision ID: 002
Revises: 001
Create Date: 2026-09-15

Changes:
    1. Creates the 'dag_runs' table with id, dag_id, status, started_at, finished_at.
    2. Adds 'error_message' column to 'task_runs' table.
    3. Converts 'task_runs.dag_run_id' from a bare UUID column to a proper
       foreign key referencing 'dag_runs.id'.

Why in this order:
    The dag_runs table must be created BEFORE the FK is added to task_runs,
    otherwise PostgreSQL will reject the constraint as referencing a
    non-existent table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# Revision identifiers used by Alembic to chain migrations together.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # Step 1: Create the dag_runs table
    # ----------------------------------------------------------------
    # This must happen before we add the FK constraint on task_runs.dag_run_id.
    op.create_table(
        "dag_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dag_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dag_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="RUNNING",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index on dag_id for fast "give me all runs for this DAG" queries
    op.create_index(
        "ix_dag_runs_dag_id",
        "dag_runs",
        ["dag_id"],
    )

    # ----------------------------------------------------------------
    # Step 2: Add error_message column to task_runs
    # ----------------------------------------------------------------
    # Nullable because most tasks succeed and never populate this field.
    op.add_column(
        "task_runs",
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    # ----------------------------------------------------------------
    # Step 3: Convert task_runs.dag_run_id to a proper FK
    # ----------------------------------------------------------------
    # The column already exists from migration 001, but had no FK constraint.
    # We add the FK now that the dag_runs table exists to reference.
    op.create_foreign_key(
        "fk_task_runs_dag_run_id",      # constraint name
        "task_runs",                    # source table
        "dag_runs",                     # referenced table
        ["dag_run_id"],                 # source columns
        ["id"],                         # referenced columns
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Reverse in the opposite order: remove the FK before dropping the table

    # Step 3 (reversed): Drop the FK constraint on task_runs.dag_run_id
    op.drop_constraint("fk_task_runs_dag_run_id", "task_runs", type_="foreignkey")

    # Step 2 (reversed): Drop the error_message column
    op.drop_column("task_runs", "error_message")

    # Step 1 (reversed): Drop the dag_runs table and its index
    op.drop_index("ix_dag_runs_dag_id", table_name="dag_runs")
    op.drop_table("dag_runs")
