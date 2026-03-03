"""Task orchestration APIs.

In this codebase, a "task" represents a user-initiated execution that may contain
multiple runs (one per selected model suite / model route).

Historically this concept was called "batch". This module is the aggressive
rename target: the public API is now /api/tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from llm_spec_web.api.deps import get_db, get_run_service
from llm_spec_web.core.db import SessionLocal
from llm_spec_web.schemas.run import (
    RunJobResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    TaskWithRunsResponse,
)
from llm_spec_web.services.run_service import RunService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _execute_task_in_background(task_id: str, max_concurrent: int = 5) -> None:
    """Execute a full task in background.

    Args:
        task_id: Task ID.
        max_concurrent: Maximum number of concurrent tests.
    """
    db = SessionLocal()
    try:
        service = RunService()
        service.execute_task(db, task_id, max_concurrent=max_concurrent)
    finally:
        db.close()


@router.post("", response_model=TaskWithRunsResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> TaskWithRunsResponse:
    """Create a new task with multiple runs."""
    task, runs = service.create_task(
        db,
        model_suite_ids=payload.model_suite_ids,
        mode=payload.mode,
        selected_tests_by_suite=payload.selected_tests_by_suite,
        name=payload.name,
    )

    max_concurrent = payload.max_concurrent or 5
    background_tasks.add_task(_execute_task_in_background, task.id, max_concurrent)

    return TaskWithRunsResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        mode=task.mode,
        total_runs=task.total_runs,
        completed_runs=task.completed_runs,
        passed_runs=task.passed_runs,
        failed_runs=task.failed_runs,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        runs=[RunJobResponse.model_validate(r) for r in runs],
    )


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[TaskResponse]:
    """List all tasks."""
    tasks, _ = service.list_tasks(db, status_filter=status_filter, limit=limit, offset=offset)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskWithRunsResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> TaskWithRunsResponse:
    """Get a task by ID with its runs."""
    task, runs = service.get_task_with_runs(db, task_id)
    return TaskWithRunsResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        mode=task.mode,
        total_runs=task.total_runs,
        completed_runs=task.completed_runs,
        passed_runs=task.passed_runs,
        failed_runs=task.failed_runs,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        runs=[RunJobResponse.model_validate(r) for r in runs],
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> None:
    """Delete a task and all its runs."""
    service.delete_task(db, task_id)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> TaskResponse:
    """Update a task's name."""
    task = service.update_task(db, task_id, payload.name)
    return TaskResponse.model_validate(task)


@router.get("/{task_id}/runs", response_model=list[RunJobResponse])
def get_task_runs(
    task_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[RunJobResponse]:
    """Get all runs in a task."""
    _, runs = service.get_task_with_runs(db, task_id)
    return [RunJobResponse.model_validate(r) for r in runs]


@router.post("/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> TaskResponse:
    """Cancel a running task (in-memory cancel + persisted cancelled state)."""
    task = service.cancel_task_execution(db, task_id)
    return TaskResponse.model_validate(task)
