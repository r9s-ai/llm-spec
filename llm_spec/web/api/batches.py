"""Batch orchestration APIs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from llm_spec.web.api.deps import get_db, get_run_service
from llm_spec.web.core.db import SessionLocal
from llm_spec.web.schemas.run import (
    BatchCreateRequest,
    BatchUpdateRequest,
    RunBatchResponse,
    RunBatchWithRunsResponse,
    RunJobResponse,
)
from llm_spec.web.services.run_service import RunService

router = APIRouter(prefix="/api/batches", tags=["batches"])


def _execute_run_in_background(run_id: str) -> None:
    """Execute a run in background.

    Args:
        run_id: Run job ID.
    """
    db = SessionLocal()
    try:
        service = RunService()
        service.execute_run(db, run_id)
        # Update batch status after run completes
        run = service.get_run(db, run_id)
        if run.batch_id:
            service.update_batch_status(db, run.batch_id)
    finally:
        db.close()


@router.post("", response_model=RunBatchWithRunsResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunBatchWithRunsResponse:
    """Create a new batch with multiple runs.

    Args:
        payload: Batch creation request.
        background_tasks: FastAPI background tasks.
        db: Database session.
        service: Run service.

    Returns:
        Created batch with runs.
    """
    batch, runs = service.create_batch(
        db,
        suite_version_ids=payload.suite_version_ids,
        mode=payload.mode,
        selected_tests_by_suite=payload.selected_tests_by_suite,
        name=payload.name,
    )

    # Schedule all runs for background execution
    for run in runs:
        background_tasks.add_task(_execute_run_in_background, run.id)

    return RunBatchWithRunsResponse(
        id=batch.id,
        name=batch.name,
        status=batch.status,
        mode=batch.mode,
        total_runs=batch.total_runs,
        completed_runs=batch.completed_runs,
        passed_runs=batch.passed_runs,
        failed_runs=batch.failed_runs,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
        created_at=batch.created_at,
        runs=[RunJobResponse.model_validate(r) for r in runs],
    )


@router.get("", response_model=list[RunBatchResponse])
def list_batches(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[RunBatchResponse]:
    """List all batches.

    Args:
        status_filter: Filter by status.
        limit: Maximum number of results.
        offset: Offset for pagination.
        db: Database session.
        service: Run service.

    Returns:
        List of batches.
    """
    batches, _ = service.list_batches(db, status_filter=status_filter, limit=limit, offset=offset)
    return [RunBatchResponse.model_validate(b) for b in batches]


@router.get("/{batch_id}", response_model=RunBatchWithRunsResponse)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunBatchWithRunsResponse:
    """Get a batch by ID with its runs.

    Args:
        batch_id: Batch ID.
        db: Database session.
        service: Run service.

    Returns:
        Batch with runs.
    """
    batch, runs = service.get_batch_with_runs(db, batch_id)
    return RunBatchWithRunsResponse(
        id=batch.id,
        name=batch.name,
        status=batch.status,
        mode=batch.mode,
        total_runs=batch.total_runs,
        completed_runs=batch.completed_runs,
        passed_runs=batch.passed_runs,
        failed_runs=batch.failed_runs,
        started_at=batch.started_at,
        finished_at=batch.finished_at,
        created_at=batch.created_at,
        runs=[RunJobResponse.model_validate(r) for r in runs],
    )


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> None:
    """Delete a batch and all its runs.

    Args:
        batch_id: Batch ID.
        db: Database session.
        service: Run service.
    """
    service.delete_batch(db, batch_id)


@router.patch("/{batch_id}", response_model=RunBatchResponse)
def update_batch(
    batch_id: str,
    payload: BatchUpdateRequest,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunBatchResponse:
    """Update a batch's name.

    Args:
        batch_id: Batch ID.
        payload: Update request with new name.
        db: Database session.
        service: Run service.

    Returns:
        Updated batch.
    """
    batch = service.update_batch(db, batch_id, payload.name)
    return RunBatchResponse.model_validate(batch)


@router.get("/{batch_id}/runs", response_model=list[RunJobResponse])
def get_batch_runs(
    batch_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[RunJobResponse]:
    """Get all runs in a batch.

    Args:
        batch_id: Batch ID.
        db: Database session.
        service: Run service.

    Returns:
        List of runs in the batch.
    """
    _, runs = service.get_batch_with_runs(db, batch_id)
    return [RunJobResponse.model_validate(r) for r in runs]
