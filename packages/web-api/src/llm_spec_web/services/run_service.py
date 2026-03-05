"""Run service for business logic."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from llm_spec.adapters.api_family import create_api_family_adapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig, load_config
from llm_spec.results.result_types import FailureInfo, RunResult, TestVerdict
from llm_spec.results.task_result import build_run_result
from llm_spec.runners import TestRunner
from llm_spec.suites import SuiteSpec, TestCase, build_execution_plan
from llm_spec.suites.types import FocusParam, HttpRequest, ValidationSpec
from llm_spec_web.config import settings
from llm_spec_web.core.db import SessionLocal
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from llm_spec_web.core.execution_registry import execution_registry
from llm_spec_web.models.run import RunCase, RunEvent, RunJob, RunTestResult, Task
from llm_spec_web.repositories.run_repo import RunRepository
from llm_spec_web.services.suite_service import SuiteService


def create_provider_client(
    provider: str,
    config: ProviderConfig,
    mode: str,
    http_client: HTTPClient,
):
    """Create a provider client based on mode and provider type."""
    if mode == "mock":
        from llm_spec_web.adapters.mock_adapter import MockProviderAdapter

        return MockProviderAdapter(
            config=config,
            base_dir=settings.mock_base_dir,
            provider_name=provider,
        )

    return create_api_family_adapter(provider=provider, config=config, http_client=http_client)


# ── Mapping helpers ───────────────────────────────────────


def _test_case_to_run_case(run_id: str, case: TestCase) -> RunCase:
    """Persist a TestCase as a RunCase snapshot."""
    return RunCase(
        run_id=run_id,
        case_id=case.case_id,
        test_name=case.test_name,
        description=case.description,
        is_baseline=case.is_baseline,
        tags=list(case.tags),
        focus_name=case.focus.name if case.focus else None,
        focus_value=case.focus.value if case.focus else None,
        request_method=case.request.method,
        request_endpoint=case.request.endpoint,
        request_params=deepcopy(case.request.params),
        request_files=deepcopy(case.request.files) if case.request.files else None,
        request_stream=case.request.stream,
        response_schema=case.checks.response_schema,
        stream_chunk_schema=case.checks.stream_chunk_schema,
        required_fields=list(case.checks.required_fields),
        stream_rules=deepcopy(case.checks.stream_rules) if case.checks.stream_rules else None,
        provider=case.provider,
        model=case.model,
        route=case.route,
        api_family=case.api_family,
    )


def _run_case_to_test_case(run_case: RunCase) -> TestCase:
    """Reconstruct a TestCase from a persisted RunCase snapshot."""
    return TestCase(
        case_id=run_case.case_id,
        test_name=run_case.test_name,
        description=run_case.description,
        is_baseline=bool(run_case.is_baseline),
        tags=list(run_case.tags),
        focus=(
            FocusParam(name=run_case.focus_name, value=run_case.focus_value)
            if run_case.focus_name
            else None
        ),
        request=HttpRequest(
            method=run_case.request_method,
            endpoint=run_case.request_endpoint,
            params=deepcopy(run_case.request_params),
            files=deepcopy(run_case.request_files) if run_case.request_files else None,
            stream=bool(run_case.request_stream),
        ),
        checks=ValidationSpec(
            response_schema=run_case.response_schema,
            stream_chunk_schema=run_case.stream_chunk_schema,
            required_fields=list(run_case.required_fields),
            stream_rules=deepcopy(run_case.stream_rules) if run_case.stream_rules else None,
        ),
        provider=run_case.provider,
        model=run_case.model,
        route=run_case.route,
        api_family=run_case.api_family,
    )


def _verdict_to_test_result_row(
    run_id: str, run_case_id: str | None, verdict: TestVerdict
) -> RunTestResult:
    """Map a TestVerdict to a RunTestResult ORM row."""
    return RunTestResult(
        run_id=run_id,
        run_case_id=run_case_id,
        case_id=verdict.case_id,
        test_name=verdict.test_name,
        focus_name=verdict.focus.name if verdict.focus else None,
        focus_value=verdict.focus.value if verdict.focus else None,
        status=verdict.status,
        latency_ms=verdict.latency_ms,
        http_status=verdict.http_status,
        schema_ok=verdict.schema_ok,
        required_fields_ok=verdict.required_fields_ok,
        stream_rules_ok=verdict.stream_rules_ok,
        fail_stage=verdict.failure.stage if verdict.failure else None,
        fail_code=verdict.failure.code if verdict.failure else None,
        fail_message=verdict.failure.message if verdict.failure else None,
        missing_fields=list(verdict.failure.missing_fields) if verdict.failure else [],
        missing_events=list(verdict.failure.missing_events) if verdict.failure else [],
        started_at=verdict.started_at,
        finished_at=verdict.finished_at,
    )


def _error_verdict(case: TestCase, error: Exception) -> TestVerdict:
    """Build an error TestVerdict for a case that failed before execution."""
    now = datetime.now(UTC).isoformat()
    return TestVerdict(
        case_id=case.case_id,
        test_name=case.test_name,
        focus=case.focus,
        status="error",
        started_at=now,
        finished_at=now,
        failure=FailureInfo(
            stage="request",
            code="REQUEST_ERROR",
            message=str(error),
        ),
    )


def _verdict_to_dict(verdict: TestVerdict) -> dict[str, Any]:
    """Serialize a TestVerdict to a JSON-safe dict."""
    return dataclasses.asdict(verdict)


def _verdict_to_case_row(verdict: TestVerdict, run_case_id: str | None = None) -> dict[str, Any]:
    """Convert a TestVerdict into the front-end TestResultRow shape.

    Expected by CompletedRunCard:
      { run_case_id, test_name, parameter?, request?, result?, validation? }
    """
    row: dict[str, Any] = {
        "test_name": verdict.test_name,
    }
    if run_case_id:
        row["run_case_id"] = run_case_id
    if verdict.focus:
        row["parameter"] = {
            "name": verdict.focus.name,
            "value": verdict.focus.value,
            "value_type": type(verdict.focus.value).__name__
            if verdict.focus.value is not None
            else "str",
        }
    if verdict.http_status is not None or verdict.latency_ms is not None:
        row["request"] = {
            "http_status": verdict.http_status or 0,
            "latency_ms": verdict.latency_ms or 0,
        }
    row["result"] = {
        "status": verdict.status,
    }
    if verdict.failure:
        row["result"]["reason"] = verdict.failure.message
    row["validation"] = {
        "schema_ok": verdict.schema_ok if verdict.schema_ok is not None else True,
        "required_fields_ok": verdict.required_fields_ok
        if verdict.required_fields_ok is not None
        else True,
        "stream_rules_ok": verdict.stream_rules_ok if verdict.stream_rules_ok is not None else True,
        "missing_fields": verdict.failure.missing_fields if verdict.failure else [],
        "missing_events": verdict.failure.missing_events if verdict.failure else [],
    }
    return row


def _run_result_to_dict(
    result: RunResult,
    case_id_to_run_case_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Serialize a RunResult to the JSON shape expected by the front-end."""
    mapping = case_id_to_run_case_id or {}
    return {
        "version": result.version,
        "run_id": result.run_id,
        "cases": [_verdict_to_case_row(v, mapping.get(v.case_id)) for v in result.verdicts],
    }


