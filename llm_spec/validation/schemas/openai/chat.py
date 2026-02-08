"""OpenAI Chat Completions API Pydantic schemas.

Notes:
- assistant message `content` can be a string or an array of typed parts
- tool calls can be `function` or `custom`
- streaming deltas (chunks) can be partial, so some fields are kept permissive
"""

from typing import Any, Literal

from pydantic import BaseModel

# ============================================================================
# Tool call related models (Tool Calls)
# ============================================================================


class FunctionCall(BaseModel):
    """Function call."""

    name: str
    arguments: str


class FunctionToolCall(BaseModel):
    """Function tool call (non-streaming / full form)."""

    id: str
    type: Literal["function"]
    function: FunctionCall


class CustomToolCallPayload(BaseModel):
    """Custom tool call payload (non-streaming / full form)."""

    name: str
    input: Any


class CustomToolCall(BaseModel):
    """Custom tool call (non-streaming / full form)."""

    id: str
    type: Literal["custom"]
    custom: CustomToolCallPayload


ToolCall = FunctionToolCall | CustomToolCall


# ============================================================================
# Logprobs related models
# ============================================================================


class TopLogprob(BaseModel):
    """Top logprob item."""

    token: str
    logprob: float
    bytes: list[int] | None = None


class LogprobContent(BaseModel):
    """Logprob content item."""

    token: str
    logprob: float
    bytes: list[int] | None = None
    top_logprobs: list[TopLogprob] | None = None


class LogprobsData(BaseModel):
    """Logprobs data."""

    content: list[LogprobContent] | None = None
    refusal: list[LogprobContent] | None = None


# ============================================================================
# Non-streaming response models
# ============================================================================


class MessageContentPart(BaseModel):
    """Message content part (assistant output)."""

    type: str
    text: str | None = None
    refusal: str | None = None
    annotations: list[dict[str, Any]] | None = None


class Message(BaseModel):
    """Message."""

    role: str
    content: str | list[MessageContentPart] | None = None
    refusal: str | None = None
    tool_calls: list[ToolCall] | None = None
    audio: dict[str, Any] | None = None


class Choice(BaseModel):
    """Choice."""

    index: int
    message: Message
    finish_reason: str | None = None
    logprobs: LogprobsData | None = None


class Usage(BaseModel):
    """Usage."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: dict[str, Any] | None = None
    completion_tokens_details: dict[str, Any] | None = None


class ChatCompletionResponse(BaseModel):
    """Chat Completion response model."""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    system_fingerprint: str | None = None
    service_tier: str | None = None


# ============================================================================
# Streaming response models
# ============================================================================


class DeltaMessage(BaseModel):
    """Delta message in streaming responses."""

    role: str | None = None
    content: str | None = None
    refusal: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # streaming structure may be partial
    audio: dict[str, Any] | None = None


class ChunkChoice(BaseModel):
    """Choice item in streaming responses."""

    index: int
    delta: DeltaMessage
    finish_reason: str | None = None
    logprobs: LogprobsData | None = None


class ChatCompletionChunkResponse(BaseModel):
    """Streaming chunk response model."""

    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    choices: list[ChunkChoice]
    usage: Usage | None = None  # only on the last chunk (when stream_options is enabled)
    system_fingerprint: str | None = None
    service_tier: str | None = None
