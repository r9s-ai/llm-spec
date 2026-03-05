"""Run-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    """Request body for creating a new task."""

    suite_ids: list[str] = Field(..., min_length=1)
    mode: Literal["real", "mock"] | None = None
    selected_tests_by_suite: dict[str, list[str]] | None = Field(
        default=None, description="Map of suite_id to list of test names"
    )
    name: str | None = Field(
        default=None, max_length=255, description="User-defined name for the task"
    )
    max_concurrent: int | None = Field(
        default=None, ge=1, le=50, description="Maximum concurrent tests per run (1-50)"
    )


class TaskUpdateRequest(BaseModel):
    """Request body for updating a task."""

    name: str = Field(..., min_length=1, max_length=255, description="New name for the task")


class RunTestRetryRequest(BaseModel):
    """Request body for retrying one test inside an existing run."""

    run_case_id: str = Field(..., min_length=1, description="Run-case snapshot ID to retry")


class RunJobResponse(BaseModel):
    """Response model for a run job."""

    id: str
    status: str
    mode: str
    provider: str
    model: str | None = None
    route: str | None = None
    endpoint: str
    task_id: str | None = None
    suite_id: str | None = None
    suite_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_total: int = 0
    progress_done: int = 0
    progress_passed: int = 0
    progress_failed: int = 0
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str
    name: str
    status: str
    mode: str
    total_runs: int
    completed_runs: int
    passed_runs: int
    failed_runs: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskWithRunsResponse(TaskResponse):
    """Response model for task with runs."""

    runs: list[RunJobResponse] = []


class RunEventResponse(BaseModel):
    """Response model for a run event."""

    id: int
    run_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
