"""Build task-level result payloads from case results."""

from __future__ import annotations

from llm_spec.results.result_types import CaseResult, TaskResult


def build_task_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    provider: str,
    model: str | None,
    route: str | None,
    endpoint: str,
    cases: list[CaseResult],
) -> TaskResult:
    """Build a stable run-level task result payload."""
    return {
        "version": "task_result.v1",
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "selection": {
            "provider": provider,
            "model": model,
            "route": route,
            "endpoint": endpoint,
        },
        "cases": cases,
    }
