"""xAI (Grok) API schema definitions.

This package contains Pydantic models for xAI API requests and responses.
xAI API is compatible with OpenAI's API format.

Modules:
- chat_completions: /v1/chat/completions API schemas
"""

from __future__ import annotations

from llm_spec.providers.xai.schemas.chat_completions import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ResponseMessage,
    Usage,
)

__all__ = [
    # Request
    "ChatCompletionRequest",
    "ChatMessage",
    # Response
    "ChatCompletionResponse",
    "Choice",
    "ResponseMessage",
    "Usage",
]
