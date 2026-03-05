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


# ---------- event_type_match tests ----------


def test_event_type_match_passes_when_sse_event_matches_data_type() -> None:
    """All chunks have event matching data.type -> no errors."""
    parsed_chunks = [
        {"type": "message_start", "event": "message_start"},
        {"type": "content_block_start", "event": "content_block_start"},
        {"type": "content_block_delta", "event": "content_block_delta"},
        {"type": "content_block_stop", "event": "content_block_stop"},
        {"type": "message_delta", "event": "message_delta"},
        {"type": "message_stop", "event": "message_stop"},
    ]

    rules: dict = {
        "checks": [{"type": "event_type_match"}],
    }

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=rules,
    )

    assert missing == []


def test_event_type_match_detects_missing_sse_event() -> None:
    """Chunk without event should be reported."""
    parsed_chunks = [
        {"type": "message_start"},  # no event
        {"type": "message_stop", "event": "message_stop"},
    ]

    rules: dict = {
        "checks": [{"type": "event_type_match"}],
    }

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=rules,
    )

    assert len(missing) == 1
    assert "event_missing:chunk#0" in missing[0]


def test_event_type_match_detects_mismatch() -> None:
    """SSE event != data.type should be reported."""
    parsed_chunks = [
        {"type": "message_start", "event": "wrong_event"},
        {"type": "message_stop", "event": "message_stop"},
    ]

    rules: dict = {
        "checks": [{"type": "event_type_match"}],
    }

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=rules,
    )

    assert len(missing) == 1
    assert "event_type_mismatch:chunk#0" in missing[0]
    assert "event=wrong_event" in missing[0]
    assert "type=message_start" in missing[0]


def test_event_type_match_detects_missing_type() -> None:
    """Chunk with event but no type should be reported as type_missing."""
    parsed_chunks = [
        {"event": "message_start"},  # has event, no type
        {"type": "message_stop", "event": "message_stop"},
    ]

    rules: dict = {
        "checks": [
            # {"type": "event_type_match"}
        ],
    }

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=rules,
    )

    assert len(missing) == 1
    assert "type_missing:chunk#0" in missing[0]


def test_event_type_match_skips_done_marker() -> None:
    """[DONE] chunks (done=True) should be skipped."""
    parsed_chunks = [
        {"type": "response.created", "event": "response.created"},
        {"done": True, "status": "completed"},  # no event, no type — should be skipped
    ]

    rules: dict = {
        "checks": [{"type": "event_type_match"}],
    }

    observations = extract_observations(
        provider="openai",
        endpoint="/v1/responses",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="openai",
        endpoint="/v1/responses",
        observations=observations,
        stream_rules=rules,
    )

    assert missing == []


def test_event_type_match_auto_enabled_when_event_or_type_present() -> None:
    """Auto-add event_type_match when chunks carry event/type fields."""
    parsed_chunks = [
        {"type": "message_start"},  # no event -> should be flagged
        {"type": "message_stop", "event": "message_stop"},
    ]

    rules: dict = {
        "checks": [{"type": "required_terminal", "value": "message_stop"}],
    }

    observations = extract_observations(
        provider="anthropic",
        endpoint="/v1/messages",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="anthropic",
        endpoint="/v1/messages",
        observations=observations,
        stream_rules=rules,
    )

    assert any("event_missing:chunk#0" in m for m in missing)


def test_event_type_match_not_auto_enabled_without_event_or_type() -> None:
    """Do not auto-add event_type_match when chunks have no event/type fields."""
    parsed_chunks = [
        {
            "candidates": [
                {"content": {"parts": [{"text": "Hello"}]}},
            ]
        }
    ]

    rules: dict = {
        "checks": [],
    }

    observations = extract_observations(
        provider="gemini",
        endpoint="/v1beta/models/gemini-3-flash-preview:streamGenerateContent",
        parsed_chunks=parsed_chunks,
        raw_chunks=[],
        stream_rules=rules,
    )

    missing = validate_stream(
        provider="gemini",
        endpoint="/v1beta/models/gemini-3-flash-preview:streamGenerateContent",
        observations=observations,
        stream_rules=rules,
    )

    assert missing == []


def test_anthropic_defaults_include_event_type_match() -> None:
    """Anthropic defaults should now include event_type_match, failing when SSE event is missing."""
    parsed_chunks = [
        {"type": "message_start"},  # no event
        {"type": "content_block_start"},
        {"type": "content_block_delta"},
        {"type": "content_block_stop"},
        {"type": "message_delta"},
        {"type": "message_stop"},
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

    # Should contain event_missing errors (one per chunk)
    event_errors = [m for m in missing if "event_missing" in m]
    assert len(event_errors) == 6
