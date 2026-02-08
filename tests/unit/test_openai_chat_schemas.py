from llm_spec.validation.schemas.openai.chat import (
    ChatCompletionChunkResponse,
    ChatCompletionResponse,
)


def test_openai_chat_completion_response_accepts_typed_content_parts_and_custom_tool():
    payload = {
        "id": "chatcmpl_123",
        "object": "chat.completion",
        "created": 1720000000,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hello!"}],
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "custom",
                            "custom": {"name": "my_tool", "input": {"x": 1}},
                        }
                    ],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
        "system_fingerprint": "fp_abc",
        "service_tier": "default",
    }

    ChatCompletionResponse(**payload)


def test_openai_chat_completion_chunk_accepts_tool_call_delta_shape():
    payload = {
        "id": "chatcmpl_123",
        "object": "chat.completion.chunk",
        "created": 1720000000,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": '{"q":"SF"}'},
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    }

    ChatCompletionChunkResponse(**payload)
