"""
api/routes/dags.py - FastAPI route handlers for DAG operations.

Three endpoints:
    POST /dags                   -- Create and validate a new DAG definition
    POST /dags/{dag_id}/run      -- Trigger a DAG execution
    GET  /dags/{dag_id}/status   -- Real-time status of all tasks in a DAG run
"""

import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dag_engine.api.schemas import (
    DagCreate,
    DagResponse,
    DagRunTriggerResponse,
    DagStatusResponse,
    TaskRunResponse,
)
from dag_engine.core.config import settings
from dag_engine.core.graph import detect_cycles, topological_sort
from dag_engine.db.base import get_db
from dag_engine.db.models import DagDefinition, TaskDefinition, TaskRun, TaskRunStatus

router = APIRouter(prefix="/dags", tags=["DAGs"])


# ---------------------------------------------------------------------------
# Dependency: get_redis
# ---------------------------------------------------------------------------
# Provides an async Redis connection per request, cleaned up afterwards.
async def get_redis() -> aioredis.Redis:
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# POST /dags
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=DagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new DAG definition",
)
async def create_dag(
    payload: DagCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts a DAG definition with tasks and their dependencies.

    Runs cycle detection before persisting anything to the database.
    If a cycle is found, returns 422 with a descriptive error.
    """
    # Step 1: Validate the graph -- reject before touching the database
    task_dicts = [
        {"name": t.name, "dependencies": t.dependencies} for t in payload.tasks
    ]
    if detect_cycles(task_dicts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cycle detected in DAG definition. "
                "Ensure no task directly or indirectly depends on itself."
            ),
        )

    # Step 2: Check for duplicate DAG name
    existing = await db.execute(
        select(DagDefinition).where(DagDefinition.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A DAG with name '{payload.name}' already exists.",
        )

    # Step 3: Persist the DAG and its tasks
    dag = DagDefinition(
        name=payload.name,
        description=payload.description,
    )
    db.add(dag)
    await db.flush()
    # flush() sends the INSERT to the database within the current transaction
    # without committing, so dag.id is now populated for use in task creation.

    for task_data in payload.tasks:
        task = TaskDefinition(
            dag_id=dag.id,
            name=task_data.name,
            command=task_data.command,
            dependencies=task_data.dependencies,
        )
        db.add(task)

    await db.commit()
    await db.refresh(dag)

    # Reload with tasks relationship populated
    result = await db.execute(
        select(DagDefinition)
        .where(DagDefinition.id == dag.id)
        .options(selectinload(DagDefinition.tasks))
    )
    dag = result.scalar_one()

    return dag


# ---------------------------------------------------------------------------
# POST /dags/{dag_id}/run
# ---------------------------------------------------------------------------
@router.post(
    "/{dag_id}/run",
    response_model=DagRunTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a DAG execution",
)
async def run_dag(
    dag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Triggers an execution of the specified DAG.

    1. Loads the DAG and its tasks from the database.
    2. Runs topological sort to determine execution order and parallelism.
    3. Creates TaskRun records for all tasks (status=PENDING).
    4. Identifies root tasks (no dependencies), marks them QUEUED,
       and pushes their TaskRun IDs to the Redis task queue.
    """
    # Load DAG with tasks
    result = await db.execute(
        select(DagDefinition)
        .where(DagDefinition.id == dag_id)
        .options(selectinload(DagDefinition.tasks))
    )
    dag = result.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DAG with id '{dag_id}' not found.",
        )

    # Build task dicts for graph algorithms
    task_dicts = [
        {"name": t.name, "dependencies": t.dependencies} for t in dag.tasks
    ]

    # Compute execution tiers
    tiers = topological_sort(task_dicts)

    # Shared run ID groups all TaskRuns from this trigger together
    dag_run_id = uuid.uuid4()

    # Map task name -> TaskDefinition for quick lookup
    task_by_name = {t.name: t for t in dag.tasks}

    # Create TaskRun records for every task in PENDING state
    task_runs: dict[str, TaskRun] = {}
    for task in dag.tasks:
        run = TaskRun(
            task_id=task.id,
            dag_run_id=dag_run_id,
            status=TaskRunStatus.PENDING,
        )
        db.add(run)
        task_runs[task.name] = run

    await db.flush()  # Populate all run.id values before queuing

    # Root tasks = tasks in tier 0 (no dependencies) -- start immediately
    root_task_names = tiers[0] if tiers else []
    queued_task_names = []

    for task_name in root_task_names:
        run = task_runs[task_name]
        run.status = TaskRunStatus.QUEUED
        # Push the TaskRun ID to Redis so a worker can claim it
        await redis.lpush(settings.TASK_QUEUE_NAME, str(run.id))
        queued_task_names.append(task_name)

    await db.commit()

    return DagRunTriggerResponse(
        dag_run_id=dag_run_id,
        dag_id=dag_id,
        message=f"DAG '{dag.name}' triggered successfully.",
        queued_tasks=queued_task_names,
        execution_tiers=tiers,
    )


# ---------------------------------------------------------------------------
# GET /dags/{dag_id}/status
# ---------------------------------------------------------------------------
@router.get(
    "/{dag_id}/status",
    response_model=DagStatusResponse,
    summary="Get real-time status of all tasks in a DAG",
)
async def get_dag_status(
    dag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current execution status of every TaskRun for the given DAG.
    Shows all runs across all triggers.
    """
    result = await db.execute(
        select(DagDefinition)
        .where(DagDefinition.id == dag_id)
        .options(
            selectinload(DagDefinition.tasks).selectinload(TaskDefinition.runs)
        )
    )
    dag = result.scalar_one_or_none()
    if not dag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DAG with id '{dag_id}' not found.",
        )

    task_runs = []
    for task in dag.tasks:
        for run in task.runs:
            task_runs.append(
                TaskRunResponse(
                    id=run.id,
                    task_id=run.task_id,
                    task_name=task.name,
                    status=run.status,
                    worker_id=run.worker_id,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
            )

    return DagStatusResponse(dag_id=dag_id, dag_name=dag.name, task_runs=task_runs)
