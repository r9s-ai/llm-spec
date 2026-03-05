"""Build RunResult from a list of TestVerdicts."""

from __future__ import annotations

from llm_spec.results.result_types import RunResult, TestVerdict


def build_run_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    provider: str,
    model: str | None,
    route: str | None,
    endpoint: str,
    suite_name: str = "",
    verdicts: list[TestVerdict],
) -> RunResult:
    """Build a RunResult from collected verdicts."""
    return RunResult(
        run_id=run_id,
        provider=provider,
        model=model,
        route=route,
        endpoint=endpoint,
        suite_name=suite_name,
        started_at=started_at,
        finished_at=finished_at,
        verdicts=verdicts,
    )
