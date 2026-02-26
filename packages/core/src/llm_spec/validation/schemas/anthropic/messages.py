"""Anthropic Messages API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ==================== Request Related Schemas ====================


Role = Literal["user", "assistant"]


class TextBlock(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    """Image source."""

    type: Literal["base64", "url"]
    media_type: str  # "image/jpeg", "image/png", "image/gif", "image/webp"
    data: str | None = None  # base64 encoded image data
    url: str | None = None  # image URL (if supported)


class ImageBlock(BaseModel):
    """Image content block."""

    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseBlock(BaseModel):
    """Tool use block (history in requests, tool call in responses)."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    """Tool result block."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list[dict[str, Any]]  # string or content blocks
    is_error: bool | None = None


class ThinkingBlock(BaseModel):
    """Thinking block."""

    type: Literal["thinking"] = "thinking"
    thinking: str
    signature: str | None = None


class RedactedThinkingBlock(BaseModel):
    """Redacted thinking block."""

    type: Literal["redacted_thinking"] = "redacted_thinking"
    data: str


class ServerToolUseBlock(BaseModel):
    """Server tool use block."""

    type: Literal["server_tool_use"] = "server_tool_use"
    id: str
    name: str
    input: dict[str, Any]


class WebSearchToolResultBlock(BaseModel):
    """Web search tool result block."""

    type: Literal["web_search_tool_result"] = "web_search_tool_result"
    content: str | list[dict[str, Any]]


# Union type for content blocks
ContentBlock = (
    TextBlock
    | ImageBlock
    | ToolUseBlock
    | ToolResultBlock
    | ThinkingBlock
    | RedactedThinkingBlock
    | ServerToolUseBlock
    | WebSearchToolResultBlock
)


class Message(BaseModel):
    """Message."""

    role: Role
    content: str | list[ContentBlock]


class ToolInputSchema(BaseModel):
    """Tool input schema (JSON Schema)."""

    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str] | None = None


class Tool(BaseModel):
    """Tool definition."""

    name: str
    description: str
    input_schema: ToolInputSchema


ToolChoiceType = Literal["auto", "any", "tool"]


class ToolChoiceAuto(BaseModel):
    """Auto tool choice."""

    type: Literal["auto"] = "auto"


class ToolChoiceAny(BaseModel):
    """Any tool choice."""

    type: Literal["any"] = "any"


class ToolChoiceTool(BaseModel):
    """Specific tool choice."""

    type: Literal["tool"] = "tool"
    name: str


ToolChoice = ToolChoiceAuto | ToolChoiceAny | ToolChoiceTool


class Metadata(BaseModel):
    """Metadata."""

    user_id: str | None = None


class ThinkingConfig(BaseModel):
    """Thinking config (Claude 3.7+)."""

    type: Literal["enabled"] = "enabled"
    budget_tokens: int | None = None


# ==================== Response Related Schemas ====================


StopReason = Literal[
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "pause_turn",
    "refusal",
]


class Usage(BaseModel):
    """Usage stats."""

    input_tokens: int | None = None  # message_delta may only include output_tokens in streaming
    output_tokens: int
    cache_creation_input_tokens: int | None = Field(None, alias="cache_creation_input_tokens")
    cache_read_input_tokens: int | None = Field(None, alias="cache_read_input_tokens")


class MessagesResponse(BaseModel):
    """Messages API response."""

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: list[ContentBlock]
    model: str
    stop_reason: StopReason | None = None
    stop_sequence: str | None = None
    usage: Usage


# ==================== Streaming Response Schemas ====================


class MessageStartEvent(BaseModel):
    """Streaming: message_start event."""

    type: Literal["message_start"] = "message_start"
    message: MessagesResponse


class ContentBlockStartEvent(BaseModel):
    """Streaming: content_block_start event."""

    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: ContentBlock


class CitationCharLocation(BaseModel):
    """Citation by character location."""

    type: Literal["char_location"] = "char_location"
    cited_text: str
    document_index: int
    document_title: str | None = None
    start_char_index: int
    end_char_index: int


class CitationPageLocation(BaseModel):
    """Citation by page location."""

    type: Literal["page_location"] = "page_location"
    cited_text: str
    document_index: int
    document_title: str | None = None
    start_page_number: int
    end_page_number: int


class Citation(BaseModel):
    """Citation."""

    citation: CitationCharLocation | CitationPageLocation


class ContentBlockDelta(BaseModel):
    """Content block delta (supports multiple delta types)."""

    type: Literal[
        "text_delta",
        "input_json_delta",
        "thinking_delta",
        "signature_delta",
        "citations_delta",
    ]
    text: str | None = None  # for text_delta
    partial_json: str | None = None  # for input_json_delta
    thinking: str | None = None  # for thinking_delta
    signature: str | None = None  # for signature_delta
    citation: CitationCharLocation | CitationPageLocation | None = None  # for citations_delta


class ContentBlockDeltaEvent(BaseModel):
    """Streaming: content_block_delta event."""

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: ContentBlockDelta


class ContentBlockStopEvent(BaseModel):
    """Streaming: content_block_stop event."""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageDelta(BaseModel):
    """Message delta."""

    stop_reason: StopReason | None = None
    stop_sequence: str | None = None


class MessageDeltaUsage(BaseModel):
    """Usage in message_delta events (output_tokens only)."""

    output_tokens: int


class MessageDeltaEvent(BaseModel):
    """Streaming: message_delta event.

    Notes:
    - In message_delta, usage typically includes output_tokens only (input_tokens is reported in message_start).
    - In some scenarios (e.g. extended thinking), usage may be missing entirely.
    """

    type: Literal["message_delta"] = "message_delta"
    delta: MessageDelta
    usage: MessageDeltaUsage | None = None  # optional; may be missing in some scenarios


class MessageStopEvent(BaseModel):
    """Streaming: message_stop event."""

    type: Literal["message_stop"] = "message_stop"


class PingEvent(BaseModel):
    """Streaming: ping event."""

    type: Literal["ping"] = "ping"


class ErrorEvent(BaseModel):
    """Streaming: error event."""

    type: Literal["error"] = "error"
    error: dict[str, Any]


# Union type for streaming events (for type checking)
StreamEvent = (
    MessageStartEvent
    | ContentBlockStartEvent
    | ContentBlockDeltaEvent
    | ContentBlockStopEvent
    | MessageDeltaEvent
    | MessageStopEvent
    | PingEvent
    | ErrorEvent
)


# ==================== Streaming Chunk Schema (for validation) ====================


class AnthropicStreamChunk(BaseModel):
    """Unified model for Anthropic streaming events.

    Used to validate each event in an Anthropic SSE stream. Because payload shapes differ by event type,
    this model uses optional fields to cover all variants. In practice, validation focuses on `type` and
    the required fields for that type.

    Note:
    - usage is full Usage in message_start
    - usage is MessageDeltaUsage (output_tokens only) in message_delta
    """

    # Fields shared by all events
    type: Literal[
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
        "ping",
        "error",
    ]

    # message_start fields
    message: MessagesResponse | None = None

    # content_block_start / content_block_stop fields
    index: int | None = None
    content_block: ContentBlock | None = None

    # content_block_delta fields
    delta: ContentBlockDelta | MessageDelta | None = None

    # message_delta fields (usage)
    # Can be full Usage (message_start) or MessageDeltaUsage (message_delta)
    usage: Usage | MessageDeltaUsage | None = None

    # error fields
    error: dict[str, Any] | None = None
