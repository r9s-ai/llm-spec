from unittest.mock import MagicMock

from llm_spec.runners.runner import ConfigDrivenTestRunner, SpecTestCase, SpecTestSuite


def test_runner_required_fields_validation():
    # Setup
    suite = SpecTestSuite(
        provider="openai",
        endpoint="/v1/chat/completions",
        required_fields=["id", "choices[0].message.content"],
    )
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

    runner = ConfigDrivenTestRunner(suite, client)

    test_case = SpecTestCase(
        name="test_missing_required",
        params={"model": "gpt-4"},
        focus_param={"name": "model", "value": "gpt-4"},
    )

    # Run test
    case_result = runner.run_test(test_case)
    result = case_result.get("result")
    result_dict = result if isinstance(result, dict) else {}

    # Verify
    assert result_dict.get("status") == "fail"
    assert "Missing required field: choices[0].message.content" in (
        str(result_dict.get("reason") or "")
    )


def test_runner_test_level_required_fields():
    # Setup
    suite = SpecTestSuite(
        provider="openai", endpoint="/v1/chat/completions", required_fields=["id"]
    )
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

    runner = ConfigDrivenTestRunner(suite, client)

    test_case = SpecTestCase(
        name="test_extra_required",
        params={"model": "gpt-4"},
        focus_param={"name": "model", "value": "gpt-4"},
        required_fields=[
            "choices[0].message.reasoning_content"
        ],  # This is missing in mock response
    )

    # Run test
    case_result = runner.run_test(test_case)
    result = case_result.get("result")
    result_dict = result if isinstance(result, dict) else {}

    # Verify
    assert result_dict.get("status") == "fail"
    assert "Missing required field: choices[0].message.reasoning_content" in (
        str(result_dict.get("reason") or "")
    )
