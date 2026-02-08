"""Anthropic API Pydantic schemas

This module exports all Pydantic schemas related to the Anthropic API.
"""

# Messages API schemas
from llm_spec.validation.schemas.anthropic.messages import (
    AnthropicStreamChunk,
    ContentBlock,
    ContentBlockDelta,
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    ErrorEvent,
    ImageBlock,
    ImageSource,
    Message,
    MessageDelta,
    MessageDeltaEvent,
    MessageDeltaUsage,  # usage type used by message_delta
    MessagesResponse,
    MessageStartEvent,
    MessageStopEvent,
    Metadata,
    PingEvent,
    Role,
    StopReason,
    StreamEvent,
    TextBlock,
    ThinkingConfig,
    Tool,
    ToolChoice,
    ToolChoiceAny,
    ToolChoiceAuto,
    ToolChoiceTool,
    ToolChoiceType,
    ToolInputSchema,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
)

__all__ = [
    # Request - Content Blocks
    "TextBlock",
    "ImageBlock",
    "ImageSource",
    "ToolUseBlock",
    "ToolResultBlock",
    "ContentBlock",
    # Request - Messages
    "Message",
    "Role",
    # Request - Tools
    "Tool",
    "ToolInputSchema",
    "ToolChoice",
    "ToolChoiceAuto",
    "ToolChoiceAny",
    "ToolChoiceTool",
    "ToolChoiceType",
    # Request - Config
    "Metadata",
    "ThinkingConfig",
    # Response - Main
    "MessagesResponse",
    "Usage",
    "StopReason",
    # Streaming - Events
    "StreamEvent",
    "MessageStartEvent",
    "ContentBlockStartEvent",
    "ContentBlockDelta",
    "ContentBlockDeltaEvent",
    "ContentBlockStopEvent",
    "MessageDelta",
    "MessageDeltaUsage",  # usage type used by message_delta
    "MessageDeltaEvent",
    "MessageStopEvent",
    "PingEvent",
    "ErrorEvent",
    # Streaming - Chunk
    "AnthropicStreamChunk",
]
