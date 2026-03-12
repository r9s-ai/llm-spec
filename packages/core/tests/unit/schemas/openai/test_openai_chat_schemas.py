import pytest
from pydantic import ValidationError

from llm_spec.validation.schemas.openai.chat import (
    ChatCompletionChunkResponse,
    ChatCompletionResponse,
    FunctionCall,
    FunctionToolCall,
    Message,
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


def test_openai_chat_completion_response_requires_mandatory_fields():
    # Missing 'id'
    payload = {
        "object": "chat.completion",
        "created": 1720000000,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
    }
    with pytest.raises(ValidationError):
        ChatCompletionResponse(**payload)


def test_openai_chat_completion_with_reasoning_and_refusal():
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
                    "content": "Final answer",
                    "reasoning_content": "Chain of thought...",
                    "refusal": "I cannot do that.",
                },
                "finish_reason": "stop",
            }
        ],
    }
    resp = ChatCompletionResponse(**payload)
    assert resp.choices[0].message.reasoning_content == "Chain of thought..."
    assert resp.choices[0].message.refusal == "I cannot do that."


def test_openai_message_role_validation():
    # Valid developer role
    Message(role="developer", content="You are a helpful assistant")

    # Invalid assistant (missing everything)
    with pytest.raises(ValidationError, match="Assistant message must have at least one"):
        Message(role="assistant")

    # Valid assistant variants
    Message(role="assistant", content="Hi")
    Message(
        role="assistant",
        tool_calls=[
            FunctionToolCall(
                id="c1", type="function", function=FunctionCall(name="f1", arguments="{}")
            )
        ],
    )
    Message(role="assistant", function_call=FunctionCall(name="f1", arguments="{}"))
    Message(role="assistant", refusal="No")

    # Tool role validation
    with pytest.raises(ValidationError, match="Tool message must have 'tool_call_id'"):
        Message(role="tool", content="done")
    Message(role="tool", content="done", tool_call_id="call_1")

    # Function role validation
    with pytest.raises(ValidationError, match="Function message must have 'name'"):
        Message(role="function", content="done")
    Message(role="function", content="done", name="get_weather")


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
