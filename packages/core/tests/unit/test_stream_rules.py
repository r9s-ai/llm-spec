from llm_spec.runners.stream_rules import extract_observations, validate_stream


def test_anthropic_defaults_missing_stop_events() -> None:
    parsed_chunks = [
        {"type": "message_start"},
        {"type": "content_block_start"},
        {"type": "content_block_delta"},
        {"type": "message_delta"},
        # missing content_block_stop, message_stop
    ]

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=None,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=None,
    )

    assert "content_block_stop" in missing
    assert "terminal:message_stop" in missing


def test_openai_responses_defaults_require_completed() -> None:
    parsed_chunks = [
        {"type": "response.created"},
        {"type": "response.in_progress"},
    ]

    observations = extract_observations(
        provider="openai",
        endpoint="/v1/responses",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=None,
    )

    missing = validate_stream(
        provider="openai",
        endpoint="/v1/responses",
        observations=observations,
        stream_rules=None,
    )

    assert "response.completed" in missing
    assert "[DONE]" in missing
    assert "terminal:[DONE]" in missing


def test_openai_chat_completions_defaults_require_done() -> None:
    parsed_chunks = [
        {
            "id": "chatcmpl_x",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
        },
        # missing [DONE]
    ]

    observations = extract_observations(
        provider="openai",
        endpoint="/v1/chat/completions",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=None,
    )

    missing = validate_stream(
        provider="openai",
        endpoint="/v1/chat/completions",
        observations=observations,
        stream_rules=None,
    )

    assert "terminal:[DONE]" in missing


def test_custom_rules_override_defaults() -> None:
    parsed_chunks = [
        {"type": "response.created"},
        {"type": "response.completed"},
    ]

    custom_rules = {
        "min_observations": 1,
        "checks": [
            {"type": "required", "values": ["response.output_text.delta"]},
        ],
    }

    observations = extract_observations(
        provider="openai",
        endpoint="/v1/responses",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=custom_rules,
    )

    missing = validate_stream(
        provider="openai",
        endpoint="/v1/responses",
        observations=observations,
        stream_rules=custom_rules,
    )

    assert missing == ["response.output_text.delta"]
