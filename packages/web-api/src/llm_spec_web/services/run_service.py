"""Run service for business logic."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.cli import _build_run_result
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import LogConfig, ProviderConfig, load_config
from llm_spec.logger import RequestLogger
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.runners import ConfigDrivenTestRunner, SpecTestSuite, load_test_suite_from_dict
from llm_spec_web.config import settings
from llm_spec_web.core.event_bus import event_bus
from llm_spec_web.core.exceptions import NotFoundError
from llm_spec_web.models.run import RunBatch, RunEvent, RunJob, RunResult, RunTestResult
from llm_spec_web.repositories.run_repo import RunRepository
from llm_spec_web.services.suite_service import SuiteService

# API-family adapter registry
API_FAMILY_ADAPTERS: dict[str, type] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "xai": XAIAdapter,
}


def create_provider_client(
    provider: str,
    config: ProviderConfig,
    mode: str,
    logger: RequestLogger | None,
    http_client: HTTPClient,
):
    """Create a provider client based on mode and provider type.

    Args:
        provider: Provider name.
        config: Provider configuration.
        mode: Execution mode ("real" or "mock").
        logger: Request logger.
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

    adapter_class = API_FAMILY_ADAPTERS.get(config.api_family or provider)
    if adapter_class is None:
        raise ValueError(f"Unsupported provider/api_family: {provider}/{config.api_family}")

    return adapter_class(config, http_client, logger)


def load_suite_from_version(parsed_json: dict[str, Any]) -> SpecTestSuite:
    """Load test suite from a SuiteVersion.

    Args:
        parsed_json: Parsed suite JSON.

    Returns:
        Loaded test suite.
    """
    return load_test_suite_from_dict(parsed_json)


