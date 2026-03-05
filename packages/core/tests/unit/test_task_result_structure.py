from llm_spec.results.result_types import TestVerdict
from llm_spec.results.task_result import build_run_result
from llm_spec.suites.types import FocusParam


def test_build_run_result_contains_verdicts() -> None:
    verdict = TestVerdict(
        case_id="openai:gpt-5.2:responses:baseline",
        test_name="baseline",
        focus=FocusParam(name="temperature", value=0.7),
        status="pass",
        started_at="2026-02-18T12:00:00Z",
        finished_at="2026-02-18T12:00:01Z",
        latency_ms=100,
        http_status=200,
        schema_ok=True,
        required_fields_ok=True,
        stream_rules_ok=True,
    )

    result = build_run_result(
        run_id="run_123",
        started_at="2026-02-18T12:00:00Z",
        finished_at="2026-02-18T12:00:10Z",
        provider="openai",
        model="gpt-5.2",
        route="responses",
        endpoint="/v1/responses",
        suite_name="openai/gpt-5.2/responses",
        verdicts=[verdict],
    )

    assert result.version == "run_result.v1"
    assert result.run_id == "run_123"
    assert result.provider == "openai"
    assert result.model == "gpt-5.2"
    assert result.route == "responses"
    assert result.endpoint == "/v1/responses"
    assert result.total == 1
    assert result.passed == 1
    assert result.failed == 0
    assert result.verdicts[0].test_name == "baseline"
    assert result.verdicts[0].status == "pass"
