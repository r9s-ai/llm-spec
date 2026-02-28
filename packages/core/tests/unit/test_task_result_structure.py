from llm_spec.results.task_result import build_task_result


def test_build_task_result_contains_selection_and_cases() -> None:
    task_result = build_task_result(
        run_id="run_123",
        started_at="2026-02-18T12:00:00Z",
        finished_at="2026-02-18T12:00:10Z",
        provider="openai",
        model="gpt-5.2",
        route="responses",
        endpoint="/v1/responses",
        cases=[
            {
                "version": "case_result.v1",
                "test_id": "openai/v1/responses::baseline",
                "test_name": "baseline",
                "provider": "openai",
                "model": "gpt-5.2",
                "endpoint": "/v1/responses",
                "parameter": {"name": "temperature", "value": 0.7, "value_type": "float"},
                "request": {"http_status": 200, "latency_ms": 100},
                "result": {"status": "pass"},
                "validation": {
                    "schema_ok": True,
                    "required_fields_ok": True,
                    "stream_rules_ok": True,
                    "missing_fields": [],
                    "missing_events": [],
                },
            }
        ],
    )

    assert task_result["version"] == "task_result.v1"
    assert task_result["run_id"] == "run_123"
    assert task_result["selection"]["provider"] == "openai"
    assert task_result["selection"]["model"] == "gpt-5.2"
    assert task_result["selection"]["route"] == "responses"
    assert task_result["selection"]["endpoint"] == "/v1/responses"
    assert isinstance(task_result["cases"], list)
    assert task_result["cases"][0]["test_name"] == "baseline"
