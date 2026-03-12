from __future__ import annotations

from pathlib import Path

from llm_spec.suites.registry import build_executable_cases, load_SuiteSpecs


def test_build_execution_plan_merges_and_overrides() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_SuiteSpecs(repo_root / "suites-registry" / "providers")

    suite = next(
        s
        for s in suites
        if s.provider_id == "openai"
        and s.route_id == "chat_completions"
        and s.model_id == "gpt-4o-mini"
    )
    cases = build_executable_cases(suite)

    assert cases
    baseline_case = next(c for c in cases if c.is_baseline is True)
    assert baseline_case.case_id.endswith(":baseline")
    assert baseline_case.request.endpoint == suite.endpoint
    assert baseline_case.request.method == suite.method
    assert baseline_case.checks.response_schema == suite.schemas.response
    assert baseline_case.checks.stream_chunk_schema == suite.schemas.stream_chunk
    assert baseline_case.request.params["model"] == "gpt-4o-mini"
    assert "messages" in baseline_case.request.params

    stream_case = next(c for c in cases if c.test_name == "stream")
    assert stream_case.request.stream is True
    assert stream_case.request.params["stream"] is True
    assert stream_case.request.params["model"] == "gpt-4o-mini"
    assert "messages" in stream_case.request.params
    assert stream_case.checks.stream_rules == suite.stream_rules

    logprobs_case = next(c for c in cases if c.test_name == "logprobs")
    assert logprobs_case.checks.required_fields == ["choices[0].logprobs"]
