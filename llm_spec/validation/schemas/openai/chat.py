from typing import Any, Literal

from pydantic import BaseModel, model_validator

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

    role: Literal["developer", "system", "user", "assistant", "tool", "function"]
    content: str | list[MessageContentPart] | None = None
    refusal: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None
    function_call: FunctionCall | None = None
    tool_call_id: str | None = None
    name: str | None = None
    audio: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> "Message":
        """Validate role-specific field requirements."""
        if self.role == "assistant":
            # Assistant: content is required unless tool_calls, function_call or refusal is present
            if not any([self.content, self.tool_calls, self.function_call, self.refusal]):
                raise ValueError(
                    "Assistant message must have at least one of 'content', 'tool_calls', 'function_call', or 'refusal'."
                )
        elif self.role == "tool" and not self.tool_call_id:
            raise ValueError("Tool message must have 'tool_call_id'.")
        elif self.role == "function" and not self.name:
            raise ValueError("Function message must have 'name'.")
        return self


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
    reasoning_content: str | None = None
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
