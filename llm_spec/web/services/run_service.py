"""Run service for business logic."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.cli import _build_run_result
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import LogConfig, ProviderConfig
from llm_spec.logger import RequestLogger
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.run_result_formatter import RunResultFormatter
from llm_spec.runners import ConfigDrivenTestRunner, load_test_suite
from llm_spec.web.config import settings
from llm_spec.web.core.exceptions import NotFoundError
from llm_spec.web.models.run import RunEvent, RunJob, RunResult, RunTestResult
from llm_spec.web.models.suite import SuiteVersion
from llm_spec.web.repositories.run_repo import RunRepository
from llm_spec.web.repositories.suite_repo import SuiteRepository

# Provider adapter registry
PROVIDER_ADAPTERS: dict[str, type] = {
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
        from llm_spec.web.adapters.mock_adapter import MockProviderAdapter

        return MockProviderAdapter(
            config=config,
            base_dir=settings.mock_base_dir,
            provider_name=provider,
        )

    adapter_class = PROVIDER_ADAPTERS.get(provider)
    if adapter_class is None:
        raise ValueError(f"Unsupported provider: {provider}")

    return adapter_class(config, http_client, logger)


def load_suite_from_version(version: SuiteVersion):
    """Load test suite from a SuiteVersion.

    Args:
        version: SuiteVersion instance.

    Returns:
        Loaded test suite.
    """
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json5", encoding="utf-8", delete=False) as f:
            f.write(version.raw_json5)
            tmp_path = Path(f.name)
        return load_test_suite(tmp_path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


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
        suite_repo = SuiteRepository(db)
        run_repo = RunRepository(db)

        # Get suite version
        suite_version = suite_repo.get_version_by_id(suite_version_id)
        if suite_version is None:
            raise NotFoundError("SuiteVersion", suite_version_id)

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
            suite_version_id=suite_version.id,
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

    def execute_run(self, db: Session, run_id: str) -> None:
        """Execute a queued run job.

        This method is designed to be called in a background task.

        Args:
            db: Database session.
            run_id: Run job ID.
        """
        suite_repo = SuiteRepository(db)
        run_repo = RunRepository(db)

        run_job = run_repo.get_by_id(run_id)
        if run_job is None:
            return

        # Get suite version
        if run_job.suite_version_id is None:
            run_job.status = "failed"
            run_job.error_message = "suite_version_id is None"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        suite_version = suite_repo.get_version_by_id(run_job.suite_version_id)
        if suite_version is None:
            run_job.status = "failed"
            run_job.error_message = f"suite_version not found: {run_job.suite_version_id}"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        # Get provider config
        from llm_spec.web.repositories.provider_repo import ProviderRepository

        provider_repo = ProviderRepository(db)
        provider_config = provider_repo.get_by_provider(run_job.provider)
        if provider_config is None:
            run_job.status = "failed"
            run_job.error_message = f"provider config missing: {run_job.provider}"
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            db.commit()
            return

        # Start run
        run_job.status = "running"
        run_job.started_at = datetime.now(UTC)
        run_repo.update(run_job)
        run_repo.append_event(run_id, "run_started", {"mode": run_job.mode})
        db.commit()

        client = None
        http_client = None
        try:
            # Load suite
            suite = load_suite_from_version(suite_version)
            selected = set(run_job.config_snapshot.get("selected_tests") or [])
            tests = [t for t in suite.tests if not selected or t.name in selected]
            run_job.progress_total = len(tests)
            run_repo.update(run_job)
            db.commit()

            # Create client
            config = ProviderConfig(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                timeout=provider_config.timeout,
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

            # Create collector and runner
            collector = EndpointResultBuilder(
                provider=suite.provider,
                endpoint=suite.endpoint,
                base_url=client.get_base_url(),
            )
            runner = ConfigDrivenTestRunner(
                suite=suite, client=client, collector=collector, logger=None
            )

            # Run tests
            for idx, test in enumerate(tests, start=1):
                db.refresh(run_job)
                if run_job.status == "cancelled":
                    run_repo.append_event(
                        run_id,
                        "run_cancelled",
                        {
                            "progress_done": run_job.progress_done,
                            "progress_total": run_job.progress_total,
                        },
                    )
                    db.commit()
                    return

                run_repo.append_event(
                    run_id, "test_started", {"test_name": test.name, "index": idx}
                )
                db.commit()

                runner.run_test(test)
                test_record = collector.tests[-1]
                status = str((test_record.get("result") or {}).get("status", "fail"))
                run_job.progress_done += 1
                if status == "pass":
                    run_job.progress_passed += 1
                else:
                    run_job.progress_failed += 1

                # Save test result
                run_test_row = RunTestResult(
                    run_id=run_id,
                    test_id=str(test_record.get("test_id", "")),
                    test_name=str(test_record.get("test_name", test.name)),
                    parameter_name=str((test_record.get("parameter") or {}).get("name", "")),
                    parameter_value=(test_record.get("parameter") or {}).get("value"),
                    status=status,
                    fail_stage=(test_record.get("result") or {}).get("fail_stage"),
                    reason_code=(test_record.get("result") or {}).get("reason_code"),
                    latency_ms=(test_record.get("request") or {}).get("latency_ms"),
                    raw_record=test_record,
                )
                run_repo.add_test_result(run_test_row)
                run_repo.update(run_job)
                run_repo.append_event(
                    run_id,
                    "test_finished",
                    {
                        "test_name": test.name,
                        "status": status,
                        "progress_done": run_job.progress_done,
                        "progress_total": run_job.progress_total,
                    },
                )
                db.commit()

            # Build and save result
            report_data = collector.build_report_data()
            run_result = _build_run_result(
                run_id=run_id,
                started_at=run_job.started_at.isoformat() if run_job.started_at else "",
                finished_at=datetime.now(UTC).isoformat(),
                reports_by_provider={run_job.provider: [report_data]},
            )
            formatter = RunResultFormatter(run_result)
            run_repo.save_result(
                RunResult(
                    run_id=run_id,
                    run_result_json=run_result,
                    report_md=formatter.generate_markdown(),
                    report_html=formatter.generate_html(),
                )
            )

            # Mark run as complete
            run_job.finished_at = datetime.now(UTC)
            run_job.status = "success" if run_job.progress_failed == 0 else "failed"
            run_repo.update(run_job)
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

        except Exception as exc:
            run_job.status = "failed"
            run_job.error_message = str(exc)
            run_job.finished_at = datetime.now(UTC)
            run_repo.update(run_job)
            run_repo.append_event(run_id, "run_failed", {"error": str(exc)})
            db.commit()
        finally:
            if http_client is not None and isinstance(http_client, HTTPClient):
                http_client.close()