class RunService:
    """Service for run-related business logic.

    This class orchestrates run operations and manages transactions.
    """

    def create_run(
        self,
        db: Session,
        suite_version_id: str,
        mode: str | None = None,
        selected_tests: list[str] | None = None,
    ) -> RunJob:
        """Create a new run job.

        Args:
            db: Database session.
            suite_version_id: Suite version ID.
            mode: Execution mode ("real" or "mock").
            selected_tests: List of test names to run.

        Returns:
            Created RunJob instance.

        Raises:
            NotFoundError: If suite version not found.
        """
        run_repo = RunRepository(db)
        suite_service = SuiteService()

        suite_version = suite_service.resolve_suite_by_version_id(suite_version_id)

        provider = str(suite_version.parsed_json.get("provider"))
        endpoint = str(suite_version.parsed_json.get("endpoint"))

        # Resolve mode
        resolved_mode = mode or ("mock" if settings.mock_mode else "real")

        # Create run job
        run = RunJob(
            status="queued",
            mode=resolved_mode,
            provider=provider,
            endpoint=endpoint,
            suite_version_id=suite_version_id,
            config_snapshot={"selected_tests": selected_tests or []},
        )
        run_repo.create(run)
        db.commit()
        db.refresh(run)
        return run

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

    def list_runs(self, db: Session, status_filter: str | None = None) -> Sequence[RunJob]:
        """List all run jobs.

        Args:
            db: Database session.
            status_filter: Filter by status.

        Returns:
            List of RunJob instances.
        """
        run_repo = RunRepository(db)
        return run_repo.list_all(status_filter=status_filter)

    def cancel_run(self, db: Session, run_id: str) -> RunJob:
        """Cancel a run job.

        Args:
            db: Database session.
            run_id: Run job ID.

        Returns:
            Updated RunJob instance.

        Raises:
            NotFoundError: If run not found.
        """
        run_repo = RunRepository(db)
        run = run_repo.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Run", run_id)

        if run.status in {"success", "failed", "cancelled"}:
            return run

        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        run_repo.update(run)
        db.commit()
        db.refresh(run)
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

    def get_result(self, db: Session, run_id: str) -> dict[str, Any]:
        """Get the result for a run.

        Args:
            db: Database session.
            run_id: Run job ID.

        Returns:
            Run result JSON.

        Raises:
            NotFoundError: If result not found.
        """
        run_repo = RunRepository(db)
        result = run_repo.get_result(run_id)
        if result is None:
            raise NotFoundError("RunResult", run_id)
        return result.run_result_json

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

    def execute_run(self, db: Session, run_id: str, max_concurrent: int = 5) -> None:
        """Execute a queued run job with concurrent test execution.

        This method is designed to be called in a background task.
        Uses asyncio for concurrent test execution.

        Args:
            db: Database session.
            run_id: Run job ID.
            max_concurrent: Maximum number of concurrent tests.
        """
        # Run the async implementation in an event loop
        asyncio.run(self._execute_run_async(db, run_id, max_concurrent))

    async def _execute_run_async(self, db: Session, run_id: str, max_concurrent: int) -> None:
        """Async implementation of execute_run.

        Args:
            db: Database session.
            run_id: Run job ID.
            max_concurrent: Maximum number of concurrent tests.
        """
        run_repo = RunRepository(db)
        suite_service = SuiteService()

        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            return

        if run_job.suite_version_id is None:
            run_job.status = "failed"
            run_job.error_message = "suite_version_id is None"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        try:
            suite_version = suite_service.resolve_suite_by_version_id(run_job.suite_version_id)
        except NotFoundError:
            run_job.status = "failed"
            run_job.error_message = f"suite_version not found: {run_job.suite_version_id}"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        app_config = load_config(settings.app_toml_path)
        provider_cfg = None
        try:
            provider_cfg = app_config.get_provider_config(run_job.provider)
        except KeyError:
            provider_cfg = None
        if provider_cfg is None and run_job.mode != "mock":
            # In real mode we need credentials/base_url to reach the upstream provider.
            run_job.status = "failed"
            run_job.error_message = f"provider config missing: {run_job.provider}"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        # Start run
        run_job.status = "running"
        run_job.started_at = datetime.now(UTC)

        # Load suite and set progress_total before starting
        suite = load_suite_from_version(suite_version.parsed_json)
        selected = set(run_job.config_snapshot.get("selected_tests") or [])
        tests = [t for t in suite.tests if not selected or t.name in selected]
        run_job.progress_total = len(tests)

        run_repo.update(run_job)
        db.commit()

        # Mark run as active in event bus and push start event
        event_bus.start_run(run_id)
        event_bus.push(
            run_id,
            "run_started",
            {
                "mode": run_job.mode,
                "progress_total": run_job.progress_total,
                "max_concurrent": max_concurrent,
            },
        )

        http_client = None
        try:
            # Create client
            if provider_cfg is None:
                # Mock mode can run without persisted provider configs.
                config = ProviderConfig(api_key="", base_url="", timeout=30.0)
            else:
                config = ProviderConfig(
                    api_key=provider_cfg.api_key,
                    base_url=provider_cfg.base_url,
                    timeout=provider_cfg.timeout,
                    api_family=provider_cfg.api_family,
                    headers=provider_cfg.headers,
                )
            logger = RequestLogger(
                LogConfig(
                    enabled=True,
                    level="INFO",
                    console=False,
                    file="./logs/llm-spec-web.log",
                )
            )
            http_client = HTTPClient(default_timeout=config.timeout)
            client = create_provider_client(
                run_job.provider, config, run_job.mode, logger, http_client
            )

            # Progress tracking (no locks needed in async)
            progress_done = 0
            progress_passed = 0
            progress_failed = 0
            cancelled = False

            # Collector list for test results
            test_results: list[dict[str, Any]] = []

            # Semaphore for controlling concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_single_test(test: Any, idx: int) -> dict[str, Any]:
                """Run a single test and return the result."""
                nonlocal progress_done, progress_passed, progress_failed, cancelled

                # Check for cancellation
                if cancelled:
                    return {"test": test, "status": "skipped", "idx": idx}

                async with semaphore:
                    if cancelled:
                        return {"test": test, "status": "skipped", "idx": idx}

                    # Create a collector for this test
                    local_collector = EndpointResultBuilder(
                        provider=suite.provider,
                        endpoint=suite.endpoint,
                        base_url=client.get_base_url(),
                    )
                    local_runner = ConfigDrivenTestRunner(
                        suite=suite, client=client, collector=local_collector, logger=None
                    )

                    # Push test start event
                    event_bus.push(run_id, "test_started", {"test_name": test.name, "index": idx})

                    try:
                        await local_runner.run_test_async(test)
                        test_record = local_collector.tests[-1]
                        status = str((test_record.get("result") or {}).get("status", "fail"))
                    except Exception as e:
                        status = "fail"
                        test_record = {
                            "test_name": test.name,
                            "result": {"status": "fail", "reason": str(e)},
                        }

                    # Update progress (no lock needed in async)
                    if cancelled:
                        return {"test": test, "status": "skipped", "idx": idx}
                    progress_done += 1
                    if status == "pass":
                        progress_passed += 1
                    else:
                        progress_failed += 1

                    # Store result
                    test_results.append(
                        {
                            "test": test,
                            "test_record": test_record,
                            "status": status,
                            "idx": idx,
                        }
                    )

                    # Push test finish event
                    event_bus.push(
                        run_id,
                        "test_finished",
                        {
                            "test_name": test.name,
                            "status": status,
                            "progress_done": progress_done,
                            "progress_total": len(tests),
                            "progress_passed": progress_passed,
                            "progress_failed": progress_failed,
                            "test_result": {
                                "test_name": test_record.get("test_name", test.name),
                                "parameter": test_record.get("parameter"),
                                "request": test_record.get("request"),
                                "result": test_record.get("result"),
                                "validation": test_record.get("validation"),
                            },
                        },
                    )

                    return {"test": test, "status": status, "idx": idx}

            # Create tasks for all tests
            tasks = [
                asyncio.create_task(run_single_test(test, idx))
                for idx, test in enumerate(tests, start=1)
            ]

            # Wait for all tasks to complete, checking for cancellation
            try:
                for coro in asyncio.as_completed(tasks):
                    try:
                        await coro
                        # Check for cancellation periodically
                        db.refresh(run_job)
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
                                "progress_total": len(tests),
                                "progress_passed": progress_passed,
                                "progress_failed": progress_failed,
                                "error": str(e),
                            },
                        )
            except asyncio.CancelledError:
                cancelled = True

            # Check if cancelled
            db.refresh(run_job)
            if run_job.status == "cancelled" or cancelled:
                event_bus.push(
                    run_id,
                    "run_cancelled",
                    {
                        "progress_done": progress_done,
                        "progress_total": len(tests),
                    },
                )
                run_repo.append_event(
                    run_id,
                    "run_cancelled",
                    {
                        "progress_done": progress_done,
                        "progress_total": len(tests),
                    },
                )
                db.commit()
                event_bus.end_run(run_id)
                return

            # Build final result from all test results
            final_collector = EndpointResultBuilder(
                provider=suite.provider,
                endpoint=suite.endpoint,
                base_url=client.get_base_url(),
            )

            # Sort results by idx and add to collector
            test_results.sort(key=lambda x: x["idx"])
            for result in test_results:
                test_record = result["test_record"]
                # Save test result to database
                run_test_row = RunTestResult(
                    run_id=run_id,
                    test_id=str(test_record.get("test_id", "")),
                    test_name=str(test_record.get("test_name", result["test"].name)),
                    parameter_name=str((test_record.get("parameter") or {}).get("name", "")),
                    parameter_value=(test_record.get("parameter") or {}).get("value"),
                    status=result["status"],
                    fail_stage=(test_record.get("result") or {}).get("fail_stage"),
                    reason_code=(test_record.get("result") or {}).get("reason_code"),
                    latency_ms=(test_record.get("request") or {}).get("latency_ms"),
                    raw_record=test_record,
                )
                run_repo.add_test_result(run_test_row)

                # Add to final collector for report
                final_collector.tests.append(test_record)

            # Update run job with final progress
            run_job.progress_done = progress_done
            run_job.progress_passed = progress_passed
            run_job.progress_failed = progress_failed

            # Build and save result
            report_data = final_collector.build_report_data()
            run_result = _build_run_result(
                run_id=run_id,
                started_at=run_job.started_at.isoformat() if run_job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                reports_by_provider={run_job.provider: [report_data]},
            )
            run_repo.save_result(
                RunResult(
                    run_id=run_id,
                    run_result_json=run_result,
                )
            )

            # Mark run as complete
            run_job.finished_at = datetime.now(UTC)
            run_job.status = "success" if run_job.progress_failed == 0 else "failed"
            run_repo.update(run_job)

            # Save terminal event to database for history
            run_repo.append_event(
                run_id,
                "run_finished",
                {
                    "status": run_job.status,
                    "passed": run_job.progress_passed,
                    "failed": run_job.progress_failed,
                },
            )
            db.commit()

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
            run_job.status = "failed"
            run_job.error_message = str(exc)
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)

            # Save terminal event to database
            run_repo.append_event(run_id, "run_failed", {"error": str(exc)})
            db.commit()

            # Push terminal event to memory
            event_bus.push(run_id, "run_failed", {"error": str(exc)})
            event_bus.end_run(run_id)
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                await http_client.close_async()
            # Cleanup event bus resources after a delay (allow client to receive terminal event)
            event_bus.cleanup(run_id)

    # ==================== Batch Operations ====================

    def create_batch(
        self,
        db: Session,
        suite_version_ids: list[str],
        mode: str | None = None,
        selected_tests_by_suite: dict[str, list[str]] | None = None,
        name: str | None = None,
    ) -> tuple[RunBatch, list[RunJob]]:
        """Create a new batch with multiple runs.

        Args:
            db: Database session.
            suite_version_ids: List of suite version IDs to run.
            mode: Execution mode ("real" or "mock").
            selected_tests_by_suite: Map of suite_id to list of test names.
            name: User-defined name for the batch.

        Returns:
            Tuple of (RunBatch instance, list of RunJob instances).

        Raises:
            NotFoundError: If any suite version not found.
        """
        run_repo = RunRepository(db)
        suite_service = SuiteService()

        # Resolve mode
        resolved_mode = mode or ("mock" if settings.mock_mode else "real")

        # Create batch
        batch = RunBatch(
            name=name or "Task",
            status="running",
            mode=resolved_mode,
            total_runs=len(suite_version_ids),
            started_at=datetime.now(UTC),
        )
        run_repo.create_batch(batch)
        db.flush()

        # Create runs for each suite version
        runs: list[RunJob] = []
        for suite_version_id in suite_version_ids:
            suite_version = suite_service.resolve_suite_by_version_id(suite_version_id)

            provider = str(suite_version.parsed_json.get("provider"))
            endpoint = str(suite_version.parsed_json.get("endpoint"))

            # Get selected tests for this suite
            suite_id = suite_version.suite_id
            selected_tests = None
            if selected_tests_by_suite and suite_id in selected_tests_by_suite:
                selected_tests = selected_tests_by_suite[suite_id]

            # Create run job
            run = RunJob(
                status="queued",
                mode=resolved_mode,
                provider=provider,
                endpoint=endpoint,
                batch_id=batch.id,
                suite_version_id=suite_version.id,
                config_snapshot={"selected_tests": selected_tests or []},
            )
            run_repo.create(run)
            runs.append(run)

        db.commit()
        db.refresh(batch)
        for run in runs:
            db.refresh(run)
        return batch, runs

    def get_batch(self, db: Session, batch_id: str) -> RunBatch:
        """Get a batch by ID.

        Args:
            db: Database session.
            batch_id: Batch ID.

        Returns:
            RunBatch instance.

        Raises:
            NotFoundError: If batch not found.
        """
        run_repo = RunRepository(db)
        batch = run_repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError("RunBatch", batch_id)
        return batch

    def get_batch_with_runs(self, db: Session, batch_id: str) -> tuple[RunBatch, Sequence[RunJob]]:
        """Get a batch with its runs.

        Args:
            db: Database session.
            batch_id: Batch ID.

        Returns:
            Tuple of (RunBatch instance, list of RunJob instances).

        Raises:
            NotFoundError: If batch not found.
        """
        run_repo = RunRepository(db)
        batch = run_repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError("RunBatch", batch_id)
        runs = run_repo.list_runs_by_batch(batch_id)
        return batch, runs

    def list_batches(
        self,
        db: Session,
        status_filter: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[RunBatch], int]:
        """List batches with pagination.

        Args:
            db: Database session.
            status_filter: Filter by status.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            Tuple of (list of RunBatch instances, total count).
        """
        run_repo = RunRepository(db)
        return run_repo.list_batches(status_filter=status_filter, limit=limit, offset=offset)

    def update_batch(self, db: Session, batch_id: str, name: str) -> RunBatch:
        """Update a batch's name.

        Args:
            db: Database session.
            batch_id: Batch ID.
            name: New name for the batch.

        Returns:
            Updated RunBatch instance.

        Raises:
            NotFoundError: If batch not found.
        """
        run_repo = RunRepository(db)
        batch = run_repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError("RunBatch", batch_id)
        batch.name = name
        run_repo.update_batch(batch)
        db.commit()
        db.refresh(batch)
        return batch

    def delete_batch(self, db: Session, batch_id: str) -> bool:
        """Delete a batch and all its runs.

        Args:
            db: Database session.
            batch_id: Batch ID.

        Returns:
            True if deleted, False if not found.
        """
        run_repo = RunRepository(db)
        result = run_repo.delete_batch(batch_id)
        if result:
            db.commit()
        return result

    def update_batch_status(self, db: Session, batch_id: str) -> RunBatch:
        """Update batch status based on its runs.

        Args:
            db: Database session.
            batch_id: Batch ID.

        Returns:
            Updated RunBatch instance.
        """
        run_repo = RunRepository(db)
        batch = run_repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError("RunBatch", batch_id)

        runs = run_repo.list_runs_by_batch(batch_id)

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

        batch.completed_runs = completed
        batch.passed_runs = passed
        batch.failed_runs = failed

        # Check if all runs are done
        if completed >= batch.total_runs:
            batch.status = "completed"
            batch.finished_at = datetime.now(UTC)

        run_repo.update_batch(batch)
        db.commit()
        db.refresh(batch)
        return batch