@dataclass
class RunExecutionContext:
    """Prepared run context shared with async execution phase."""

    run_id: str
    run_job: RunJob
    run_repo: RunRepository
    task_id: str | None
    cases: list[TestCase]
    suite: SuiteSpec | None
    client: Any
    http_client: HTTPClient
    max_concurrent: int
    case_id_to_run_case_id: dict[str, str] = field(default_factory=dict)


class RunService:
    """Service for run-related business logic."""

    # ── Run queries ───────────────────────────────────────

    def get_run(self, db: Session, run_id: str) -> RunJob:
        run_repo = RunRepository(db)
        run = run_repo.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Run", run_id)
        return run

    def list_events(self, db: Session, run_id: str, after_seq: int = 0) -> Sequence[RunEvent]:
        run_repo = RunRepository(db)
        return run_repo.list_events(run_id, after_seq=after_seq)

    def get_task_result(self, db: Session, run_id: str) -> dict[str, Any]:
        """Get the run result JSON for a run (legacy endpoint name kept)."""
        run_repo = RunRepository(db)
        result = run_repo.get_run_result(run_id)
        if result is None:
            raise NotFoundError("RunResult", run_id)
        return result.result_json

    def list_test_results(self, db: Session, run_id: str) -> list[dict]:
        """List test results for a run as dicts."""
        run_repo = RunRepository(db)
        results = run_repo.list_test_results(run_id)
        out: list[dict] = []
        for r in results:
            out.append(
                {
                    "case_id": r.case_id,
                    "test_name": r.test_name,
                    "focus_name": r.focus_name,
                    "focus_value": r.focus_value,
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "http_status": r.http_status,
                    "schema_ok": r.schema_ok,
                    "required_fields_ok": r.required_fields_ok,
                    "stream_rules_ok": r.stream_rules_ok,
                    "fail_stage": r.fail_stage,
                    "fail_code": r.fail_code,
                    "fail_message": r.fail_message,
                    "missing_fields": r.missing_fields,
                    "missing_events": r.missing_events,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                }
            )
        return out

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
        target_case = _run_case_to_test_case(run_case)

        app_config = load_config(settings.app_toml_path)
        provider_cfg = None
        try:
            provider_cfg = app_config.get_provider_config(run_job.provider)
        except KeyError:
            provider_cfg = None
        if provider_cfg is None and run_job.mode != "mock":
            raise ConfigurationError(f"provider config missing: {run_job.provider}")

        asyncio.run(
            self._retry_test_in_run_async(
                db=db,
                run_repo=run_repo,
                run_job=run_job,
                run_case=run_case,
                target_case=target_case,
                provider_cfg=provider_cfg,
            )
        )
        if run_job.task_id:
            self.update_task_status(db, run_job.task_id)
        db.refresh(run_job)
        return run_job

    async def _retry_test_in_run_async(
        self,
        *,
        db: Session,
        run_repo: RunRepository,
        run_job: RunJob,
        run_case: RunCase,
        target_case: TestCase,
        provider_cfg: Any,
    ) -> None:
        http_client = None
        try:
            if provider_cfg is None:
                config = ProviderConfig(api_key="", base_url="", timeout=30.0)
            else:
                config = ProviderConfig(
                    api_key=provider_cfg.api_key,
                    base_url=provider_cfg.base_url,
                    timeout=provider_cfg.timeout,
                    api_family=provider_cfg.api_family,
                    headers=provider_cfg.headers,
                )

            http_client = HTTPClient(default_timeout=config.timeout)
            client = create_provider_client(run_job.provider, config, run_job.mode, http_client)

            runner = TestRunner(client=client)
            try:
                verdict = await runner.run_async(target_case)
            except Exception as exc:
                verdict = _error_verdict(target_case, exc)

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
            updated_json = self._merge_verdict_into_run_result(
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

    @staticmethod
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
        new_row = _verdict_to_case_row(new_verdict, run_case_id)
        replaced = False
        for idx, row in enumerate(cases):
            if isinstance(row, dict) and str(row.get("run_case_id", "")) == run_case_id:
                cases[idx] = new_row
                replaced = True
                break
        if not replaced:
            cases.append(new_row)
        return merged

    # ── Single case execution ─────────────────────────────

    async def _run_single_case_async(
        self,
        *,
        case: TestCase,
        idx: int,
        runner: TestRunner,
        run_case_id: str | None,
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        """Run a single test case under concurrency control."""
        async with semaphore:
            try:
                verdict = await runner.run_async(case)
            except Exception as e:
                verdict = _error_verdict(case, e)

            return {
                "case": case,
                "verdict": verdict,
                "run_case_id": run_case_id,
                "status": verdict.status,
                "idx": idx,
            }

    # ── Prepare and execute ───────────────────────────────

    def _prepare_run_context(
        self, run_repo: RunRepository, run_job: RunJob, max_concurrent: int
    ) -> RunExecutionContext:
        """Prepare cases/client for one run before async execution."""
        suite_service = SuiteService()
        if run_job.suite_id is None:
            raise ValidationError("suite_id is None")

        suite = suite_service.get_suite(run_job.suite_id)

        app_config = load_config(settings.app_toml_path)
        provider_cfg = None
        try:
            provider_cfg = app_config.get_provider_config(run_job.provider)
        except KeyError:
            provider_cfg = None
        if provider_cfg is None and run_job.mode != "mock":
            raise ConfigurationError(f"provider config missing: {run_job.provider}")

        if provider_cfg is None:
            config = ProviderConfig(api_key="", base_url="", timeout=30.0)
        else:
            config = ProviderConfig(
                api_key=provider_cfg.api_key,
                base_url=provider_cfg.base_url,
                timeout=provider_cfg.timeout,
                api_family=provider_cfg.api_family,
                headers=provider_cfg.headers,
            )
        http_client = HTTPClient(default_timeout=config.timeout)
        try:
            client = create_provider_client(run_job.provider, config, run_job.mode, http_client)

            selected = set(run_job.selected_tests or []) or None
            cases = build_execution_plan(suite, selected_tests=selected)

            run_cases = [_test_case_to_run_case(run_job.id, case) for case in cases]
            persisted = run_repo.replace_run_cases(run_job.id, run_cases)
            case_id_to_run_case_id: dict[str, str] = {row.case_id: row.id for row in persisted}

            run_repo.mark_run_running(run_job, progress_total=len(cases))

            event_bus.start_run(run_job.id)
            event_bus.push(
                run_job.id,
                "run_started",
                {
                    "mode": run_job.mode,
                    "progress_total": run_job.progress_total,
                    "test_order": [c.test_name for c in cases],
                    "max_concurrent": max_concurrent,
                },
            )

            return RunExecutionContext(
                run_id=run_job.id,
                run_job=run_job,
                run_repo=run_repo,
                task_id=run_job.task_id,
                cases=cases,
                suite=suite,
                client=client,
                http_client=http_client,
                max_concurrent=max_concurrent,
                case_id_to_run_case_id=case_id_to_run_case_id,
            )
        except Exception:
            with contextlib.suppress(Exception):
                asyncio.run(http_client.close_async())
            raise

    async def run_by_context(self, context: RunExecutionContext) -> None:
        """Execute prepared test cases."""
        run_repo = context.run_repo
        run_id = context.run_id
        run_job = context.run_job
        task_id = context.task_id
        cases = context.cases
        client = context.client
        http_client = context.http_client
        max_concurrent = context.max_concurrent
        suite = context.suite
        case_id_map = context.case_id_to_run_case_id

        try:
            runner = TestRunner(
                client=client,
                source_path=suite.source_path if suite else None,
            )

            progress_done = 0
            progress_passed = 0
            progress_failed = 0
            cancelled = False

            collected: list[dict[str, Any]] = []

            semaphore = asyncio.Semaphore(max_concurrent)
            tasks: list[asyncio.Task[dict[str, Any]]] = []
            for idx, case in enumerate(cases, start=1):
                event_bus.push(run_id, "test_started", {"test_name": case.test_name, "index": idx})
                run_case_id = case_id_map.get(case.case_id)
                case_task = asyncio.create_task(
                    self._run_single_case_async(
                        case=case,
                        idx=idx,
                        runner=runner,
                        run_case_id=run_case_id,
                        semaphore=semaphore,
                    )
                )
                tasks.append(case_task)
                if task_id:
                    execution_registry.register_case_task(task_id, run_id, run_case_id, case_task)

            try:
                for coro in asyncio.as_completed(tasks):
                    try:
                        result = await coro
                        if cancelled:
                            continue

                        progress_done += 1
                        if result["status"] == "pass":
                            progress_passed += 1
                        else:
                            progress_failed += 1

                        collected.append(result)

                        verdict = cast(TestVerdict, result["verdict"])
                        case_obj = cast(TestCase, result["case"])
                        event_bus.push(
                            run_id,
                            "test_finished",
                            {
                                "test_name": case_obj.test_name,
                                "index": result["idx"],
                                "status": verdict.status,
                                "progress_done": progress_done,
                                "progress_total": len(cases),
                                "progress_passed": progress_passed,
                                "progress_failed": progress_failed,
                                "test_result": {
                                    "test_name": verdict.test_name,
                                    "focus": (
                                        {
                                            "name": verdict.focus.name,
                                            "value": verdict.focus.value,
                                        }
                                        if verdict.focus
                                        else None
                                    ),
                                    "status": verdict.status,
                                    "latency_ms": verdict.latency_ms,
                                    "http_status": verdict.http_status,
                                    "schema_ok": verdict.schema_ok,
                                    "required_fields_ok": verdict.required_fields_ok,
                                    "stream_rules_ok": verdict.stream_rules_ok,
                                    "fail_stage": (
                                        verdict.failure.stage if verdict.failure else None
                                    ),
                                    "fail_message": (
                                        verdict.failure.message if verdict.failure else None
                                    ),
                                },
                            },
                        )

                        # Check for cancellation periodically
                        run_repo.refresh(run_job)
                        if run_job.status == "cancelled":
                            cancelled = True
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                            break
                    except asyncio.CancelledError:
                        progress_done += 1
                        progress_failed += 1
                    except Exception as e:
                        progress_done += 1
                        progress_failed += 1
                        event_bus.push(
                            run_id,
                            "test_finished",
                            {
                                "test_name": "unknown",
                                "status": "fail",
                                "progress_done": progress_done,
                                "progress_total": len(cases),
                                "progress_passed": progress_passed,
                                "progress_failed": progress_failed,
                                "error": str(e),
                            },
                        )
            except asyncio.CancelledError:
                cancelled = True

            # Check if cancelled
            run_repo.refresh(run_job)
            if run_job.status == "cancelled" or cancelled:
                event_bus.push(
                    run_id,
                    "run_cancelled",
                    {
                        "progress_done": progress_done,
                        "progress_total": len(cases),
                    },
                )
                run_repo.append_event_and_commit(
                    run_id,
                    "run_cancelled",
                    {
                        "progress_done": progress_done,
                        "progress_total": len(cases),
                    },
                )
                event_bus.end_run(run_id)
                return

            # Sort and persist case results
            collected.sort(key=lambda x: x["idx"])
            verdicts: list[TestVerdict] = []
            test_rows: list[RunTestResult] = []
            cid_to_rcid: dict[str, str] = {}
            for item in collected:
                verdict = item["verdict"]
                verdicts.append(verdict)
                cid_to_rcid[verdict.case_id] = item["run_case_id"]
                test_rows.append(_verdict_to_test_result_row(run_id, item["run_case_id"], verdict))

            run_result = build_run_result(
                run_id=run_id,
                started_at=run_job.started_at.isoformat() if run_job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                provider=run_job.provider,
                model=run_job.model,
                route=run_job.route,
                endpoint=run_job.endpoint,
                suite_name=run_job.suite_name or "",
                verdicts=verdicts,
            )
            run_job = run_repo.complete_run_with_results(
                run_job=run_job,
                progress_done=progress_done,
                progress_passed=progress_passed,
                progress_failed=progress_failed,
                test_results=test_rows,
                result_json=_run_result_to_dict(run_result, cid_to_rcid),
            )

            event_bus.push(
                run_id,
                "run_finished",
                {
                    "status": run_job.status,
                    "passed": run_job.progress_passed,
                    "failed": run_job.progress_failed,
                },
            )
            event_bus.end_run(run_id)

        except Exception as exc:
            run_repo.fail_run_with_event(run_job, str(exc))
            event_bus.push(run_id, "run_failed", {"error": str(exc)})
            event_bus.end_run(run_id)
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                await http_client.close_async()
            event_bus.cleanup(run_id)

    # ── Task operations ───────────────────────────────────

    def create_task(
        self,
        db: Session,
        suite_ids: list[str],
        mode: str | None = None,
        selected_tests_by_suite: dict[str, list[str]] | None = None,
        name: str | None = None,
    ) -> tuple[Task, list[RunJob]]:
        run_repo = RunRepository(db)
        suite_service = SuiteService()

        resolved_mode = mode or ("mock" if settings.mock_mode else "real")

        task = Task(
            name=name or "Task",
            status="running",
            mode=resolved_mode,
            total_runs=len(suite_ids),
            started_at=datetime.now(UTC),
        )

        run_jobs: list[RunJob] = []
        for suite_id in suite_ids:
            suite = suite_service.get_suite(suite_id)

            selected_tests = None
            if selected_tests_by_suite and suite_id in selected_tests_by_suite:
                selected_tests = selected_tests_by_suite[suite_id]

            run_job = RunJob(
                status="queued",
                mode=resolved_mode,
                provider=suite.provider_id,
                route=suite.route_id,
                model=suite.model_id,
                endpoint=suite.endpoint,
                suite_id=suite.suite_id,
                suite_name=suite.suite_name,
                selected_tests=selected_tests or [],
            )
            run_jobs.append(run_job)

        task, run_jobs = run_repo.create_task_with_runs(task, run_jobs)
        return task, run_jobs

    def get_task(self, db: Session, task_id: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    def get_task_with_runs(self, db: Session, task_id: str) -> tuple[Task, Sequence[RunJob]]:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        runs = run_repo.list_runs_by_task(task_id)
        return task, runs

    def list_tasks(
        self,
        db: Session,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Task], int]:
        run_repo = RunRepository(db)
        return run_repo.list_tasks(status_filter=status_filter, limit=limit, offset=offset)

    def update_task(self, db: Session, task_id: str, name: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        task.name = name
        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task

    def delete_task(self, db: Session, task_id: str) -> bool:
        run_repo = RunRepository(db)
        result = run_repo.delete_task(task_id)
        if result:
            db.commit()
        return result

    def update_task_status(self, db: Session, task_id: str) -> Task:
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        if task.status == "cancelled":
            return task

        runs = run_repo.list_runs_by_task(task_id)

        completed = 0
        passed = 0
        failed = 0
        for run in runs:
            if run.status in {"success", "failed", "cancelled"}:
                completed += 1
                if run.status == "success":
                    passed += 1
                elif run.status == "failed":
                    failed += 1

        task.completed_runs = completed
        task.passed_runs = passed
        task.failed_runs = failed

        if completed >= task.total_runs:
            task.status = "completed"
            task.finished_at = datetime.now(UTC)

        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task

    # ── Execution orchestration ───────────────────────────

    def execute_run(self, db: Session, run_id: str, max_concurrent: int = 5) -> None:
        run_repo = RunRepository(db)
        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            return

        try:
            context = self._prepare_run_context(run_repo, run_job, max_concurrent)
        except Exception as exc:
            run_repo.fail_run_with_event(run_job, str(exc))
            event_bus.push(run_id, "run_failed", {"error": str(exc)})
            event_bus.end_run(run_id)
            event_bus.cleanup(run_id)
            return

        asyncio.run(self.run_by_context(context))

    async def _execute_run_by_id_async(
        self, run_id: str, max_concurrent: int = 5, *, task_id: str | None = None
    ) -> None:
        """Execute one run by ID inside an existing event loop."""
        db = SessionLocal()
        try:
            run_repo = RunRepository(db)
            run_job = run_repo.get_by_id(run_id)
            if run_job is None:
                return
            try:
                context = self._prepare_run_context(run_repo, run_job, max_concurrent)
            except Exception as exc:
                run_repo.fail_run_with_event(run_job, str(exc))
                event_bus.push(run_id, "run_failed", {"error": str(exc)})
                event_bus.end_run(run_id)
                event_bus.cleanup(run_id)
                return
            if task_id is not None:
                context.task_id = task_id
            await self.run_by_context(context)
            if run_job.task_id:
                self.update_task_status(db, run_job.task_id)
        finally:
            db.close()

    async def _execute_task_async(
        self,
        task_id: str,
        run_ids: list[str],
        *,
        max_concurrent: int,
        run_concurrency: int,
    ) -> None:
        """Execute all runs in one task under a task-level async root."""
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("task root not available")
        execution_registry.register_task(
            task_id, asyncio.get_running_loop(), cast(asyncio.Task[object], current)
        )
        semaphore = asyncio.Semaphore(max(1, run_concurrency))
        try:

            async def _run_one(run_id: str) -> None:
                async with semaphore:
                    execution_registry.register_run(task_id, run_id)
                    await self._execute_run_by_id_async(run_id, max_concurrent, task_id=task_id)

            await asyncio.gather(*(_run_one(run_id) for run_id in run_ids))
        finally:
            execution_registry.unregister_task(task_id)

    def execute_task(
        self,
        db: Session,
        task_id: str,
        *,
        max_concurrent: int = 5,
        run_concurrency: int = 2,
    ) -> None:
        """Execute one task (all child runs) in a single background root."""
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        runs = run_repo.list_runs_by_task(task_id)
        run_ids = [run.id for run in runs if run.status in {"queued", "running"}]
        if not run_ids:
            return
        try:
            asyncio.run(
                self._execute_task_async(
                    task_id=task_id,
                    run_ids=run_ids,
                    max_concurrent=max_concurrent,
                    run_concurrency=run_concurrency,
                )
            )
        except asyncio.CancelledError:
            return

    def cancel_task_execution(self, db: Session, task_id: str) -> Task:
        """Cancel an in-progress task."""
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)

        execution_registry.cancel_task(task_id)
        runs = run_repo.list_runs_by_task(task_id)
        now = datetime.now(UTC)
        for run in runs:
            if run.status in {"queued", "running"}:
                run.status = "cancelled"
                run.finished_at = now
                run_repo.update(run)
                run_repo.append_event(run.id, "run_cancelled", {"reason": "task_cancelled"})
                event_bus.push(run.id, "run_cancelled", {"reason": "task_cancelled"})
                event_bus.end_run(run.id)
                event_bus.cleanup(run.id)

        task.status = "cancelled"
        task.finished_at = now
        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task
