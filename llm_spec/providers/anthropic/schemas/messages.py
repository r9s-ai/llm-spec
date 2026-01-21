"""Anthropic Messages API schema definitions.

API Reference: https://docs.anthropic.com/en/api/messages
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class TextContent(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str = Field(..., description="Text content")


class ImageSource(BaseModel):
    """Image source for image content."""

    type: Literal["base64", "url"] = Field(..., description="Source type")
    media_type: str | None = Field(default=None, description="MIME type for base64")
    data: str | None = Field(default=None, description="Base64 data")
    url: str | None = Field(default=None, description="URL for url type")


class ImageContent(BaseModel):
    """Image content block."""

    type: Literal["image"] = "image"
    source: ImageSource = Field(..., description="Image source")


class ToolUseContent(BaseModel):
    """Tool use content block in response."""

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(..., description="Tool use ID")
    name: str = Field(..., description="Tool name")
    input: dict[str, Any] = Field(..., description="Tool input")


class ToolResultContent(BaseModel):
    """Tool result content block in request."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = Field(..., description="Corresponding tool use ID")
    content: str | list[TextContent | ImageContent] = Field(..., description="Tool result")
    is_error: bool | None = Field(default=None, description="Whether result is an error")


class Message(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant"] = Field(..., description="Message role")
    content: str | list[TextContent | ImageContent | ToolUseContent | ToolResultContent] = Field(
        ..., description="Message content"
    )


class Tool(BaseModel):
    """Tool definition."""

    name: str = Field(..., description="Tool name")
    description: str | None = Field(default=None, description="Tool description")
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for input")


class MessageRequest(BaseModel):
    """Request body for POST /v1/messages."""

    model: str = Field(..., description="Model ID")
    messages: list[Message] = Field(..., description="Input messages")
    max_tokens: int = Field(..., description="Maximum tokens to generate")
    system: str | list[TextContent] | None = Field(default=None, description="System prompt")
    temperature: float | None = Field(default=None, ge=0, le=1)
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    stop_sequences: list[str] | None = Field(default=None)
    stream: bool | None = Field(default=None)
    tools: list[Tool] | None = Field(default=None)
    tool_choice: dict[str, Any] | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


# ============================================================================
# Response Models
# ============================================================================


class ResponseTextContent(BaseModel):
    """Text content block in response."""

    type: Literal["text"] = Field(..., description="Content type")
    text: str = Field(..., description="Generated text")


class ResponseToolUseContent(BaseModel):
    """Tool use content block in response."""

    type: Literal["tool_use"] = Field(..., description="Content type")
    id: str = Field(..., description="Tool use ID")
    name: str = Field(..., description="Tool name")
    input: dict[str, Any] = Field(..., description="Tool input")


class ResponseUsage(BaseModel):
    """Token usage statistics."""

    input_tokens: int = Field(..., description="Input tokens")
    output_tokens: int = Field(..., description="Output tokens")
    cache_creation_input_tokens: int | None = Field(default=None)
    cache_read_input_tokens: int | None = Field(default=None)


class MessageResponse(BaseModel):
    """Response body for POST /v1/messages (non-streaming)."""

    id: str = Field(..., description="Unique message ID")
    type: Literal["message"] = Field(..., description="Object type")
    role: Literal["assistant"] = Field(..., description="Always 'assistant'")
    content: list[ResponseTextContent | ResponseToolUseContent] = Field(
        ..., description="Response content blocks"
    )
    model: str = Field(..., description="Model used")
    stop_reason: str | None = Field(
        default=None, description="Reason: end_turn, max_tokens, stop_sequence, tool_use"
    )
    stop_sequence: str | None = Field(default=None, description="Stop sequence if matched")
    usage: ResponseUsage = Field(..., description="Token usage")


# ============================================================================
# Streaming Response Models
# ============================================================================


class MessageStartEvent(BaseModel):
    """message_start event."""

    type: Literal["message_start"] = Field(...)
    message: MessageResponse = Field(...)


class ContentBlockStartEvent(BaseModel):
    """content_block_start event."""

    type: Literal["content_block_start"] = Field(...)
    index: int = Field(...)
    content_block: ResponseTextContent | ResponseToolUseContent = Field(...)


class ContentBlockDeltaEvent(BaseModel):
    """content_block_delta event."""

    type: Literal["content_block_delta"] = Field(...)
    index: int = Field(...)
    delta: dict[str, Any] = Field(...)


class ContentBlockStopEvent(BaseModel):
    """content_block_stop event."""

    type: Literal["content_block_stop"] = Field(...)
    index: int = Field(...)


class MessageDeltaEvent(BaseModel):
    """message_delta event."""

    type: Literal["message_delta"] = Field(...)
    delta: dict[str, Any] = Field(...)
    usage: dict[str, int] = Field(...)


class MessageStopEvent(BaseModel):
    """message_stop event."""

    type: Literal["message_stop"] = Field(...)


# Union type for all stream events
MessageStreamResponse = (
    MessageStartEvent
    | ContentBlockStartEvent
    | ContentBlockDeltaEvent
    | ContentBlockStopEvent
    | MessageDeltaEvent
    | MessageStopEvent
)
