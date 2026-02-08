"""xAI Chat Completions response schemas (OpenAI-compatible)."""

from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    """Message."""

    role: str
    content: str


class Choice(BaseModel):
    """Choice."""

    index: int
    message: Message
    finish_reason: str | None = None


class Usage(BaseModel):
    """Usage."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat Completions response model."""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
