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


class BatchCreateRequest(BaseModel):
    """Request body for creating a new batch.

    Attributes:
        suite_version_ids: List of suite version IDs to run.
        mode: Execution mode ("real" or "mock").
        selected_tests_by_suite: Map of suite_id to list of test names.
        name: User-defined name for the batch.
        max_concurrent: Maximum number of tests to run concurrently per run job.
    """

    suite_version_ids: list[str] = Field(..., min_length=1)
    mode: Literal["real", "mock"] | None = None
    selected_tests_by_suite: dict[str, list[str]] | None = Field(
        default=None, description="Map of suite_id to list of test names"
    )
    name: str | None = Field(
        default=None, max_length=255, description="User-defined name for the batch"
    )
    max_concurrent: int | None = Field(
        default=None, ge=1, le=50, description="Maximum concurrent tests per run (1-50)"
    )


class BatchUpdateRequest(BaseModel):
    """Request body for updating a batch.

    Attributes:
        name: New name for the batch.
    """

    name: str = Field(..., min_length=1, max_length=255, description="New name for the batch")


class RunJobResponse(BaseModel):
    """Response model for run job.

    Attributes:
        id: Run job ID.
        status: Job status.
        mode: Execution mode.
        provider: Provider name.
        endpoint: API endpoint path.
        batch_id: Batch ID this run belongs to.
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
    batch_id: str | None = None
    suite_version_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    progress_total: int
    progress_done: int
    progress_passed: int
    progress_failed: int
    error_message: str | None

    model_config = {"from_attributes": True}


class RunBatchResponse(BaseModel):
    """Response model for run batch.

    Attributes:
        id: Batch ID.
        name: User-defined name for the batch.
        status: Batch status.
        mode: Execution mode.
        total_runs: Total number of runs.
        completed_runs: Number of completed runs.
        passed_runs: Number of passed runs.
        failed_runs: Number of failed runs.
        started_at: Execution start timestamp.
        finished_at: Execution finish timestamp.
        created_at: Creation timestamp.
    """

    id: str
    name: str
    status: str
    mode: str
    total_runs: int
    completed_runs: int
    passed_runs: int
    failed_runs: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunBatchWithRunsResponse(RunBatchResponse):
    """Response model for run batch with runs.

    Attributes:
        runs: List of runs in this batch.
    """

    runs: list[RunJobResponse] = []


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
