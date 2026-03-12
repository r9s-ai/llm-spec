from unittest.mock import MagicMock

from llm_spec.runners.runner import TestRunner
from llm_spec.suites.types import ExecutableCase, FocusParam, HttpRequest, ValidationSpec


def test_runner_required_fields_validation():
    client = MagicMock()

    # Mock response
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.json.return_value = {
        "id": "123",
        "object": "chat.completion",
        "created": 12345,
        "model": "gpt-4",
        "choices": [{"index": 0, "message": {"role": "assistant"}}],  # Missing 'content'
    }
    client.request.return_value = response_mock

    runner = TestRunner(client)

    case = ExecutableCase(
        case_id="test_missing_required",
        test_name="test_missing_required",
        focus=FocusParam(name="model", value="gpt-4"),
        request=HttpRequest(
            method="POST",
            endpoint="/v1/chat/completions",
            params={"model": "gpt-4"},
        ),
        checks=ValidationSpec(
            required_fields=["id", "choices[0].message.content"],
        ),
        provider="openai",
    )

    verdict = runner.run(case)

    assert verdict.status == "fail"
    assert verdict.failure is not None
    assert "choices[0].message.content" in (verdict.failure.message or "")


def test_runner_test_level_required_fields():
    client = MagicMock()

    # Mock response
    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.json.return_value = {
        "id": "123",
        "object": "chat.completion",
        "created": 12345,
        "model": "gpt-4",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
    }
    client.request.return_value = response_mock

    runner = TestRunner(client)

    case = ExecutableCase(
        case_id="test_extra_required",
        test_name="test_extra_required",
        focus=FocusParam(name="model", value="gpt-4"),
        request=HttpRequest(
            method="POST",
            endpoint="/v1/chat/completions",
            params={"model": "gpt-4"},
        ),
        checks=ValidationSpec(
            required_fields=["id", "choices[0].message.reasoning_content"],
        ),
        provider="openai",
    )

    verdict = runner.run(case)

    assert verdict.status == "fail"
    assert verdict.failure is not None
    assert "choices[0].message.reasoning_content" in (verdict.failure.message or "")
