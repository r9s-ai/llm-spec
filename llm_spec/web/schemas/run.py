"""Run-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    """Request body for creating a new run.

    Attributes:
        suite_version_id: ID of the suite version to run.
        mode: Execution mode ("real" or "mock").
        selected_tests: List of test names to run (empty means all tests).
    """

    suite_version_id: str = Field(..., min_length=1)
    mode: Literal["real", "mock"] | None = None
    selected_tests: list[str] | None = Field(default=None, description="List of test names to run")


class RunJobResponse(BaseModel):
    """Response model for run job.

    Attributes:
        id: Run job ID.
        status: Job status.
        mode: Execution mode.
        provider: Provider name.
        endpoint: API endpoint path.
        suite_version_id: Suite version ID.
        started_at: Execution start timestamp.
        finished_at: Execution finish timestamp.
        progress_total: Total number of tests.
        progress_done: Number of completed tests.
        progress_passed: Number of passed tests.
        progress_failed: Number of failed tests.
        error_message: Error message if failed.
    """

    id: str
    status: str
    mode: str
    provider: str
    endpoint: str
    suite_version_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    progress_total: int
    progress_done: int
    progress_passed: int
    progress_failed: int
    error_message: str | None

    model_config = {"from_attributes": True}


class RunEventResponse(BaseModel):
    """Response model for run event.

    Attributes:
        id: Event ID.
        run_id: Run job ID.
        seq: Sequence number.
        event_type: Event type.
        payload: Event data.
        created_at: Event timestamp.
    """

    id: int
    run_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
