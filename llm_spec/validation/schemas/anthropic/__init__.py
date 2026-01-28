"""Anthropic API Pydantic schemas

此模块导出所有 Anthropic API 相关的 Pydantic schema。
"""

# Messages API schemas
from llm_spec.validation.schemas.anthropic.messages import (
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
    MessageStartEvent,
    MessageStopEvent,
    MessagesResponse,
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
    "MessageDeltaEvent",
    "MessageStopEvent",
    "PingEvent",
    "ErrorEvent",
]
