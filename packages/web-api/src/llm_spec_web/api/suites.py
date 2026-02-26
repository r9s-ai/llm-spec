"""Read-only suite APIs from suites-registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from llm_spec_web.api.deps import get_db, get_suite_service
from llm_spec_web.schemas.suite import SuiteResponse, SuiteVersionResponse
from llm_spec_web.services.suite_service import SuiteService

router = APIRouter(prefix="/api/suites", tags=["suites"])
version_router = APIRouter(prefix="/api/suite-versions", tags=["suite-versions"])


@router.post("/cache/refresh")
def refresh_suite_registry_cache(
    service: SuiteService = Depends(get_suite_service),
) -> dict[str, int | str]:
    suite_count, version_count = service.refresh_cache()
    return {
        "status": "ok",
        "suite_count": suite_count,
        "version_count": version_count,
    }


@router.get("", response_model=list[SuiteResponse])
def list_suites(
    provider: str | None = None,
    route: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteResponse]:
    suites = service.list_suites(db, provider=provider, route=route, model=model, endpoint=endpoint)
    return [SuiteResponse.model_validate(s) for s in suites]


@router.get("/{suite_id}", response_model=SuiteResponse)
def get_suite(
    suite_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteResponse:
    suite = service.get_suite(db, suite_id)
    return SuiteResponse.model_validate(suite)


@router.get("/{suite_id}/versions", response_model=list[SuiteVersionResponse])
def list_versions(
    suite_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteVersionResponse]:
    versions = service.list_versions(db, suite_id)
    return [SuiteVersionResponse.model_validate(v) for v in versions]


@version_router.get("/{version_id}", response_model=SuiteVersionResponse)
def get_version(
    version_id: str,
    db: Session = Depends(get_db),
    service: SuiteService = Depends(get_suite_service),
) -> SuiteVersionResponse:
    version = service.get_version(db, version_id)
    return SuiteVersionResponse.model_validate(version)
