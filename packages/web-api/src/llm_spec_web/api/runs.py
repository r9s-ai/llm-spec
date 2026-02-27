"""Run orchestration APIs."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec_web.api.deps import get_db, get_run_service
from llm_spec_web.core.db import SessionLocal
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.models.run import RunEvent, RunJob
from llm_spec_web.schemas.run import (
    RunCreateRequest,
    RunEventResponse,
    RunJobResponse,
    RunTestRetryRequest,
)
from llm_spec_web.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _execute_in_background(run_id: str) -> None:
    """Execute a run in background.

    Args:
        run_id: Run job ID.
    """
    db = SessionLocal()
    try:
        service = RunService()
        service.execute_run(db, run_id)
    finally:
        db.close()


@router.post("", response_model=RunJobResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunJobResponse:
    """Create a new run job.

    Args:
        payload: Run creation request.
        background_tasks: FastAPI background tasks.
        db: Database session.
        service: Run service.

    Returns:
        Created run job.
    """
    run = service.create_run(
        db,
        suite_version_id=payload.suite_version_id,
        mode=payload.mode,
        selected_tests=payload.selected_tests,
    )
    background_tasks.add_task(_execute_in_background, run.id)
    return RunJobResponse.model_validate(run)


@router.get("", response_model=list[RunJobResponse])
def list_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[RunJobResponse]:
    """List all run jobs.

    Args:
        status_filter: Filter by status.
        db: Database session.
        service: Run service.

    Returns:
        List of run jobs.
    """
    runs = service.list_runs(db, status_filter=status_filter)
    return [RunJobResponse.model_validate(r) for r in runs]


@router.get("/{run_id}", response_model=RunJobResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunJobResponse:
    """Get a run job by ID.

    Args:
        run_id: Run job ID.
        db: Database session.
        service: Run service.

    Returns:
        Run job details.
    """
    run = service.get_run(db, run_id)
    return RunJobResponse.model_validate(run)


@router.post("/{run_id}/cancel", response_model=RunJobResponse)
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunJobResponse:
    """Cancel a run job.

    Args:
        run_id: Run job ID.
        db: Database session.
        service: Run service.

    Returns:
        Cancelled run job.
    """
    run = service.cancel_run(db, run_id)
    return RunJobResponse.model_validate(run)


@router.post("/{run_id}/tests/retry", response_model=RunJobResponse)
def retry_run_test(
    run_id: str,
    payload: RunTestRetryRequest,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunJobResponse:
    """Retry one test within an existing run and persist updated run result."""
    run = service.retry_test_in_run(db, run_id=run_id, test_name=payload.test_name)
    return RunJobResponse.model_validate(run)


@router.get("/{run_id}/events", response_model=list[RunEventResponse])
def list_run_events(
    run_id: str,
    after_seq: int = Query(default=0),
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[RunEventResponse]:
    """List events for a run.

    Args:
        run_id: Run job ID.
        after_seq: Only return events with seq > after_seq.
        db: Database session.
        service: Run service.

    Returns:
        List of run events.
    """
    events = service.list_events(db, run_id, after_seq=after_seq)
    return [RunEventResponse.model_validate(e) for e in events]


@router.get("/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    after_seq: int = Query(default=0),
) -> StreamingResponse:
    """Stream events for a run using Server-Sent Events.

    Uses in-memory event bus for real-time updates without database polling.

    Args:
        run_id: Run job ID.
        after_seq: Only return events with seq > after_seq (for reconnection).

    Returns:
        SSE stream of run events.
    """

    async def event_generator():
        # First, check if run exists and get any historical events from database
        db = SessionLocal()
        try:
            run = db.get(RunJob, run_id)
            if run is None:
                yield 'event: error\ndata: {"error":"run not found"}\n\n'
                return

            # If run is already finished, return terminal event from database
            if run.status in {"success", "failed", "cancelled"}:
                # Get the terminal event from database
                stmt = (
                    select(RunEvent)
                    .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                    .order_by(RunEvent.seq.asc())
                )
                events = list(db.execute(stmt).scalars().all())
                for event in events:
                    payload = {
                        "run_id": event.run_id,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat(),
                    }
                    yield (
                        f"event: {event.event_type}\n"
                        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    )
                terminal = {"run_id": run.id, "status": run.status}
                yield f"event: done\ndata: {json.dumps(terminal, ensure_ascii=False)}\n\n"
                return
        finally:
            db.close()

        # Subscribe to in-memory event bus for real-time updates
        seq = 0
        async for event in event_bus.subscribe(run_id, timeout=30.0):
            # Skip heartbeat events in SSE output
            if event["event_type"] == "heartbeat":
                yield ": heartbeat\n\n"
                continue

            seq += 1
            payload = {
                "run_id": run_id,
                "seq": seq,
                "event_type": event["event_type"],
                "payload": event["payload"],
                "created_at": event["created_at"],
            }
            yield (
                f"event: {event['event_type']}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            )

            # Terminal event, send done and exit
            if event["event_type"] in ("run_finished", "run_failed", "run_cancelled"):
                # Get final status from database
                db = SessionLocal()
                try:
                    run = db.get(RunJob, run_id)
                    if run:
                        terminal = {"run_id": run.id, "status": run.status}
                        yield f"event: done\ndata: {json.dumps(terminal, ensure_ascii=False)}\n\n"
                finally:
                    db.close()
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/{run_id}/result")
def get_run_result(
    run_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> dict:
    """Get the result for a run.

    Args:
        run_id: Run job ID.
        db: Database session.
        service: Run service.

    Returns:
        Run result JSON.
    """
    return service.get_result(db, run_id)


@router.get("/{run_id}/tests")
def list_run_tests(
    run_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> list[dict]:
    """List test results for a run.

    Args:
        run_id: Run job ID.
        db: Database session.
        service: Run service.

    Returns:
        List of test result records.
    """
    return service.list_test_results(db, run_id)
