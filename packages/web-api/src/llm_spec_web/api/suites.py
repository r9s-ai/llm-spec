"""Read-only model-suite APIs from suites-registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from llm_spec_web.api.deps import get_suite_service
from llm_spec_web.schemas.suite import ModelSuiteResponse
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


@router.get("", response_model=list[ModelSuiteResponse])
def list_suites(
    provider: str | None = None,
    route: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    service: SuiteService = Depends(get_suite_service),
) -> list[ModelSuiteResponse]:
    suites = service.list_suites(
        provider=provider,
        route=route,
        model_name=model,
        endpoint=endpoint,
    )
    return [ModelSuiteResponse.model_validate(s) for s in suites]


@router.get("/{suite_id}", response_model=ModelSuiteResponse)
def get_suite(
    suite_id: str,
    service: SuiteService = Depends(get_suite_service),
) -> ModelSuiteResponse:
    suite = service.get_suite(suite_id)
    return ModelSuiteResponse.model_validate(suite)
