"""Run service for business logic."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.orm import Session

from llm_spec.adapters.api_family import create_api_family_adapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig, load_config
from llm_spec.results.result_types import CaseResult, TaskResult
from llm_spec.results.task_result import build_task_result
from llm_spec.runners import ConfigDrivenTestRunner
from llm_spec.suites import ExecutableCase
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
    """Create a provider client based on mode and provider type.

    Args:
        provider: Provider name.
        config: Provider configuration.
        mode: Execution mode ("real" or "mock").
        http_client: HTTP client instance.

    Returns:
        Provider adapter instance.

    Raises:
        ValueError: If provider is not supported.
    """
    if mode == "mock":
        # Import here to avoid circular dependency
        from llm_spec_web.adapters.mock_adapter import MockProviderAdapter

        return MockProviderAdapter(
            config=config,
            base_dir=settings.mock_base_dir,
            provider_name=provider,
        )

    return create_api_family_adapter(provider=provider, config=config, http_client=http_client)


def _build_case_id(
    *,
    provider: str,
    route: str | None,
    model: str | None,
    test_name: str,
    parameter_name: str | None,
    parameter_value: Any,
) -> str:
    basis = {
        "provider": provider,
        "route": route,
        "model": model,
        "test_name": test_name,
        "parameter_name": parameter_name,
        "parameter_value": parameter_value,
    }
    digest = hashlib.sha1(
        json.dumps(basis, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"case_{digest}"


def load_suite_from_route_suite(
    route_suite: dict[str, Any], model_name: str | None
) -> list[ExecutableCase]:
    """Build executable-case list from a model-suite ``route_suite`` payload.

    Args:
        route_suite: Parsed route suite JSON.
        model_name: Selected model name for this model suite.

    Returns:
        Fully prepared executable cases.
    """
    provider = str(route_suite.get("provider") or "")
    endpoint_default = str(route_suite.get("endpoint") or "")
    method_default = str(route_suite.get("method") or "POST")
    route = str(route_suite.get("route") or "") or None
    suite_schemas = route_suite.get("schemas")
    suite_required_fields = route_suite.get("required_fields")
    suite_stream_expectations = route_suite.get("stream_expectations")
    tests_raw = route_suite.get("tests")
    if not isinstance(suite_schemas, dict):
        suite_schemas = {}
    if not isinstance(suite_required_fields, list):
        suite_required_fields = []
    if not isinstance(tests_raw, list):
        tests_raw = []

    baseline_params_raw = route_suite.get("baseline_params")
    if not isinstance(baseline_params_raw, dict):
        baseline_params_raw = route_suite.get("base_param")
    baseline_params: dict[str, Any] = (
        deepcopy(baseline_params_raw) if isinstance(baseline_params_raw, dict) else {}
    )
    for row in tests_raw:
        if isinstance(row, dict) and bool(row.get("baseline")):
            params = row.get("params")
            if isinstance(params, dict):
                baseline_params = deepcopy(params)
            break

    prepared: list[ExecutableCase] = []
    for row in tests_raw:
        if not isinstance(row, dict):
            continue
        test_name = str(row.get("name") or "")
        if not test_name:
            continue
        test_params = row.get("params")
        request_params = deepcopy(baseline_params)
        if isinstance(test_params, dict):
            request_params.update(deepcopy(test_params))
        if model_name:
            request_params["model"] = model_name

        endpoint_override = row.get("endpoint_override")
        endpoint = (
            str(endpoint_override) if isinstance(endpoint_override, str) else endpoint_default
        )
        method_override = row.get("method")
        method = str(method_override) if isinstance(method_override, str) else method_default
        param_name = None
        param_value: Any = None
        focus_param = row.get("focus_param")
        if isinstance(focus_param, dict):
            maybe_name = focus_param.get("name")
            if isinstance(maybe_name, str) and maybe_name:
                param_name = maybe_name
                param_value = focus_param.get("value")

        schemas = row.get("schemas")
        if not isinstance(schemas, dict):
            schemas = {}
        response_schema = schemas.get("response")
        stream_chunk_schema = schemas.get("stream_chunk")
        if not isinstance(response_schema, str):
            response_schema = suite_schemas.get("response")
        if not isinstance(stream_chunk_schema, str):
            stream_chunk_schema = suite_schemas.get("stream_chunk")

        required_fields = [str(v) for v in suite_required_fields if isinstance(v, str)]
        test_required = row.get("required_fields")
        if isinstance(test_required, list):
            required_fields.extend(str(v) for v in test_required if isinstance(v, str))

        stream_expectations = row.get("stream_expectations")
        if not isinstance(stream_expectations, dict):
            stream_expectations = (
                suite_stream_expectations if isinstance(suite_stream_expectations, dict) else None
            )

        tags_raw = row.get("tags")
        tags = [str(v) for v in tags_raw] if isinstance(tags_raw, list) else []
        files_raw = row.get("files")
        request_files = deepcopy(files_raw) if isinstance(files_raw, dict) else None

        case_id = _build_case_id(
            provider=provider,
            route=route,
            model=model_name,
            test_name=test_name,
            parameter_name=param_name,
            parameter_value=param_value,
        )
        prepared.append(
            ExecutableCase(
                case_id=case_id,
                test_name=test_name,
                description=str(row.get("description") or ""),
                provider=provider,
                route=route,
                model=model_name,
                request_method=method,
                request_endpoint=endpoint,
                request_params=request_params,
                request_files=request_files,
                check_stream=bool(row.get("check_stream")),
                response_schema=response_schema if isinstance(response_schema, str) else None,
                stream_chunk_schema=(
                    stream_chunk_schema if isinstance(stream_chunk_schema, str) else None
                ),
                required_fields=required_fields,
                stream_expectations=stream_expectations,
                parameter_name=param_name,
                parameter_value=param_value,
                parameter_value_type=(
                    type(param_value).__name__ if param_value is not None else "none"
                ),
                is_baseline=bool(row.get("baseline")),
                tags=tags,
            )
        )
    return prepared


@dataclass
class RunExecutionContext:
    """Prepared run context shared with async execution phase."""

    run_id: str
    run_job: RunJob
    run_repo: RunRepository
    task_id: str | None
    cases: list[ExecutableCase]
    client: Any
    http_client: HTTPClient
    max_concurrent: int


class RunService:
    """Service for run-related business logic.

    This class orchestrates run operations and manages transactions.
    """

    @staticmethod
    def _case_status(case: CaseResult) -> str:
        result = case.get("result")
        if isinstance(result, dict):
            value = result.get("status")
            if isinstance(value, str):
                return value
        return "fail"

    @staticmethod
    def _case_passed(case: CaseResult) -> bool:
        return RunService._case_status(case) == "pass"

    def get_run(self, db: Session, run_id: str) -> RunJob:
        """Get a run job by ID.

        Args:
            db: Database session.
            run_id: Run job ID.

        Returns:
            RunJob instance.

        Raises:
            NotFoundError: If run not found.
        """
        run_repo = RunRepository(db)
        run = run_repo.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Run", run_id)
        return run

    def list_events(
        self,
        db: Session,
        run_id: str,
        after_seq: int = 0,
    ) -> Sequence[RunEvent]:
        """List events for a run.

        Args:
            db: Database session.
            run_id: Run job ID.
            after_seq: Only return events with seq > after_seq.

        Returns:
            List of RunEvent instances.
        """
        run_repo = RunRepository(db)
        return run_repo.list_events(run_id, after_seq=after_seq)

    def get_task_result(self, db: Session, run_id: str) -> dict[str, Any]:
        """Get the task result for a run.

        Args:
            db: Database session.
            run_id: Run job ID.

        Returns:
            Task result JSON.

        Raises:
            NotFoundError: If task result not found.
        """
        run_repo = RunRepository(db)
        result = run_repo.get_task_result(run_id)
        if result is None:
            raise NotFoundError("TaskResult", run_id)
        return result.task_result_json

    def list_test_results(self, db: Session, run_id: str) -> list[dict]:
        """List test results for a run.

        Args:
            db: Database session.
            run_id: Run job ID.

        Returns:
            List of test result records.
        """
        run_repo = RunRepository(db)
        results = run_repo.list_test_results(run_id)
        return [r.raw_record for r in results]

    @staticmethod
    def _executable_case_to_run_case(run_id: str, case: ExecutableCase) -> RunCase:
        return RunCase(
            run_id=run_id,
            case_id=case.case_id,
            test_name=case.test_name,
            provider=case.provider,
            route=case.route,
            model=case.model,
            request_method=case.request_method,
            request_endpoint=case.request_endpoint,
            request_params=deepcopy(case.request_params),
            request_files=deepcopy(case.request_files) if case.request_files else None,
            check_stream=bool(case.check_stream),
            response_schema=case.response_schema,
            stream_chunk_schema=case.stream_chunk_schema,
            required_fields=list(case.required_fields),
            stream_expectations=(
                deepcopy(case.stream_expectations) if case.stream_expectations else None
            ),
            parameter_name=case.parameter_name,
            parameter_value=case.parameter_value,
            parameter_value_type=case.parameter_value_type,
            is_baseline=bool(case.is_baseline),
            tags=list(case.tags),
            description=case.description,
        )

    @staticmethod
    def _run_case_to_executable_case(run_case: RunCase) -> ExecutableCase:
        return ExecutableCase(
            case_id=run_case.case_id,
            test_name=run_case.test_name,
            description=run_case.description,
            provider=run_case.provider,
            route=run_case.route,
            model=run_case.model,
            request_method=run_case.request_method,
            request_endpoint=run_case.request_endpoint,
            request_params=deepcopy(run_case.request_params),
            request_files=deepcopy(run_case.request_files) if run_case.request_files else None,
            check_stream=bool(run_case.check_stream),
            response_schema=run_case.response_schema,
            stream_chunk_schema=run_case.stream_chunk_schema,
            required_fields=list(run_case.required_fields),
            stream_expectations=(
                deepcopy(run_case.stream_expectations) if run_case.stream_expectations else None
            ),
            parameter_name=run_case.parameter_name,
            parameter_value=run_case.parameter_value,
            parameter_value_type=run_case.parameter_value_type,
            is_baseline=bool(run_case.is_baseline),
            tags=list(run_case.tags),
            run_case_id=run_case.id,
        )

    def retry_test_in_run(self, db: Session, run_id: str, run_case_id: str) -> RunJob:
        """Retry one persisted run-case and persist updates back to the same run."""
        run_repo = RunRepository(db)

        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            raise NotFoundError("Run", run_id)
        if run_job.status in {"running", "queued"}:
            raise ValidationError(f"Run is still active: {run_id}")
        run_case = run_repo.get_run_case(run_case_id)
        if run_case is None or run_case.run_id != run_id:
            raise NotFoundError("RunCase", run_case_id)
        target_case = self._run_case_to_executable_case(run_case)

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
        target_case: ExecutableCase,
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

            case_result: CaseResult
            try:
                case_result = await ConfigDrivenTestRunner.run_executable_case_async(
                    target_case, client
                )
            except Exception as exc:
                case_result = {
                    "version": "case_result.v1",
                    "test_id": target_case.case_id,
                    "test_name": target_case.test_name,
                    "provider": target_case.provider,
                    "model": target_case.model,
                    "route": target_case.route,
                    "endpoint": target_case.request_endpoint,
                    "parameter": {"name": None, "value": None, "value_type": "none"},
                    "result": {
                        "status": "fail",
                        "fail_stage": "request",
                        "reason_code": "REQUEST_ERROR",
                        "reason": str(exc),
                    },
                    "request": {"ok": False, "http_status": 0},
                    "validation": {
                        "schema_ok": False,
                        "required_fields_ok": False,
                        "stream_rules_ok": False,
                        "missing_fields": [],
                        "missing_events": [],
                    },
                }

            result_record = case_result.get("result")
            result_record_dict = result_record if isinstance(result_record, dict) else {}
            request_record = case_result.get("request")
            request_record_dict = request_record if isinstance(request_record, dict) else {}
            parameter_record = case_result.get("parameter")
            parameter_record_dict = parameter_record if isinstance(parameter_record, dict) else {}
            status = str(result_record_dict.get("status", "fail"))
            run_repo.upsert_test_result_by_run_case_id(
                run_id=run_job.id,
                run_case_id=run_case.id,
                test_id=str(case_result.get("test_id", "")),
                test_name=str(case_result.get("test_name", target_case.test_name)),
                parameter_value=parameter_record_dict.get("value"),
                status=status,
                fail_stage=result_record_dict.get("fail_stage"),
                reason_code=result_record_dict.get("reason_code"),
                latency_ms=request_record_dict.get("latency_ms"),
                raw_record=dict(case_result),
            )

            task_result_row = run_repo.get_task_result(run_job.id)
            if task_result_row is None:
                raise NotFoundError("TaskResult", run_job.id)
            updated_task_result = self._merge_case_result_into_task_result(
                task_result_row.task_result_json,
                run_case_id=run_case.id,
                new_case_result=case_result,
            )
            task_result_row.task_result_json = dict(updated_task_result)
            run_repo.save_task_result(task_result_row)

            cases = updated_task_result.get("cases", [])
            case_rows = [c for c in cases if isinstance(c, dict)]
            run_job.progress_total = len(case_rows)
            run_job.progress_done = run_job.progress_total
            run_job.progress_passed = sum(1 for c in case_rows if self._case_passed(c))
            run_job.progress_failed = run_job.progress_total - run_job.progress_passed
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
                    "status": status,
                    "run_status": run_job.status,
                },
            )
            db.commit()
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                await http_client.close_async()

    def _merge_case_result_into_task_result(
        self,
        task_result_json: TaskResult | dict[str, Any],
        *,
        run_case_id: str,
        new_case_result: CaseResult,
    ) -> TaskResult:
        merged = cast(TaskResult, deepcopy(task_result_json))
        cases = merged.get("cases")
        if not isinstance(cases, list):
            raise ValidationError("task result format invalid: missing cases")
        replaced = False
        for idx, row in enumerate(cases):
            if isinstance(row, dict) and str(row.get("run_case_id", "")) == run_case_id:
                cases[idx] = new_case_result
                replaced = True
                break
        if not replaced:
            cases.append(new_case_result)
        merged["finished_at"] = datetime.now(UTC).isoformat()
        return merged

    def _prepare_run_context(
        self, run_repo: RunRepository, run_job: RunJob, max_concurrent: int
    ) -> RunExecutionContext:
        """Prepare model/provider/cases/client for one run before async execution."""
        suite_service = SuiteService()
        if run_job.model_suite_id is None:
            raise ValidationError("model_suite_id is None")

        model_suite = suite_service.resolve_model_suite(run_job.model_suite_id)

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

            executable_cases = load_suite_from_route_suite(
                model_suite.route_suite, model_suite.model_name
            )
            selected = set(run_job.selected_tests or [])
            cases = [c for c in executable_cases if not selected or c.test_name in selected]
            run_cases = [self._executable_case_to_run_case(run_job.id, case) for case in cases]
            persisted = run_repo.replace_run_cases(run_job.id, run_cases)
            by_case_id: dict[str, RunCase] = {row.case_id: row for row in persisted}
            for case in cases:
                row = by_case_id.get(case.case_id)
                if row is None:
                    raise ValidationError(f"run_case missing for case_id={case.case_id}")
                case.run_case_id = row.id

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
                client=client,
                http_client=http_client,
                max_concurrent=max_concurrent,
            )
        except Exception:
            with contextlib.suppress(Exception):
                asyncio.run(http_client.close_async())
            raise

    def execute_run(self, db: Session, run_id: str, max_concurrent: int = 5) -> None:
        """Execute a queued run job with concurrent test execution.

        This method is designed to be called in a background task.
        Uses asyncio for concurrent test execution.

        Args:
            db: Database session.
            run_id: Run job ID.
            max_concurrent: Maximum number of concurrent tests.
        """
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

        # Run the async execution phase in an event loop
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
            # Expected when task is cancelled from execution registry.
            return

    def cancel_task_execution(self, db: Session, task_id: str) -> Task:
        """Cancel an in-progress task by in-memory handle, then persist cancelled state."""
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

    async def _run_single_case_async(
        self,
        *,
        case: ExecutableCase,
        idx: int,
        client: Any,
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        """Run a single executable case under concurrency control."""
        async with semaphore:
            case_result: CaseResult
            try:
                case_result = await ConfigDrivenTestRunner.run_executable_case_async(case, client)
            except Exception as e:
                case_result = {
                    "version": "case_result.v1",
                    "run_case_id": case.run_case_id,
                    "test_id": case.case_id,
                    "test_name": case.test_name,
                    "provider": case.provider,
                    "model": case.model,
                    "route": case.route,
                    "endpoint": case.request_endpoint,
                    "parameter": {"name": None, "value": None, "value_type": "none"},
                    "request": {"ok": False, "http_status": 0, "latency_ms": 0},
                    "validation": {
                        "schema_ok": False,
                        "required_fields_ok": False,
                        "stream_rules_ok": False,
                        "missing_fields": [],
                        "missing_events": [],
                    },
                    "result": {"status": "fail", "reason": str(e)},
                }
            if case.run_case_id:
                case_result["run_case_id"] = case.run_case_id
            status = self._case_status(case_result)
            return {
                "case": case,
                "case_result": case_result,
                "status": status,
                "idx": idx,
            }

    async def run_by_context(self, context: RunExecutionContext) -> None:
        """Execute prepared runnable cases.

        Args:
            context: Prepared run context.
        """
        run_repo = context.run_repo
        run_id = context.run_id
        run_job = context.run_job
        task_id = context.task_id
        cases = context.cases
        client = context.client
        http_client = context.http_client
        max_concurrent = context.max_concurrent
        try:
            # Progress tracking (no locks needed in async)
            progress_done = 0
            progress_passed = 0
            progress_failed = 0
            cancelled = False

            # Collected case results
            test_results: list[dict[str, Any]] = []

            # Semaphore for controlling concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            # Create tasks for all tests
            tasks = []
            for idx, case in enumerate(cases, start=1):
                event_bus.push(run_id, "test_started", {"test_name": case.test_name, "index": idx})
                case_task = asyncio.create_task(
                    self._run_single_case_async(
                        case=case,
                        idx=idx,
                        client=client,
                        semaphore=semaphore,
                    )
                )
                tasks.append(case_task)
                if task_id:
                    execution_registry.register_case_task(
                        task_id, run_id, case.run_case_id, case_task
                    )

            # Wait for all tasks to complete, checking for cancellation
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

                        test_results.append(result)

                        case_result = cast(dict[str, Any], result["case_result"])
                        case_obj = cast(ExecutableCase, result["case"])
                        event_bus.push(
                            run_id,
                            "test_finished",
                            {
                                "test_name": case_obj.test_name,
                                "index": result["idx"],
                                "status": result["status"],
                                "progress_done": progress_done,
                                "progress_total": len(cases),
                                "progress_passed": progress_passed,
                                "progress_failed": progress_failed,
                                "test_result": {
                                    "test_name": case_result.get("test_name", case_obj.test_name),
                                    "parameter": case_result.get("parameter"),
                                    "request": case_result.get("request"),
                                    "result": case_result.get("result"),
                                    "validation": case_result.get("validation"),
                                },
                            },
                        )

                        # Check for cancellation periodically
                        run_repo.refresh(run_job)
                        if run_job.status == "cancelled":
                            cancelled = True
                            # Cancel remaining tasks
                            for t in tasks:
                                if not t.done():
                                    t.cancel()
                            break
                    except asyncio.CancelledError:
                        progress_done += 1
                        progress_failed += 1
                    except Exception as e:
                        # Handle test execution error
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
            test_results.sort(key=lambda x: x["idx"])
            case_results: list[CaseResult] = []
            test_rows: list[RunTestResult] = []
            for result in test_results:
                case_result = result["case_result"]
                # Save test result to database
                run_test_row = RunTestResult(
                    run_id=run_id,
                    run_case_id=cast(ExecutableCase, result["case"]).run_case_id,
                    test_id=str(case_result.get("test_id", "")),
                    test_name=str(case_result.get("test_name", result["case"].test_name)),
                    parameter_value=(case_result.get("parameter") or {}).get("value"),
                    status=result["status"],
                    fail_stage=(case_result.get("result") or {}).get("fail_stage"),
                    reason_code=(case_result.get("result") or {}).get("reason_code"),
                    latency_ms=(case_result.get("request") or {}).get("latency_ms"),
                    raw_record=dict(case_result),
                )
                test_rows.append(run_test_row)
                case_results.append(case_result)

            # Build and save result
            task_result = build_task_result(
                run_id=run_id,
                started_at=run_job.started_at.isoformat() if run_job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                provider=run_job.provider,
                model=run_job.model,
                route=run_job.route,
                endpoint=run_job.endpoint,
                cases=case_results,
            )
            run_job = run_repo.complete_run_with_results(
                run_job=run_job,
                progress_done=progress_done,
                progress_passed=progress_passed,
                progress_failed=progress_failed,
                test_results=test_rows,
                task_result_json=dict(task_result),
            )

            # Push terminal event to memory and cleanup
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

            # Push terminal event to memory
            event_bus.push(run_id, "run_failed", {"error": str(exc)})
            event_bus.end_run(run_id)
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                await http_client.close_async()
            # Cleanup event bus resources after a delay (allow client to receive terminal event)
            event_bus.cleanup(run_id)

    # ==================== Task Operations ====================

    def create_task(
        self,
        db: Session,
        model_suite_ids: list[str],
        mode: str | None = None,
        selected_tests_by_suite: dict[str, list[str]] | None = None,
        name: str | None = None,
    ) -> tuple[Task, list[RunJob]]:
        """Create a new task with multiple runs.

        Args:
            db: Database session.
            model_suite_ids: List of model suite IDs to run.
            mode: Execution mode ("real" or "mock").
            selected_tests_by_suite: Map of suite_id to list of test names.
            name: User-defined name for the task.

        Returns:
            Tuple of (Task instance, list of RunJob instances).

        Raises:
            NotFoundError: If any model suite not found.
        """
        run_repo = RunRepository(db)
        suite_service = SuiteService()

        # Resolve mode
        resolved_mode = mode or ("mock" if settings.mock_mode else "real")

        # Create task
        task = Task(
            name=name or "Task",
            status="running",
            mode=resolved_mode,
            total_runs=len(model_suite_ids),
            started_at=datetime.now(UTC),
        )

        # Build runs for each model suite
        run_jobs: list[RunJob] = []
        for model_suite_id in model_suite_ids:
            model_suite = suite_service.resolve_model_suite(model_suite_id)
            provider = model_suite.provider
            endpoint = str(model_suite.route_suite.get("endpoint"))
            route = str(model_suite.route_suite.get("route") or "")

            # Get selected tests for this suite
            suite_id = model_suite.id
            selected_tests = None
            if selected_tests_by_suite and suite_id in selected_tests_by_suite:
                selected_tests = selected_tests_by_suite[suite_id]

            # Build run job
            run_job = RunJob(
                status="queued",
                mode=resolved_mode,
                provider=provider,
                route=route or None,
                model=model_suite.model_name,
                endpoint=endpoint,
                model_suite_id=model_suite.id,
                selected_tests=selected_tests or [],
            )
            run_jobs.append(run_job)

        # Persist task and all runs via repository
        task, run_jobs = run_repo.create_task_with_runs(task, run_jobs)
        return task, run_jobs

    def get_task(self, db: Session, task_id: str) -> Task:
        """Get a task by ID.

        Args:
            db: Database session.
            task_id: Task ID.

        Returns:
            Task instance.

        Raises:
            NotFoundError: If task not found.
        """
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        return task

    def get_task_with_runs(self, db: Session, task_id: str) -> tuple[Task, Sequence[RunJob]]:
        """Get a task with its runs.

        Args:
            db: Database session.
            task_id: Task ID.

        Returns:
            Tuple of (Task instance, list of RunJob instances).

        Raises:
            NotFoundError: If task not found.
        """
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
        """List tasks with pagination.

        Args:
            db: Database session.
            status_filter: Filter by status.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            Tuple of (list of Task instances, total count).
        """
        run_repo = RunRepository(db)
        return run_repo.list_tasks(status_filter=status_filter, limit=limit, offset=offset)

    def update_task(self, db: Session, task_id: str, name: str) -> Task:
        """Update a task's name.

        Args:
            db: Database session.
            task_id: Task ID.
            name: New name for the task.

        Returns:
            Updated Task instance.

        Raises:
            NotFoundError: If task not found.
        """
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
        """Delete a task and all its runs.

        Args:
            db: Database session.
            task_id: Task ID.

        Returns:
            True if deleted, False if not found.
        """
        run_repo = RunRepository(db)
        result = run_repo.delete_task(task_id)
        if result:
            db.commit()
        return result

    def update_task_status(self, db: Session, task_id: str) -> Task:
        """Update task status based on its runs.

        Args:
            db: Database session.
            task_id: Task ID.

        Returns:
            Updated Task instance.
        """
        run_repo = RunRepository(db)
        task = run_repo.get_task_by_id(task_id)
        if task is None:
            raise NotFoundError("Task", task_id)
        if task.status == "cancelled":
            return task

        runs = run_repo.list_runs_by_task(task_id)

        # Count completed runs
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

        # Check if all runs are done
        if completed >= task.total_runs:
            task.status = "completed"
            task.finished_at = datetime.now(UTC)

        run_repo.update_task(task)
        db.commit()
        db.refresh(task)
        return task
