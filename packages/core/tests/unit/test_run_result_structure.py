from llm_spec.cli import _build_run_result
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.report_types import ReportData


def test_collector_report_contains_endpoint_tests_array() -> None:
    collector = EndpointResultBuilder(
        provider="openai",
        endpoint="/v1/chat/completions",
        base_url="https://api.openai.com",
    )
    collector.record_result(
        {
            "test_name": "test_param_temperature[0.7]",
            "params": {"model": "gpt-4.1", "temperature": 0.7},
            "status_code": 200,
            "response_body": {"id": "ok"},
            "error": None,
            "tested_param": 0.7,
            "request_ok": True,
            "schema_ok": True,
            "required_fields_ok": True,
            "stream_rules_ok": True,
            "started_at": "2026-02-18T10:00:00Z",
            "finished_at": "2026-02-18T10:00:01Z",
            "latency_ms": 1000,
            "is_baseline": False,
        }
    )

    report = collector.build_report_data()
    tests = report.get("tests", [])

    assert len(tests) == 1
    test_record = tests[0]
    parameter = test_record.get("parameter")
    assert parameter is not None
    assert parameter["value"] == 0.7
    result = test_record.get("result")
    assert result is not None
    status = result.get("status")
    assert status == "pass"
    request = test_record.get("request")
    assert request is not None
    http_status = request.get("http_status")
    assert http_status == 200


def test_build_run_result_with_provider_endpoint_tests_structure() -> None:
    report_data: ReportData = {
        "provider": "openai",
        "endpoint": "/v1/chat/completions",
        "base_url": "https://api.openai.com",
        "test_summary": {"total_tests": 2, "passed": 1, "failed": 1},
        "tests": [
            {
                "test_id": "openai/v1/chat/completions::test_param_temperature[0.7]",
                "test_name": "test_param_temperature[0.7]",
                "parameter": {"value": 0.7, "value_type": "float"},
                "request": {"ok": True, "http_status": 200},
                "validation": {
                    "schema_ok": True,
                    "required_fields_ok": True,
                    "stream_rules_ok": True,
                    "missing_fields": [],
                    "missing_events": [],
                },
                "result": {
                    "status": "pass",
                    "fail_stage": None,
                    "reason_code": None,
                    "reason": None,
                },
                "timestamps": {
                    "started_at": "2026-02-18T10:00:00Z",
                    "finished_at": "2026-02-18T10:00:01Z",
                },
            }
        ],
    }
    run_result = _build_run_result(
        run_id="20260218_120000",
        started_at="2026-02-18T12:00:00Z",
        finished_at="2026-02-18T12:00:10Z",
        reports_by_provider={"openai": [report_data]},
    )

    assert run_result["providers"][0]["provider"] == "openai"
    endpoint = run_result["providers"][0]["endpoints"][0]
    assert endpoint["endpoint"] == "/v1/chat/completions"
    assert isinstance(endpoint["tests"], list)
    first_test = endpoint["tests"][0]
    parameter = first_test.get("parameter")
    assert parameter is not None
    assert parameter["value"] == 0.7
