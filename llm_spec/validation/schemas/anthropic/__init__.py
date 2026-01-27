"""Anthropic Messages 响应 Pydantic schemas"""

from typing import Literal

from pydantic import BaseModel


class ContentBlock(BaseModel):
    """内容块"""

    type: Literal["text"]
    text: str


class Usage(BaseModel):
    """使用量"""

    input_tokens: int
    output_tokens: int


class MessagesResponse(BaseModel):
    """Messages 响应模型"""

    id: str
    type: Literal["message"]
    role: Literal["assistant"]
    content: list[ContentBlock]
    model: str
    stop_reason: str | None = None
    stop_sequence: str | None = None
    usage: Usage
