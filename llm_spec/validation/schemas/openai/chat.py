"""OpenAI Chat Completions 响应 Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# 工具调用相关模型 (Tool Calls)
# ============================================================================


class FunctionCall(BaseModel):
    """函数调用模型"""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用模型"""

    id: str
    type: Literal["function"]
    function: FunctionCall


# ============================================================================
# Logprobs 相关模型
# ============================================================================


class TopLogprob(BaseModel):
    """Top logprob 项"""

    token: str
    logprob: float
    bytes: list[int] | None = None


class LogprobContent(BaseModel):
    """Logprob 内容项"""

    token: str
    logprob: float
    bytes: list[int] | None = None
    top_logprobs: list[TopLogprob] | None = None


class LogprobsData(BaseModel):
    """Logprobs 数据模型"""

    content: list[LogprobContent] | None = None


# ============================================================================
# 非流式响应模型 (Non-streaming)
# ============================================================================


class Message(BaseModel):
    """消息模型"""

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class Choice(BaseModel):
    """选择项模型"""

    index: int
    message: Message
    finish_reason: str | None = None
    logprobs: LogprobsData | None = None


class Usage(BaseModel):
    """使用量模型"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat Completion 响应模型"""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    system_fingerprint: str | None = None


# ============================================================================
# 流式响应模型 (Streaming)
# ============================================================================


class DeltaMessage(BaseModel):
    """流式响应中的增量消息"""

    role: str | None = None
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # 流式时结构可能不完整


class ChunkChoice(BaseModel):
    """流式响应中的选择项"""

    index: int
    delta: DeltaMessage
    finish_reason: str | None = None
    logprobs: LogprobsData | None = None


class ChatCompletionChunkResponse(BaseModel):
    """流式响应 chunk 模型"""

    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    choices: list[ChunkChoice]
    usage: Usage | None = None  # 仅在最后一个 chunk（stream_options 启用时）
    system_fingerprint: str | None = None
