"""
api/schemas.py - Pydantic request and response models for the DAG Engine API.

These models define the shape of JSON payloads coming in and going out.
FastAPI uses them to automatically validate requests and serialise responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from dag_engine.db.models import DagStatus, TaskRunStatus


# ---------------------------------------------------------------------------
# Request Models (incoming payloads)
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    """A single task definition within a DAG creation request."""
    name: str = Field(..., description="Unique name for this task within the DAG")
    command: str = Field(..., description="The shell command this task executes")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Names of tasks that must succeed before this task runs",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "name": "extract_data",
            "command": "python scripts/extract.py",
            "dependencies": [],
        }
    }}


class DagCreate(BaseModel):
    """Request body for POST /dags -- creates a new DAG definition."""
    name: str = Field(..., description="Unique name for this DAG")
    description: str | None = Field(None, description="Optional description")
    tasks: list[TaskCreate] = Field(
        ...,
        min_length=1,
        description="List of tasks that make up this DAG",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "name": "data_pipeline",
            "description": "Daily ETL pipeline",
            "tasks": [
                {"name": "extract", "command": "python extract.py", "dependencies": []},
                {"name": "transform", "command": "python transform.py", "dependencies": ["extract"]},
                {"name": "load", "command": "python load.py", "dependencies": ["transform"]},
            ],
        }
    }}


# ---------------------------------------------------------------------------
# Response Models (outgoing payloads)
# ---------------------------------------------------------------------------

class TaskDefinitionResponse(BaseModel):
    """Response shape for a single task definition."""
    id: uuid.UUID
    name: str
    command: str
    dependencies: list[str]

    model_config = {"from_attributes": True}
    # from_attributes=True tells Pydantic to read values from SQLAlchemy
    # model attributes rather than expecting a plain dict.


class DagResponse(BaseModel):
    """Response shape for a created or retrieved DAG."""
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    status: DagStatus
    tasks: list[TaskDefinitionResponse]

    model_config = {"from_attributes": True}


class TaskRunResponse(BaseModel):
    """Response shape for a single task run instance."""
    id: uuid.UUID
    task_id: uuid.UUID
    task_name: str
    status: TaskRunStatus
    worker_id: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class DagRunTriggerResponse(BaseModel):
    """Response returned when a DAG run is triggered."""
    dag_run_id: uuid.UUID
    dag_id: uuid.UUID
    message: str
    queued_tasks: list[str]
    execution_tiers: list[list[str]]


class DagStatusResponse(BaseModel):
    """Response for GET /dags/{dag_id}/status -- real-time execution state."""
    dag_id: uuid.UUID
    dag_name: str
    task_runs: list[TaskRunResponse]
