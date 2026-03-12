from llm_spec.validation.schemas.openai.responses import ResponsesStreamEvent


def test_openai_responses_stream_event_accepts_response_queued_snapshot_shape():
    payload = {
        "type": "response.queued",
        "sequence_number": 0,
        "response": {
            "id": "resp_123",
            "object": "response",
            "status": "queued",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    }

    ResponsesStreamEvent(**payload)


def test_openai_responses_stream_event_accepts_function_call_arguments_delta_shape():
    payload = {
        "type": "response.function_call_arguments.delta",
        "sequence_number": 12,
        "item_id": "item_1",
        "output_index": 0,
        "call_id": "call_1",
        "name": "get_weather",
        "delta": '{"q":"S',
    }

    ResponsesStreamEvent(**payload)
