"""xAI (Grok) Chat Completions API schema definitions.

xAI API is compatible with OpenAI's API format.
API Reference: https://docs.x.ai/api
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models (OpenAI-compatible)
# ============================================================================


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Request body for POST /v1/chat/completions."""

    model: str = Field(..., description="Model ID (e.g., 'grok-beta')")
    messages: list[ChatMessage] = Field(..., description="List of messages")
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    n: int | None = Field(default=None, ge=1)
    stream: bool | None = Field(default=None)
    stop: str | list[str] | None = Field(default=None)
    max_tokens: int | None = Field(default=None)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)


# ============================================================================
# Response Models (OpenAI-compatible)
# ============================================================================


class ResponseMessage(BaseModel):
    """Message in the response."""

    role: str = Field(..., description="Always 'assistant'")
    content: str | None = Field(default=None, description="Response content")


class Choice(BaseModel):
    """A single completion choice."""

    index: int = Field(..., description="Choice index")
    message: ResponseMessage = Field(..., description="The generated message")
    finish_reason: str | None = Field(default=None, description="Completion reason")


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Tokens in the prompt")
    completion_tokens: int = Field(..., description="Tokens in the completion")
    total_tokens: int = Field(..., description="Total tokens used")


class ChatCompletionResponse(BaseModel):
    """Response body for POST /v1/chat/completions."""

    id: str = Field(..., description="Unique identifier")
    object: str = Field(..., description="Object type")
    created: int = Field(..., description="Unix timestamp")
    model: str = Field(..., description="Model used")
    choices: list[Choice] = Field(..., description="Completion choices")
    usage: Usage | None = Field(default=None, description="Token usage")
    system_fingerprint: str | None = Field(default=None)
