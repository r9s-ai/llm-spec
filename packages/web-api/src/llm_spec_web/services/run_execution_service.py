"""Run execution service — async orchestration, retry, and provider client creation.

Delegates all execution to ``llm_spec.executor.run_suites()`` (core),
injecting web-layer side-effects (DB writes, SSE events) via callbacks.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig, ProviderConfig, load_config
from llm_spec.executor import (
    ExecutionProgress,
    Executor,
    SuiteContext,
    SuiteResult,
    create_provider_adapter,
    run_suites,
    run_task_suites,
)
from llm_spec.results.result_types import TestVerdict
from llm_spec.suites import TestCase
from llm_spec_web.config import settings
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from llm_spec_web.models.run import RunJob, RunTestResult
from llm_spec_web.repositories.run_repo import RunRepository
from llm_spec_web.services.mappers import (
    run_case_to_test_case,
    run_result_to_dict,
    test_case_to_run_case,
    verdict_to_case_row,
    verdict_to_test_result_row,
)
from llm_spec_web.services.suite_service import SuiteService
from llm_spec_web.services.task_service import TaskService


def _create_client(
    provider: str,
    app_config: AppConfig,
    mode: str,
) -> tuple[HTTPClient, Any]:
    """Create (HTTPClient, ProviderAdapter) — delegates to core for real mode."""
    if mode == "mock":
        from llm_spec_web.adapters.mock_adapter import MockProviderAdapter

        config = ProviderConfig(api_key="", base_url="", timeout=30.0)
        return HTTPClient(), MockProviderAdapter(
            config=config,
            base_dir=settings.mock_base_dir,
            provider_name=provider,
        )
    return create_provider_adapter(provider, app_config)


class RunExecutionService:
    """Service for test execution orchestration — run, retry, and cancellation."""

    def __init__(self) -> None:
        self._task_service = TaskService()

    # ── Retry ─────────────────────────────────────────────

    def retry_test_in_run(self, db: Session, run_id: str, run_case_id: str) -> RunJob:
        """Retry one persisted run-case and update the run."""
        run_repo = RunRepository(db)

        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            raise NotFoundError("Run", run_id)
        if run_job.status in {"running", "queued"}:
            raise ValidationError(f"Run is still active: {run_id}")
        run_case = run_repo.get_run_case(run_case_id)
        if run_case is None or run_case.run_id != run_id:
            raise NotFoundError("RunCase", run_case_id)
        target_case = run_case_to_test_case(run_case)

        app_config = load_config(settings.app_toml_path)
        if run_job.mode != "mock":
            try:
                app_config.get_provider_config(run_job.provider)
            except KeyError as err:
                raise ConfigurationError(f"provider config missing: {run_job.provider}") from err

        asyncio.run(
            self._retry_test_in_run_async(
                db=db,
                run_repo=run_repo,
                run_job=run_job,
                run_case=run_case,
                target_case=target_case,
                app_config=app_config,
            )
        )
        if run_job.task_id:
            self._task_service.update_task_status(db, run_job.task_id)
        db.refresh(run_job)
        return run_job

    async def _retry_test_in_run_async(
        self,
        *,
        db: Session,
        run_repo: RunRepository,
        run_job: RunJob,
        run_case: Any,
        target_case: TestCase,
        app_config: Any,
    ) -> None:
        http_client = None
        try:
            http_client, client = _create_client(run_job.provider, app_config, run_job.mode)

            executor = Executor(client=client)
            verdict = await executor.run_one(target_case)

            # Upsert test result
            run_repo.upsert_test_result_by_run_case_id(
                run_id=run_job.id,
                run_case_id=run_case.id,
                verdict=verdict,
            )

            # Update stored run result
            result_row = run_repo.get_run_result(run_job.id)
            if result_row is None:
                raise NotFoundError("RunResult", run_job.id)
            updated_json = _merge_verdict_into_run_result(
                result_row.result_json,
                case_id=target_case.case_id,
                new_verdict=verdict,
                run_case_id=run_case.id,
            )
            result_row.result_json = updated_json
            run_repo.save_run_result(result_row)

            # Recalculate progress from cases
            cases_raw = updated_json.get("cases", [])
            total = len(cases_raw)
            passed = sum(
                1
                for c in cases_raw
                if isinstance(c, dict)
                and isinstance(c.get("result"), dict)
                and c["result"].get("status") == "pass"
            )
            run_job.progress_total = total
            run_job.progress_done = total
            run_job.progress_passed = passed
            run_job.progress_failed = total - passed
            run_job.status = "success" if run_job.progress_failed == 0 else "failed"
            run_job.error_message = None if run_job.status == "success" else run_job.error_message
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            run_repo.append_event(
                run_job.id,
                "test_retried",
                {
                    "test_name": target_case.test_name,
                    "run_case_id": run_case.id,
                    "status": verdict.status,
                    "run_status": run_job.status,
                },
            )
            db.commit()
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                await http_client.close_async()

    # ── Single-run entry (no task) ────────────────────────

    def execute_run(self, db: Session, run_id: str, max_concurrent: int = 5) -> None:
        """Execute a single run (no parent task)."""
        run_repo = RunRepository(db)
        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            return
        if run_job.suite_id is None:
            run_repo.fail_run_with_event(run_job, "suite_id is None")
            return

        app_config = load_config(settings.app_toml_path)
        if run_job.mode != "mock":
            try:
                app_config.get_provider_config(run_job.provider)
            except KeyError:
                run_repo.fail_run_with_event(
                    run_job, f"provider config missing: {run_job.provider}"
                )
                event_bus.push(
                    run_id, "run_failed", {"error": f"provider config missing: {run_job.provider}"}
                )
                event_bus.end_run(run_id)
                event_bus.cleanup(run_id)
                return

        suite_service = SuiteService()
        suite_service.get_suite(run_job.suite_id)
        suites_registry = suite_service.get_registry()

        run_map: dict[str, RunJob] = {run_job.suite_id: run_job}
        case_id_maps: dict[str, dict[str, str]] = {}
        progress_counters: dict[str, list[int]] = {}
        executors: dict[str, Executor] = {}

        mode = run_job.mode

        def _client_factory(provider: str, cfg: AppConfig) -> tuple[HTTPClient, Any]:
            return _create_client(provider, cfg, mode)

        async def _on_suite_start(ctx: SuiteContext) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            cases = ctx.cases
            executors[sid] = ctx.executor
            rc = [test_case_to_run_case(job.id, c) for c in cases]
            persisted = run_repo.replace_run_cases(job.id, rc)
            case_id_maps[sid] = {row.case_id: row.id for row in persisted}
            progress_counters[sid] = [0, 0]  # [passed, failed]
            run_repo.mark_run_running(job, progress_total=len(cases))
            event_bus.start_run(job.id)
            event_bus.push(
                job.id,
                "run_started",
                {
                    "mode": job.mode,
                    "progress_total": job.progress_total,
                    "test_order": [c.test_name for c in cases],
                    "max_concurrent": max_concurrent,
                },
            )

        async def _on_test_start(case: TestCase, idx: int, total: int) -> None:
            for sid, cmap in case_id_maps.items():
                if case.case_id in cmap:
                    job = run_map[sid]
                    event_bus.push(
                        job.id, "test_started", {"test_name": case.test_name, "index": idx + 1}
                    )
                    return

        async def _on_test_done(progress: ExecutionProgress) -> None:
            case = progress.case
            verdict = progress.verdict
            for sid, cmap in case_id_maps.items():
                if case.case_id in cmap:
                    job = run_map[sid]
                    counters = progress_counters[sid]
                    if verdict.status == "pass":
                        counters[0] += 1
                    else:
                        counters[1] += 1
                    event_bus.push(
                        job.id,
                        "test_finished",
                        {
                            "test_name": case.test_name,
                            "index": progress.index + 1,
                            "status": verdict.status,
                            "progress_done": progress.done,
                            "progress_total": progress.total,
                            "progress_passed": counters[0],
                            "progress_failed": counters[1],
                            "test_result": _verdict_to_sse_payload(verdict),
                        },
                    )
                    run_repo.refresh(job)
                    if job.status == "cancelled":
                        executor = executors.get(sid)
                        if executor:
                            executor.cancel()
                    return

        async def _on_suite_done(ctx: SuiteContext, result: SuiteResult) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            cmap = case_id_maps.get(sid, {})
            counters = progress_counters.get(sid, [0, 0])
            verdicts = result.verdicts

            run_repo.refresh(job)
            if job.status == "cancelled" or ctx.executor.cancelled:
                done_count = counters[0] + counters[1]
                event_bus.push(
                    job.id,
                    "run_cancelled",
                    {"progress_done": done_count, "progress_total": len(verdicts)},
                )
                run_repo.append_event_and_commit(
                    job.id,
                    "run_cancelled",
                    {"progress_done": done_count, "progress_total": len(verdicts)},
                )
                event_bus.end_run(job.id)
                event_bus.cleanup(job.id)
                return

            test_rows: list[RunTestResult] = []
            cid_to_rcid: dict[str, str] = {}
            for v in verdicts:
                rcid = cmap.get(v.case_id, "")
                cid_to_rcid[v.case_id] = rcid
                test_rows.append(verdict_to_test_result_row(job.id, rcid, v))

            from llm_spec.results.task_result import build_run_result

            run_result = build_run_result(
                run_id=job.id,
                started_at=job.started_at.isoformat() if job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                provider=job.provider,
                model=job.model,
                route=job.route,
                endpoint=job.endpoint,
                suite_name=job.suite_name or "",
                verdicts=verdicts,
            )
            run_repo.complete_run_with_results(
                run_job=job,
                progress_done=len(verdicts),
                progress_passed=counters[0],
                progress_failed=counters[1],
                test_results=test_rows,
                result_json=run_result_to_dict(run_result, cid_to_rcid),
            )
            event_bus.push(
                job.id,
                "run_finished",
                {
                    "status": job.status,
                    "passed": job.progress_passed,
                    "failed": job.progress_failed,
                },
            )
            event_bus.end_run(job.id)
            event_bus.cleanup(job.id)

        async def _on_suite_error(ctx: SuiteContext, exc: Exception) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            run_repo.fail_run_with_event(job, str(exc))
            event_bus.push(job.id, "run_failed", {"error": str(exc)})
            event_bus.end_run(job.id)
            event_bus.cleanup(job.id)

        selected = set(run_job.selected_tests or []) or None
        selected_tests = {run_job.suite_id: selected} if selected else None

        try:
            asyncio.run(
                run_suites(
                    suites_registry,
                    app_config,
                    suite_ids=[run_job.suite_id],
                    selected_tests=selected_tests,
                    max_concurrent_suites=1,
                    max_concurrent_tests=max_concurrent,
                    on_test_start=_on_test_start,
                    on_test_done=_on_test_done,
                    on_suite_start=_on_suite_start,
                    on_suite_done=_on_suite_done,
                    on_suite_error=_on_suite_error,
                    client_factory=_client_factory,
                )
            )
        except Exception as exc:
            run_repo.fail_run_with_event(run_job, str(exc))
            event_bus.push(run_id, "run_failed", {"error": str(exc)})
            event_bus.end_run(run_id)
            event_bus.cleanup(run_id)

    # ── Task execution (multiple runs) ────────────────────

    def execute_task(
        self,
        db: Session,
        task_id: str,
        *,
        max_concurrent: int = 5,
        run_concurrency: int = 2,
    ) -> None:
        """Execute one task (all child runs) via core run_suites()."""
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        runs = run_repo.list_runs_by_task(task_id)
        active_runs = [r for r in runs if r.status in {"queued", "running"}]
        if not active_runs:
            return

        # Build suite_id → RunJob mapping
        run_map: dict[str, RunJob] = {}
        suite_ids: list[str] = []
        selected_tests: dict[str, set[str]] = {}
        mode = active_runs[0].mode  # all runs in a task share the same mode

        for run_job in active_runs:
            if run_job.suite_id is None:
                run_repo.fail_run_with_event(run_job, "suite_id is None")
                continue
            run_map[run_job.suite_id] = run_job
            suite_ids.append(run_job.suite_id)
            sel = set(run_job.selected_tests or [])
            if sel:
                selected_tests[run_job.suite_id] = sel

        if not suite_ids:
            return

        app_config = load_config(settings.app_toml_path)
        suite_service = SuiteService()
        suites_registry = suite_service.get_registry()

        # Per-suite mutable state closed over by callbacks
        case_id_maps: dict[str, dict[str, str]] = {}
        progress_counters: dict[str, list[int]] = {}  # [passed, failed]
        executors: dict[str, Executor] = {}

        def _client_factory(provider: str, cfg: AppConfig) -> tuple[HTTPClient, Any]:
            return _create_client(provider, cfg, mode)

        async def _on_suite_start(ctx: SuiteContext) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            cases = ctx.cases
            executors[sid] = ctx.executor
            rc = [test_case_to_run_case(job.id, c) for c in cases]
            persisted = run_repo.replace_run_cases(job.id, rc)
            case_id_maps[sid] = {row.case_id: row.id for row in persisted}
            progress_counters[sid] = [0, 0]
            run_repo.mark_run_running(job, progress_total=len(cases))
            event_bus.start_run(job.id)
            event_bus.push(
                job.id,
                "run_started",
                {
                    "mode": job.mode,
                    "progress_total": job.progress_total,
                    "test_order": [c.test_name for c in cases],
                    "max_concurrent": max_concurrent,
                },
            )

        async def _on_test_start(case: TestCase, idx: int, total: int) -> None:
            for sid, cmap in case_id_maps.items():
                if case.case_id in cmap:
                    job = run_map[sid]
                    event_bus.push(
                        job.id, "test_started", {"test_name": case.test_name, "index": idx + 1}
                    )
                    return

        async def _on_test_done(progress: ExecutionProgress) -> None:
            case = progress.case
            verdict = progress.verdict
            for sid, cmap in case_id_maps.items():
                if case.case_id in cmap:
                    job = run_map[sid]
                    counters = progress_counters[sid]
                    if verdict.status == "pass":
                        counters[0] += 1
                    else:
                        counters[1] += 1
                    event_bus.push(
                        job.id,
                        "test_finished",
                        {
                            "test_name": case.test_name,
                            "index": progress.index + 1,
                            "status": verdict.status,
                            "progress_done": progress.done,
                            "progress_total": progress.total,
                            "progress_passed": counters[0],
                            "progress_failed": counters[1],
                            "test_result": _verdict_to_sse_payload(verdict),
                        },
                    )
                    run_repo.refresh(job)
                    if job.status == "cancelled":
                        executor = executors.get(sid)
                        if executor:
                            executor.cancel()
                    return

        async def _on_suite_done(ctx: SuiteContext, result: SuiteResult) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            cmap = case_id_maps.get(sid, {})
            counters = progress_counters.get(sid, [0, 0])
            verdicts = result.verdicts

            run_repo.refresh(job)
            if job.status == "cancelled" or ctx.executor.cancelled:
                done_count = counters[0] + counters[1]
                event_bus.push(
                    job.id,
                    "run_cancelled",
                    {"progress_done": done_count, "progress_total": len(verdicts)},
                )
                run_repo.append_event_and_commit(
                    job.id,
                    "run_cancelled",
                    {"progress_done": done_count, "progress_total": len(verdicts)},
                )
                event_bus.end_run(job.id)
                event_bus.cleanup(job.id)
                return

            test_rows: list[RunTestResult] = []
            cid_to_rcid: dict[str, str] = {}
            for v in verdicts:
                rcid = cmap.get(v.case_id, "")
                cid_to_rcid[v.case_id] = rcid
                test_rows.append(verdict_to_test_result_row(job.id, rcid, v))

            from llm_spec.results.task_result import build_run_result

            run_result = build_run_result(
                run_id=job.id,
                started_at=job.started_at.isoformat() if job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                provider=job.provider,
                model=job.model,
                route=job.route,
                endpoint=job.endpoint,
                suite_name=job.suite_name or "",
                verdicts=verdicts,
            )
            run_repo.complete_run_with_results(
                run_job=job,
                progress_done=len(verdicts),
                progress_passed=counters[0],
                progress_failed=counters[1],
                test_results=test_rows,
                result_json=run_result_to_dict(run_result, cid_to_rcid),
            )
            event_bus.push(
                job.id,
                "run_finished",
                {
                    "status": job.status,
                    "passed": job.progress_passed,
                    "failed": job.progress_failed,
                },
            )
            event_bus.end_run(job.id)
            event_bus.cleanup(job.id)

            if job.task_id:
                self._task_service.update_task_status(db, job.task_id)

        async def _on_suite_error(ctx: SuiteContext, exc: Exception) -> None:
            sid = ctx.suite.suite_id
            job = run_map[sid]
            run_repo.fail_run_with_event(job, str(exc))
            event_bus.push(job.id, "run_failed", {"error": str(exc)})
            event_bus.end_run(job.id)
            event_bus.cleanup(job.id)

        try:
            asyncio.run(
                run_task_suites(
                    task_id=task_id,
                    registry=suites_registry,
                    config=app_config,
                    suite_ids=suite_ids,
                    selected_tests=selected_tests or None,
                    max_concurrent_suites=max(1, run_concurrency),
                    max_concurrent_tests=max_concurrent,
                    on_test_start=_on_test_start,
                    on_test_done=_on_test_done,
                    on_suite_start=_on_suite_start,
                    on_suite_done=_on_suite_done,
                    on_suite_error=_on_suite_error,
                    client_factory=_client_factory,
                )
            )
        except asyncio.CancelledError:
            return


def _verdict_to_sse_payload(verdict: TestVerdict) -> dict[str, Any]:
    """Build the test_result dict for SSE push."""
    return {
        "test_name": verdict.test_name,
        "focus": (
            {"name": verdict.focus.name, "value": verdict.focus.value} if verdict.focus else None
        ),
        "status": verdict.status,
        "latency_ms": verdict.latency_ms,
        "http_status": verdict.http_status,
        "schema_ok": verdict.schema_ok,
        "required_fields_ok": verdict.required_fields_ok,
        "stream_rules_ok": verdict.stream_rules_ok,
        "fail_stage": verdict.failure.stage if verdict.failure else None,
        "fail_message": verdict.failure.message if verdict.failure else None,
    }


def _merge_verdict_into_run_result(
    result_json: dict[str, Any],
    *,
    case_id: str,
    new_verdict: TestVerdict,
    run_case_id: str | None = None,
) -> dict[str, Any]:
    """Replace one case row in the stored run result JSON."""
    merged = deepcopy(result_json)
    cases = merged.get("cases")
    if not isinstance(cases, list):
        raise ValidationError("run result format invalid: missing cases")
    new_row = verdict_to_case_row(new_verdict, run_case_id)
    replaced = False
    for idx, row in enumerate(cases):
        if isinstance(row, dict) and str(row.get("run_case_id", "")) == run_case_id:
            cases[idx] = new_row
            replaced = True
            break
    if not replaced:
        cases.append(new_row)
    return merged
