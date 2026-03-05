"""Run execution service — async orchestration, retry, and provider client creation."""

from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from llm_spec.adapters.api_family import create_api_family_adapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig, load_config
from llm_spec.results.result_types import TestVerdict
from llm_spec.results.task_result import build_run_result
from llm_spec.runners import TestRunner
from llm_spec.suites import SuiteSpec, TestCase, build_execution_plan
from llm_spec_web.config import settings
from llm_spec_web.core.db import SessionLocal
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from llm_spec_web.core.execution_registry import execution_registry
from llm_spec_web.models.run import RunJob, RunTestResult
from llm_spec_web.repositories.run_repo import RunRepository
from llm_spec_web.services.mappers import (
    error_verdict,
    run_case_to_test_case,
    run_result_to_dict,
    test_case_to_run_case,
    verdict_to_case_row,
    verdict_to_test_result_row,
)
from llm_spec_web.services.suite_service import SuiteService
from llm_spec_web.services.task_service import TaskService


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
                verdict = error_verdict(target_case, exc)

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
                verdict = error_verdict(case, e)

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

            run_cases = [test_case_to_run_case(run_job.id, case) for case in cases]
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
                test_rows.append(verdict_to_test_result_row(run_id, item["run_case_id"], verdict))

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
                result_json=run_result_to_dict(run_result, cid_to_rcid),
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
                self._task_service.update_task_status(db, run_job.task_id)
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
