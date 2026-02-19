"""Service layer for suite/version CRUD and run execution."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import json5
from sqlalchemy import func, select
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
from llm_spec.web.mock_adapter import MockProviderAdapter
from llm_spec.web.models import (
    ProviderConfigModel,
    RunEvent,
    RunJob,
    RunResult,
    RunTestResult,
    Suite,
    SuiteVersion,
)


def parse_suite_json5(raw_json5: str) -> dict[str, Any]:
    """Parse JSON5 content and perform minimum shape checks."""
    parsed = json5.loads(raw_json5)
    if not isinstance(parsed, dict):
        raise ValueError("Suite JSON5 must be an object")
    if "provider" not in parsed:
        raise ValueError("Suite JSON5 missing required field: provider")
    if "endpoint" not in parsed:
        raise ValueError("Suite JSON5 missing required field: endpoint")
    if not isinstance(parsed.get("tests"), list):
        raise ValueError("Suite JSON5 missing required field: tests(list)")
    return parsed


def validate_suite_by_runner(raw_json5: str) -> None:
    """Validate suite using existing loader, preserving current behavior."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json5", encoding="utf-8", delete=False) as f:
            f.write(raw_json5)
            tmp_path = Path(f.name)
        load_test_suite(tmp_path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def create_suite_with_initial_version(
    db: Session,
    *,
    provider: str,
    endpoint: str,
    name: str,
    raw_json5: str,
    created_by: str,
) -> Suite:
    """Create a suite and version=1 snapshot."""
    parsed = parse_suite_json5(raw_json5)
    validate_suite_by_runner(raw_json5)

    existing = db.execute(
        select(Suite).where(Suite.provider == provider, Suite.endpoint == endpoint)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"Suite already exists for {provider} {endpoint}")

    suite = Suite(
        provider=provider,
        endpoint=endpoint,
        name=name,
        latest_version=1,
    )
    db.add(suite)
    db.flush()

    suite_version = SuiteVersion(
        suite_id=suite.id,
        version=1,
        raw_json5=raw_json5,
        parsed_json=parsed,
        created_by=created_by,
    )
    db.add(suite_version)
    db.commit()
    db.refresh(suite)
    return suite


def create_suite_version(
    db: Session, *, suite: Suite, raw_json5: str, created_by: str
) -> SuiteVersion:
    """Create a new version snapshot for an existing suite."""
    parsed = parse_suite_json5(raw_json5)
    validate_suite_by_runner(raw_json5)
    next_version = suite.latest_version + 1

    suite_version = SuiteVersion(
        suite_id=suite.id,
        version=next_version,
        raw_json5=raw_json5,
        parsed_json=parsed,
        created_by=created_by,
    )
    suite.latest_version = next_version
    db.add(suite_version)
    db.add(suite)
    db.commit()
    db.refresh(suite_version)
    return suite_version


def _get_run_next_seq(db: Session, run_id: str) -> int:
    stmt = select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)
    max_seq = db.execute(stmt).scalar_one()
    return int(max_seq or 0) + 1


