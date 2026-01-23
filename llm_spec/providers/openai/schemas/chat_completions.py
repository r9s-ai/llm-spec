"""OpenAI Chat Completions API schema definitions.

API Reference: https://platform.openai.com/docs/api-reference/chat/create
Streaming: https://platform.openai.com/docs/api-reference/chat-streaming
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# Request Models
# ============================================================================


class ChatMessageContent(BaseModel):
    """Content part for multimodal messages."""

    type: Literal["text", "image_url"] = Field(..., description="Content type")
    text: str | None = Field(default=None, description="Text content")
    image_url: dict[str, Any] | None = Field(default=None, description="Image URL object")


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool", "developer"] = Field(
        ..., description="Message role"
    )
    content: str | list[ChatMessageContent] | None = Field(
        default=None, description="Message content"
    )
    name: str | None = Field(default=None, description="Optional name for the participant")
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None, description="Tool calls made by assistant"
    )
    tool_call_id: str | None = Field(default=None, description="Tool call ID for tool messages")


class ChatCompletionRequest(BaseModel):
    """Request body for POST /v1/chat/completions."""

    model: str = Field(..., description="Model ID to use")
    messages: list[ChatMessage] = Field(..., description="List of messages")
    temperature: float | None = Field(default=None, ge=0, le=2, description="Sampling temperature")
    top_p: float | None = Field(default=None, ge=0, le=1, description="Nucleus sampling")
    n: int | None = Field(default=None, ge=1, description="Number of completions")
    stream: bool | None = Field(default=None, description="Enable streaming")
    stream_options: dict[str, Any] | None = Field(
        default=None, description="Options for streaming (e.g., include_usage)"
    )
    stop: str | list[str] | None = Field(default=None, description="Stop sequences")
    max_tokens: int | None = Field(default=None, description="Max tokens to generate")
    max_completion_tokens: int | None = Field(default=None, description="Max completion tokens")
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    logit_bias: dict[str, float] | None = Field(default=None)
    logprobs: bool | None = Field(default=None, description="Return log probabilities")
    top_logprobs: int | None = Field(
        default=None, ge=0, le=20, description="Number of top logprobs to return (0-20)"
    )
    user: str | None = Field(default=None, description="User identifier")
    tools: list[dict[str, Any]] | None = Field(default=None, description="Available tools")
    tool_choice: str | dict[str, Any] | None = Field(default=None)
    parallel_tool_calls: bool | None = Field(
        default=None, description="Whether to enable parallel tool calls"
    )
    response_format: dict[str, Any] | None = Field(default=None)
    seed: int | None = Field(default=None, description="Random seed for determinism")
    store: bool | None = Field(default=None, description="Whether to store the output")
    metadata: dict[str, str] | None = Field(default=None, description="Request metadata")


# ============================================================================
# Response Models
# ============================================================================


class ToolCallFunction(BaseModel):
    """Function call details in tool_calls."""

    name: str = Field(..., description="Function name")
    arguments: str = Field(..., description="JSON string containing function arguments")


class ToolCall(BaseModel):
    """Single tool call in the response."""

    id: str = Field(..., description="Unique tool call identifier")
    type: Literal["function"] = Field(..., description="Tool call type")
    function: ToolCallFunction = Field(..., description="Function call details")


class ResponseMessage(BaseModel):
    """Message in the response."""

    role: str = Field(..., description="Always 'assistant'")
    content: str | None = Field(default=None, description="Response content")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls made by the model")
    refusal: str | None = Field(default=None, description="Refusal message if applicable")
    annotations: list[dict[str, Any]] | None = Field(
        default=None, description="Annotations for the message"
    )


class Choice(BaseModel):
    """A single completion choice."""

    index: int = Field(..., description="Choice index")
    message: ResponseMessage = Field(..., description="The generated message")
    finish_reason: str | None = Field(
        default=None,
        description="Reason for completion: stop, length, tool_calls, content_filter",
    )
    logprobs: dict[str, Any] | None = Field(default=None, description="Log probabilities")


class PromptTokensDetails(BaseModel):
    """Breakdown of prompt tokens."""

    cached_tokens: int = Field(default=0, description="Number of cached tokens")
    audio_tokens: int = Field(default=0, description="Number of audio tokens")


class CompletionTokensDetails(BaseModel):
    """Breakdown of completion tokens."""

    reasoning_tokens: int = Field(default=0, description="Tokens used for reasoning (o1/o3 models)")
    audio_tokens: int = Field(default=0, description="Number of audio tokens")
    accepted_prediction_tokens: int = Field(default=0, description="Accepted prediction tokens")
    rejected_prediction_tokens: int = Field(default=0, description="Rejected prediction tokens")


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    completion_tokens: int = Field(..., description="Tokens in the completion")
    total_tokens: int = Field(..., description="Total tokens used")
    prompt_tokens_details: PromptTokensDetails | None = Field(default=None, description="Prompt tokens breakdown")
    completion_tokens_details: CompletionTokensDetails | None = Field(default=None, description="Completion tokens breakdown")


class ChatCompletionResponse(BaseModel):
    """Response body for POST /v1/chat/completions (non-streaming)."""

    id: str = Field(..., description="Unique identifier")
    object: Literal["chat.completion"] = Field(..., description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[Choice] = Field(..., description="Completion choices")
    usage: Usage | None = Field(default=None, description="Token usage")
    system_fingerprint: str | None = Field(default=None, description="System fingerprint")
    service_tier: str | None = Field(default=None, description="Service tier used")


# ============================================================================
# Streaming Response Models
# ============================================================================


class DeltaMessage(BaseModel):
    """Delta content in streaming response."""

    role: str | None = Field(default=None)
    content: str | None = Field(default=None)
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls delta")
    refusal: str | None = Field(default=None)
    annotations: list[dict[str, Any]] | None = Field(default=None)


class StreamChoice(BaseModel):
    """A single streaming choice."""

    index: int = Field(..., description="Choice index")
    delta: DeltaMessage = Field(..., description="Delta content")
    finish_reason: str | None = Field(default=None)
    logprobs: dict[str, Any] | None = Field(default=None)


class ChatCompletionStreamResponse(BaseModel):
    """Single chunk in streaming response."""

    id: str = Field(..., description="Unique identifier")
    object: Literal["chat.completion.chunk"] = Field(..., description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[StreamChoice] = Field(..., description="Streaming choices")
    system_fingerprint: str | None = Field(default=None)
    service_tier: str | None = Field(default=None)
    usage: Usage | None = Field(default=None, description="Only in last chunk with stream_options")
