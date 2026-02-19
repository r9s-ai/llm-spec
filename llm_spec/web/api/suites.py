"""Suite CRUD and version APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_spec.web.db import get_db
from llm_spec.web.models import Suite, SuiteVersion
from llm_spec.web.schemas import (
    SuiteCreateRequest,
    SuiteResponse,
    SuiteUpdateRequest,
    SuiteVersionCreateRequest,
    SuiteVersionResponse,
)
from llm_spec.web.services import create_suite_version, create_suite_with_initial_version

router = APIRouter(prefix="/api/suites", tags=["suites"])
version_router = APIRouter(prefix="/api/suite-versions", tags=["suite-versions"])


@router.get("", response_model=list[SuiteResponse])
def list_suites(
    provider: str | None = Query(default=None),
    endpoint: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Suite]:
    stmt = select(Suite)
    if provider:
        stmt = stmt.where(Suite.provider == provider)
    if endpoint:
        stmt = stmt.where(Suite.endpoint == endpoint)
    return list(db.execute(stmt.order_by(Suite.provider, Suite.endpoint)).scalars().all())


@router.post("", response_model=SuiteResponse, status_code=status.HTTP_201_CREATED)
def create_suite(payload: SuiteCreateRequest, db: Session = Depends(get_db)) -> Suite:
    try:
        suite = create_suite_with_initial_version(
            db,
            provider=payload.provider,
            endpoint=payload.endpoint,
            name=payload.name,
            raw_json5=payload.raw_json5,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return suite


@router.get("/{suite_id}", response_model=SuiteResponse)
def get_suite(suite_id: str, db: Session = Depends(get_db)) -> Suite:
    suite = db.get(Suite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="suite not found")
    return suite


@router.put("/{suite_id}", response_model=SuiteResponse)
def update_suite(
    suite_id: str, payload: SuiteUpdateRequest, db: Session = Depends(get_db)
) -> Suite:
    suite = db.get(Suite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="suite not found")
    if payload.name is not None:
        suite.name = payload.name
    if payload.status is not None:
        suite.status = payload.status
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(suite_id: str, db: Session = Depends(get_db)) -> None:
    suite = db.get(Suite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="suite not found")
    db.delete(suite)
    db.commit()


@router.get("/{suite_id}/versions", response_model=list[SuiteVersionResponse])
def list_versions(suite_id: str, db: Session = Depends(get_db)) -> list[SuiteVersion]:
    suite = db.get(Suite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="suite not found")
    stmt = (
        select(SuiteVersion)
        .where(SuiteVersion.suite_id == suite_id)
        .order_by(SuiteVersion.version.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.post(
    "/{suite_id}/versions",
    response_model=SuiteVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    suite_id: str,
    payload: SuiteVersionCreateRequest,
    db: Session = Depends(get_db),
) -> SuiteVersion:
    suite = db.get(Suite, suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="suite not found")
    try:
        return create_suite_version(
            db,
            suite=suite,
            raw_json5=payload.raw_json5,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@version_router.get("/{version_id}", response_model=SuiteVersionResponse)
def get_version(version_id: str, db: Session = Depends(get_db)) -> SuiteVersion:
    row = db.get(SuiteVersion, version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="suite_version not found")
    return row