def _append_event(db: Session, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    seq = _get_run_next_seq(db, run_id)
    db.add(RunEvent(run_id=run_id, seq=seq, event_type=event_type, payload=payload))


def _make_provider_config(row: ProviderConfigModel) -> ProviderConfig:
    return ProviderConfig(api_key=row.api_key, base_url=row.base_url, timeout=row.timeout)


def _make_client(provider: str, row: ProviderConfigModel, mode: str):
    config = _make_provider_config(row)
    if mode == "mock":
        return MockProviderAdapter(
            config=config, base_dir=settings.mock_base_dir, provider_name=provider
        )

    logger = RequestLogger(
        LogConfig(enabled=True, level="INFO", console=False, file="./logs/llm-spec-web.log")
    )
    http_client = HTTPClient(default_timeout=config.timeout)
    if provider == "openai":
        return OpenAIAdapter(config, http_client, logger)
    if provider == "anthropic":
        return AnthropicAdapter(config, http_client, logger)
    if provider == "gemini":
        return GeminiAdapter(config, http_client, logger)
    if provider == "xai":
        return XAIAdapter(config, http_client, logger)
    raise ValueError(f"Unsupported provider: {provider}")


def _load_suite_from_version(version: SuiteVersion):
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json5", encoding="utf-8", delete=False) as f:
            f.write(version.raw_json5)
            tmp_path = Path(f.name)
        return load_test_suite(tmp_path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def execute_run_job(db: Session, run_id: str) -> None:
    """Execute one queued run and persist progress/results."""
    run_job = db.get(RunJob, run_id)
    if run_job is None:
        return

    suite_version = db.get(SuiteVersion, run_job.suite_version_id)
    if suite_version is None:
        run_job.status = "failed"
        run_job.error_message = f"suite_version not found: {run_job.suite_version_id}"
        run_job.finished_at = datetime.now(UTC)
        db.add(run_job)
        db.commit()
        return

    provider_config = db.get(ProviderConfigModel, run_job.provider)
    if provider_config is None:
        run_job.status = "failed"
        run_job.error_message = f"provider config missing: {run_job.provider}"
        run_job.finished_at = datetime.now(UTC)
        db.add(run_job)
        db.commit()
        return

    run_job.status = "running"
    run_job.started_at = datetime.now(UTC)
    db.add(run_job)
    _append_event(db, run_id, "run_started", {"mode": run_job.mode})
    db.commit()

    client = None
    try:
        suite = _load_suite_from_version(suite_version)
        selected = set(run_job.config_snapshot.get("selected_tests") or [])
        tests = [t for t in suite.tests if not selected or t.name in selected]
        run_job.progress_total = len(tests)
        db.add(run_job)
        db.commit()

        client = _make_client(run_job.provider, provider_config, run_job.mode)
        collector = EndpointResultBuilder(
            provider=suite.provider,
            endpoint=suite.endpoint,
            base_url=client.get_base_url(),
        )
        runner = ConfigDrivenTestRunner(
            suite=suite, client=client, collector=collector, logger=None
        )

        for idx, test in enumerate(tests, start=1):
            db.refresh(run_job)
            if run_job.status == "cancelled":
                _append_event(
                    db,
                    run_id,
                    "run_cancelled",
                    {
                        "progress_done": run_job.progress_done,
                        "progress_total": run_job.progress_total,
                    },
                )
                db.commit()
                return

            _append_event(db, run_id, "test_started", {"test_name": test.name, "index": idx})
            db.commit()

            runner.run_test(test)
            test_record = collector.tests[-1]
            status = str((test_record.get("result") or {}).get("status", "fail"))
            run_job.progress_done += 1
            if status == "pass":
                run_job.progress_passed += 1
            else:
                run_job.progress_failed += 1

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
            db.add(run_test_row)
            db.add(run_job)
            _append_event(
                db,
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

        report_data = collector.build_report_data()
        run_result = _build_run_result(
            run_id=run_id,
            started_at=run_job.started_at.isoformat() if run_job.started_at else "",
            finished_at=datetime.now(UTC).isoformat(),
            reports_by_provider={run_job.provider: [report_data]},
        )
        formatter = RunResultFormatter(run_result)
        db.merge(
            RunResult(
                run_id=run_id,
                run_result_json=run_result,
                report_md=formatter.generate_markdown(),
                report_html=formatter.generate_html(),
            )
        )

        run_job.finished_at = datetime.now(UTC)
        run_job.status = "success" if run_job.progress_failed == 0 else "failed"
        db.add(run_job)
        _append_event(
            db,
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
        db.add(run_job)
        _append_event(db, run_id, "run_failed", {"error": str(exc)})
        db.commit()
    finally:
        http_client = getattr(client, "http_client", None)
        if isinstance(http_client, HTTPClient):
            http_client.close()
