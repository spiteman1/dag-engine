"""
worker/worker.py - Standalone async worker node.

Run as many instances of this script as needed for parallelism:
    python -m dag_engine.worker.worker

Each instance:
    1. Connects to Redis and PostgreSQL
    2. Blocks on BRPOP waiting for task IDs
    3. Claims the task (sets status=RUNNING)
    4. Simulates execution with asyncio.sleep()
    5. Marks the task SUCCESS
    6. Checks if any downstream tasks are now unblocked
    7. If yes, queues them in Redis and repeats
"""

import asyncio
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from dag_engine.core.config import settings
from dag_engine.db.base import AsyncSessionLocal
from dag_engine.db.models import TaskDefinition, TaskRun, TaskRunStatus

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(f"worker.{settings.WORKER_ID}")


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
class Worker:
    """
    A single async worker node that processes tasks from the Redis queue.

    Designed to run indefinitely until a SIGINT or SIGTERM is received,
    at which point it finishes the current task and shuts down cleanly.
    """

    def __init__(self):
        self.worker_id = settings.WORKER_ID
        self.running = True
        self.redis: aioredis.Redis | None = None

    async def start(self):
        """Main entry point -- connects to dependencies and starts the loop."""
        logger.info(f"Worker '{self.worker_id}' starting up...")

        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )

        # Graceful shutdown on SIGINT (Ctrl+C) and SIGTERM (Docker stop)
        #
        # loop.add_signal_handler() is a Unix-only API. On Windows, the
        # ProactorEventLoop raises NotImplementedError. We skip it there
        # and instead catch KeyboardInterrupt in _run_loop() below.
        # This is the same pattern uvicorn uses internally.
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._handle_shutdown)

        logger.info(f"Worker '{self.worker_id}' connected. Listening for tasks...")
        await self._run_loop()

    def _handle_shutdown(self):
        """Called on SIGINT/SIGTERM -- sets the stop flag."""
        logger.info(f"Worker '{self.worker_id}' received shutdown signal. Finishing current task...")
        self.running = False

    async def _run_loop(self):
        """Continuously pops tasks from Redis and processes them."""
        while self.running:
            try:
                # BRPOP blocks for up to BRPOP_TIMEOUT seconds.
                # Returns (queue_name, task_run_id) or None on timeout.
                result = await self.redis.brpop(
                    settings.TASK_QUEUE_NAME,
                    timeout=settings.BRPOP_TIMEOUT,
                )

                if result is None:
                    # Timeout -- no tasks available, loop and check running flag
                    continue

                _, task_run_id_str = result
                task_run_id = uuid.UUID(task_run_id_str)

                logger.info(f"Claimed task run: {task_run_id}")
                await self._process_task(task_run_id)

            except KeyboardInterrupt:
                # Windows fallback: Ctrl+C raises KeyboardInterrupt directly
                # since we can't use add_signal_handler on ProactorEventLoop.
                # On Unix this path is never hit because SIGINT is caught
                # by the signal handler which sets self.running = False.
                logger.info(f"Worker '{self.worker_id}' received KeyboardInterrupt. Shutting down...")
                self.running = False

            except Exception as exc:
                logger.error(f"Unexpected error in worker loop: {exc}", exc_info=True)
                await asyncio.sleep(1)  # Brief back-off before retrying

        logger.info(f"Worker '{self.worker_id}' shut down cleanly.")
        if self.redis:
            await self.redis.aclose()

    async def _process_task(self, task_run_id: uuid.UUID):
        """
        Full lifecycle of a single task execution:
            PENDING -> RUNNING -> SUCCESS -> (enqueue dependents if ready)
        """
        async with AsyncSessionLocal() as db:
            # ----------------------------------------------------------------
            # Step 1: Load the TaskRun with its TaskDefinition
            # ----------------------------------------------------------------
            result = await db.execute(
                select(TaskRun)
                .where(TaskRun.id == task_run_id)
                .options(
                    selectinload(TaskRun.task).selectinload(TaskDefinition.dag)
                )
            )
            task_run = result.scalar_one_or_none()

            if not task_run:
                logger.warning(f"TaskRun {task_run_id} not found in database. Skipping.")
                return

            task_def = task_run.task

            # ----------------------------------------------------------------
            # Step 2: Mark as RUNNING
            # ----------------------------------------------------------------
            task_run.status = TaskRunStatus.RUNNING
            task_run.worker_id = self.worker_id
            task_run.started_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                f"Executing task '{task_def.name}' "
                f"(dag_run={task_run.dag_run_id}, command='{task_def.command}')"
            )

            # ----------------------------------------------------------------
            # Step 3: Simulate execution
            # ----------------------------------------------------------------
            # In a real system, this would shell out to run task_def.command.
            # We simulate with a variable sleep to mimic different workloads.
            import random
            execution_time = random.uniform(1.0, 3.0)
            await asyncio.sleep(execution_time)

            # ----------------------------------------------------------------
            # Step 4: Mark as SUCCESS
            # ----------------------------------------------------------------
            task_run.status = TaskRunStatus.SUCCESS
            task_run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                f"Task '{task_def.name}' completed in {execution_time:.2f}s"
            )

            # ----------------------------------------------------------------
            # Step 5: Orchestration fanout -- check downstream dependents
            # ----------------------------------------------------------------
            await self._enqueue_ready_dependents(db, task_def, task_run.dag_run_id)

    async def _enqueue_ready_dependents(
        self,
        db,
        completed_task: TaskDefinition,
        dag_run_id: uuid.UUID,
    ):
        """
        After a task succeeds, find all downstream tasks that depend on it.
        For each downstream task, check if ALL its parents are now SUCCESS.
        If yes, mark it QUEUED and push its TaskRun ID to Redis.

        This is the core orchestration logic that makes the DAG execute
        in the correct dependency order without a central coordinator.
        """
        # Load all tasks in this DAG to check for dependents
        result = await db.execute(
            select(TaskDefinition)
            .where(TaskDefinition.dag_id == completed_task.dag_id)
        )
        all_tasks = result.scalars().all()

        # Find tasks that list completed_task.name in their dependencies
        dependent_tasks = [
            t for t in all_tasks
            if completed_task.name in t.dependencies
        ]

        for dependent in dependent_tasks:
            # Get the TaskRun for this dependent task in this specific dag_run
            dep_run_result = await db.execute(
                select(TaskRun)
                .where(
                    TaskRun.task_id == dependent.id,
                    TaskRun.dag_run_id == dag_run_id,
                )
            )
            dep_run = dep_run_result.scalar_one_or_none()

            if not dep_run or dep_run.status != TaskRunStatus.PENDING:
                continue  # Already queued or running -- skip

            # Check if ALL parent tasks for this dependent are SUCCESS
            parent_names = dependent.dependencies
            parent_tasks = [t for t in all_tasks if t.name in parent_names]

            # Load runs for all parent tasks in this dag_run
            parent_run_result = await db.execute(
                select(TaskRun).where(
                    TaskRun.task_id.in_([p.id for p in parent_tasks]),
                    TaskRun.dag_run_id == dag_run_id,
                )
            )
            parent_runs = parent_run_result.scalars().all()

            all_parents_succeeded = (
                len(parent_runs) == len(parent_tasks)
                and all(r.status == TaskRunStatus.SUCCESS for r in parent_runs)
            )

            if all_parents_succeeded:
                dep_run.status = TaskRunStatus.QUEUED
                await db.commit()
                await self.redis.lpush(settings.TASK_QUEUE_NAME, str(dep_run.id))
                logger.info(
                    f"Enqueued downstream task '{dependent.name}' "
                    f"(all {len(parent_tasks)} parent(s) succeeded)"
                )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main():
    worker = Worker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
