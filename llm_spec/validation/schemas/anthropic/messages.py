"""Anthropic Messages API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== Request Related Schemas ====================


Role = Literal["user", "assistant"]


class TextBlock(BaseModel):
    """文本内容块"""

    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    """图片来源"""

    type: Literal["base64", "url"]
    media_type: str  # "image/jpeg", "image/png", "image/gif", "image/webp"
    data: str | None = None  # base64 encoded image data
    url: str | None = None  # image URL (if supported)


class ImageBlock(BaseModel):
    """图片内容块"""

    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseBlock(BaseModel):
    """工具使用块（请求中作为对话历史，响应中作为工具调用）"""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    """工具结果块"""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str | list[dict[str, Any]]  # string or content blocks
    is_error: bool | None = None


class ThinkingBlock(BaseModel):
    """思考过程块"""

    type: Literal["thinking"] = "thinking"
    thinking: str
    signature: str | None = None


# Union type for content blocks
ContentBlock = TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock | ThinkingBlock


class Message(BaseModel):
    """消息"""

    role: Role
    content: str | list[ContentBlock]


class ToolInputSchema(BaseModel):
    """工具输入 schema (JSON Schema)"""

    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str] | None = None


class Tool(BaseModel):
    """工具定义"""

    name: str
    description: str
    input_schema: ToolInputSchema


ToolChoiceType = Literal["auto", "any", "tool"]


class ToolChoiceAuto(BaseModel):
    """自动工具选择"""

    type: Literal["auto"] = "auto"


class ToolChoiceAny(BaseModel):
    """任意工具选择"""

    type: Literal["any"] = "any"


class ToolChoiceTool(BaseModel):
    """指定工具选择"""

    type: Literal["tool"] = "tool"
    name: str


ToolChoice = ToolChoiceAuto | ToolChoiceAny | ToolChoiceTool


class Metadata(BaseModel):
    """元数据"""

    user_id: str | None = None


class ThinkingConfig(BaseModel):
    """思考配置（Claude 3.7+）"""

    type: Literal["enabled"] = "enabled"
    budget_tokens: int | None = None


# ==================== Response Related Schemas ====================


StopReason = Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]


class Usage(BaseModel):
    """使用量统计"""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int | None = Field(
        None, alias="cache_creation_input_tokens"
    )
    cache_read_input_tokens: int | None = Field(None, alias="cache_read_input_tokens")


class MessagesResponse(BaseModel):
    """Messages API 响应"""

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
    """流式响应：消息开始事件"""

    type: Literal["message_start"] = "message_start"
    message: MessagesResponse


class ContentBlockStartEvent(BaseModel):
    """流式响应：内容块开始事件"""

    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: ContentBlock


class ContentBlockDelta(BaseModel):
    """内容块增量"""

    type: Literal["text_delta", "input_json_delta"]
    text: str | None = None  # for text_delta
    partial_json: str | None = None  # for input_json_delta


class ContentBlockDeltaEvent(BaseModel):
    """流式响应：内容块增量事件"""

    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: ContentBlockDelta


class ContentBlockStopEvent(BaseModel):
    """流式响应：内容块结束事件"""

    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageDelta(BaseModel):
    """消息增量"""

    stop_reason: StopReason | None = None
    stop_sequence: str | None = None


class MessageDeltaEvent(BaseModel):
    """流式响应：消息增量事件"""

    type: Literal["message_delta"] = "message_delta"
    delta: MessageDelta
    usage: Usage


class MessageStopEvent(BaseModel):
    """流式响应：消息结束事件"""

    type: Literal["message_stop"] = "message_stop"


class PingEvent(BaseModel):
    """流式响应：ping 事件"""

    type: Literal["ping"] = "ping"


class ErrorEvent(BaseModel):
    """流式响应：错误事件"""

    type: Literal["error"] = "error"
    error: dict[str, Any]


# Union type for streaming events
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
