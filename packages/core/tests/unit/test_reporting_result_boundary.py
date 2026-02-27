from llm_spec.reporting.collector import EndpointResultBuilder


def test_collector_accepts_normalized_test_result_dict() -> None:
    collector = EndpointResultBuilder(
        provider="openai",
        endpoint="/v1/chat/completions",
        base_url="https://api.openai.com",
    )

    collector.record_result(
        {
            "test_name": "test_param_temperature",
            "params": {"model": "gpt-4.1", "temperature": 9.9},
            "status_code": 400,
            "response_body": {"error": {"message": "temperature is out of range"}},
            "error": "HTTP 400",
            "tested_param": 9.9,
            "is_baseline": False,
        }
    )

    assert collector.total_tests == 1
    assert collector.failed_tests == 1
    report = collector.build_report_data()
    tests = report.get("tests")
    assert tests is not None
    parameter = tests[0].get("parameter")
    assert parameter is not None
    assert parameter["value"] == 9.9
    result = tests[0].get("result")
    assert result is not None
    status = result.get("status")
    assert status == "fail"
    reason = result.get("reason")
    assert "HTTP 400" in str(reason)
