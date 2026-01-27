"""xAI Chat Completions 响应 Pydantic schemas（与 OpenAI 兼容）"""

from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    """消息"""

    role: str
    content: str


class Choice(BaseModel):
    """选择"""

    index: int
    message: Message
    finish_reason: str | None = None


class Usage(BaseModel):
    """使用量"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat Completions 响应模型"""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
