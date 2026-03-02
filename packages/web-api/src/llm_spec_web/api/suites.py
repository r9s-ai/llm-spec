"""Read-only suite APIs from suites-registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from llm_spec_web.api.deps import get_suite_service
from llm_spec_web.schemas.suite import SuiteResponse, SuiteVersionResponse
from llm_spec_web.services.suite_service import SuiteService

router = APIRouter(prefix="/api/suites", tags=["suites"])


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
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteResponse]:
    suites = service.list_suites(provider=provider, route=route, model=model, endpoint=endpoint)
    return [SuiteResponse.model_validate(s) for s in suites]


@router.get("/{suite_id}", response_model=SuiteResponse)
def get_suite(
    suite_id: str,
    service: SuiteService = Depends(get_suite_service),
) -> SuiteResponse:
    suite = service.get_suite(suite_id)
    return SuiteResponse.model_validate(suite)


@router.get("/{suite_id}/versions", response_model=list[SuiteVersionResponse])
def list_versions(
    suite_id: str,
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteVersionResponse]:
    versions = service.list_versions(suite_id)
    return [SuiteVersionResponse.model_validate(v) for v in versions]


@router.get("/versions/{version_id}", response_model=SuiteVersionResponse)
def get_version(
    version_id: str,
    service: SuiteService = Depends(get_suite_service),
) -> SuiteVersionResponse:
    version = service.get_version(version_id)
    return SuiteVersionResponse.model_validate(version)
