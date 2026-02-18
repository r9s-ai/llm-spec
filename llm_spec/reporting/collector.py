"""Report collector for accumulating test results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from llm_spec.reporting.report_types import (
    ReportData,
    TestExecutionResult,
    TestRecord,
    TestRequestRecord,
    TestTimestampsRecord,
)


class EndpointResultBuilder:
    """Per-endpoint report collector."""

    def __init__(self, provider: str, endpoint: str, base_url: str):
        """Initialize the report collector.

        Args:
            provider: provider name
            endpoint: API endpoint path
            base_url: base URL
        """
        self.provider = provider
        self.endpoint = endpoint
        self.base_url = base_url
        self.test_time = datetime.now().isoformat()

        # Test summary
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

        # Response field tracking
        self.expected_fields: set[str] = set()
        self.unsupported_fields: list[dict[str, Any]] = []  # TODO: add typed schema later

        # Error tracking
        self.errors: list[dict[str, Any]] = []  # TODO: add typed schema later

        self.tests: list[TestRecord] = []

    def record_result(self, result: TestExecutionResult) -> None:
        """Record one normalized test execution result."""
        tested_param_input = result.get("tested_param")
        tested_param: tuple[str, Any] | None = None
        if tested_param_input:
            param_name = tested_param_input.get("name")
            if isinstance(param_name, str) and param_name:
                tested_param = (param_name, tested_param_input.get("value"))

        test_name = str(result.get("test_name", "unknown"))
        status_code = int(result.get("status_code", 0))
        response_body = result.get("response_body")
        error = result.get("error")
        missing_fields = result.get("missing_fields")
        expected_fields = result.get("expected_fields")
        request_ok_input = result.get("request_ok")
        schema_ok_input = result.get("schema_ok")
        required_fields_ok_input = result.get("required_fields_ok")
        stream_rules_ok_input = result.get("stream_rules_ok")
        missing_events = result.get("missing_events") or []
        started_at = result.get("started_at")
        finished_at = result.get("finished_at")
        latency_ms = result.get("latency_ms")

        self.total_tests += 1

        # Record expected fields
        if expected_fields:
            for field in expected_fields:
                self.expected_fields.add(field)

        # Determine success
        http_success = 200 <= status_code < 300
        request_ok = bool(request_ok_input) if request_ok_input is not None else http_success
        schema_ok = bool(schema_ok_input) if schema_ok_input is not None else (error is None)
        required_fields_ok = (
            bool(required_fields_ok_input)
            if required_fields_ok_input is not None
            else not bool(missing_fields)
        )
        stream_rules_ok = bool(stream_rules_ok_input) if stream_rules_ok_input is not None else True
        validation_ok = schema_ok and required_fields_ok and stream_rules_ok
        is_success = request_ok and validation_ok

        if is_success:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

            # Record errors
            if error or status_code >= 400:
                if 400 <= status_code < 500:
                    error_type = "http_error"
                elif 500 <= status_code < 600:
                    error_type = "server_error"
                else:
                    error_type = "validation_error"

                self.errors.append(
                    {
                        "test_name": test_name,
                        "type": error_type,
                        "status_code": status_code,
                        "error": error,
                        "response_body": response_body,
                    }
                )

        # Record missing fields
        if missing_fields:
            for field in missing_fields:
                self.unsupported_fields.append(
                    {
                        "field": field,
                        "test_name": test_name,
                        "reason": "Field missing in response",
                    }
                )

        # Build stable endpoint-level test record for run_result/report consumption
        param_name = tested_param[0] if tested_param else "__baseline__"
        param_value = tested_param[1] if tested_param else None

        fail_stage: str | None = None
        reason_code: str | None = None
        if not request_ok:
            fail_stage = "request"
            reason_code = f"HTTP_{status_code}" if status_code else "REQUEST_ERROR"
        elif not schema_ok:
            fail_stage = "schema"
            reason_code = "SCHEMA_INVALID"
        elif not required_fields_ok:
            fail_stage = "required_fields"
            reason_code = "REQUIRED_FIELDS_MISSING"
        elif not stream_rules_ok:
            fail_stage = "stream_rules"
            reason_code = "STREAM_RULES_FAILED"

        request_record: TestRequestRecord = {
            "ok": request_ok,
            "http_status": status_code,
        }
        if isinstance(latency_ms, int):
            request_record["latency_ms"] = int(latency_ms)

        timestamps_record: TestTimestampsRecord = {}
        if started_at:
            timestamps_record["started_at"] = str(started_at)
        if finished_at:
            timestamps_record["finished_at"] = str(finished_at)

        self.tests.append(
            TestRecord(
                test_id=f"{self.provider}/{self.endpoint.lstrip('/')}::{test_name}",
                test_name=test_name,
                parameter={
                    "name": param_name,
                    "value": param_value,
                    "value_type": type(param_value).__name__ if param_value is not None else "none",
                },
                request=request_record,
                validation={
                    "schema_ok": schema_ok,
                    "required_fields_ok": required_fields_ok,
                    "stream_rules_ok": stream_rules_ok,
                    "missing_fields": list(missing_fields or []),
                    "missing_events": list(missing_events),
                },
                result={
                    "status": "pass" if is_success else "fail",
                    "fail_stage": fail_stage,
                    "reason_code": reason_code,
                    "reason": error,
                },
                timestamps=timestamps_record,
            )
        )

    def build_report_data(self) -> ReportData:
        """Build endpoint report payload in-memory."""
        return {
            "test_time": self.test_time,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "base_url": self.base_url,
            "test_summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
            },
            "response_fields": {
                "expected": sorted(self.expected_fields),
                "unsupported": self.unsupported_fields,
            },
            "errors": self.errors,
            "tests": self.tests,
        }

    def to_report_data(self) -> ReportData:
        """Backward-compatible alias for ``build_report_data``."""
        return self.build_report_data()
