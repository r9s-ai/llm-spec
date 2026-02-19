"""Run orchestration APIs."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec.web.config import settings
from llm_spec.web.db import SessionLocal, get_db
from llm_spec.web.models import RunEvent, RunJob, RunResult, RunTestResult, SuiteVersion
from llm_spec.web.schemas import RunCreateRequest, RunEventResponse, RunJobResponse
from llm_spec.web.services import execute_run_job

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _execute_in_background(run_id: str) -> None:
    db = SessionLocal()
    try:
        execute_run_job(db, run_id)
    finally:
        db.close()


@router.post("", response_model=RunJobResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RunJob:
    suite_version = db.get(SuiteVersion, payload.suite_version_id)
    if suite_version is None:
        raise HTTPException(status_code=404, detail="suite_version not found")
    provider = str(suite_version.parsed_json.get("provider"))
    endpoint = str(suite_version.parsed_json.get("endpoint"))

    resolved_mode = payload.mode or ("mock" if settings.mock_mode else "real")

    run = RunJob(
        status="queued",
        mode=resolved_mode,
        provider=provider,
        endpoint=endpoint,
        suite_version_id=suite_version.id,
        config_snapshot={"selected_tests": payload.selected_tests or []},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_execute_in_background, run.id)
    return run


@router.get("", response_model=list[RunJobResponse])
def list_runs(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[RunJob]:
    stmt = select(RunJob).order_by(RunJob.started_at.desc().nulls_last(), RunJob.id.desc())
    if status_filter:
        stmt = stmt.where(RunJob.status == status_filter)
    return list(db.execute(stmt).scalars().all())


@router.get("/{run_id}", response_model=RunJobResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunJob:
    row = db.get(RunJob, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return row


@router.post("/{run_id}/cancel", response_model=RunJobResponse)
def cancel_run(run_id: str, db: Session = Depends(get_db)) -> RunJob:
    row = db.get(RunJob, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    if row.status in {"success", "failed", "cancelled"}:
        return row
    row.status = "cancelled"
    row.finished_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{run_id}/events", response_model=list[RunEventResponse])
def list_run_events(
    run_id: str,
    after_seq: int = Query(default=0),
    db: Session = Depends(get_db),
) -> list[RunEvent]:
    stmt = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
        .order_by(RunEvent.seq.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    after_seq: int = Query(default=0),
) -> StreamingResponse:
    async def event_generator():
        next_seq = after_seq + 1
        while True:
            db = SessionLocal()
            try:
                run = db.get(RunJob, run_id)
                if run is None:
                    yield 'event: error\ndata: {"error":"run not found"}\n\n'
                    return

                stmt = (
                    select(RunEvent)
                    .where(RunEvent.run_id == run_id, RunEvent.seq >= next_seq)
                    .order_by(RunEvent.seq.asc())
                )
                events = list(db.execute(stmt).scalars().all())
                for event in events:
                    payload = {
                        "id": event.id,
                        "run_id": event.run_id,
                        "seq": event.seq,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat(),
                    }
                    yield (
                        f"id: {event.seq}\n"
                        f"event: {event.event_type}\n"
                        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    )
                    next_seq = event.seq + 1

                if run.status in {"success", "failed", "cancelled"}:
                    terminal = {"run_id": run.id, "status": run.status}
                    yield f"event: done\ndata: {json.dumps(terminal, ensure_ascii=False)}\n\n"
                    return
            finally:
                db.close()
            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/{run_id}/result")
def get_run_result(run_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(RunResult, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run_result not found")
    return row.run_result_json


@router.get("/{run_id}/tests")
def list_run_tests(run_id: str, db: Session = Depends(get_db)) -> list[dict]:
    stmt = (
        select(RunTestResult)
        .where(RunTestResult.run_id == run_id)
        .order_by(RunTestResult.test_name.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [r.raw_record for r in rows]
