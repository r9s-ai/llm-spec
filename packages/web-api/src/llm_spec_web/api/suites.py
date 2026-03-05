"""Read-only suite APIs from suites-registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from llm_spec_web.api.deps import get_suite_service
from llm_spec_web.schemas.suite import SuiteSpecResponse, TestDefResponse
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


@router.get("", response_model=list[SuiteSpecResponse])
def list_suites(
    provider: str | None = None,
    route: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    service: SuiteService = Depends(get_suite_service),
) -> list[SuiteSpecResponse]:
    suites = service.list_suites(
        provider=provider,
        route=route,
        model_name=model,
        endpoint=endpoint,
    )
    return [
        SuiteSpecResponse(
            suite_id=s.suite_id,
            suite_name=s.suite_name,
            provider_id=s.provider_id,
            model_id=s.model_id,
            route_id=s.route_id,
            api_family=s.api_family,
            endpoint=s.endpoint,
            method=s.method,
            tests=[
                TestDefResponse(
                    name=t.name,
                    description=t.description,
                    baseline=t.baseline,
                    check_stream=t.check_stream,
                    focus_name=t.focus_param.name if t.focus_param else None,
                    focus_value=t.focus_param.value if t.focus_param else None,
                    tags=t.tags,
                )
                for t in s.tests
            ],
        )
        for s in suites
    ]


@router.get("/{suite_id}", response_model=SuiteSpecResponse)
def get_suite(
    suite_id: str,
    service: SuiteService = Depends(get_suite_service),
) -> SuiteSpecResponse:
    s = service.get_suite(suite_id)
    return SuiteSpecResponse(
        suite_id=s.suite_id,
        suite_name=s.suite_name,
        provider_id=s.provider_id,
        model_id=s.model_id,
        route_id=s.route_id,
        api_family=s.api_family,
        endpoint=s.endpoint,
        method=s.method,
        tests=[
            TestDefResponse(
                name=t.name,
                description=t.description,
                baseline=t.baseline,
                check_stream=t.check_stream,
                focus_name=t.focus_param.name if t.focus_param else None,
                focus_value=t.focus_param.value if t.focus_param else None,
                tags=t.tags,
            )
            for t in s.tests
        ],
    )
