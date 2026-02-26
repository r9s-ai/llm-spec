"""Schema registry for response validation schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

# Lazy import to avoid circular dependencies
_REGISTRY: dict[str, type[BaseModel]] = {}
_INITIALIZED = False


def _init_registry() -> None:
    """Initialize the schema registry."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    # Import all schemas
    from llm_spec.validation.schemas.anthropic import (
        AnthropicStreamChunk,
        MessagesResponse,
    )
    from llm_spec.validation.schemas.gemini import (
        BatchCreateResponse,
        CountTokensResponse,
        EmbedContentResponse,
        GeminiStreamChunk,
        GenerateContentResponse,
    )
    from llm_spec.validation.schemas.openai.audio import (
        AudioStreamEvent,
        AudioTranscriptionResponse,
        AudioTranslationResponse,
        TranscriptionStreamEvent,
    )
    from llm_spec.validation.schemas.openai.chat import (
        ChatCompletionChunkResponse,
        ChatCompletionResponse,
    )
    from llm_spec.validation.schemas.openai.embeddings import (
        EmbeddingResponse as OpenAIEmbeddingResponse,
    )
    from llm_spec.validation.schemas.openai.images import ImageResponse, ImageStreamEvent
    from llm_spec.validation.schemas.openai.responses import ResponseObject, ResponsesStreamEvent
    from llm_spec.validation.schemas.xai import (
        ChatCompletionResponse as XAIChatResponse,
    )

    # Register OpenAI schemas
    _REGISTRY["openai.ChatCompletionResponse"] = ChatCompletionResponse
    _REGISTRY["openai.ChatCompletionChunkResponse"] = ChatCompletionChunkResponse
    _REGISTRY["openai.ResponseObject"] = ResponseObject
    _REGISTRY["openai.ResponsesStreamEvent"] = ResponsesStreamEvent
    _REGISTRY["openai.EmbeddingResponse"] = OpenAIEmbeddingResponse
    _REGISTRY["openai.ImageResponse"] = ImageResponse
    _REGISTRY["openai.ImageStreamEvent"] = ImageStreamEvent
    _REGISTRY["openai.AudioTranscriptionResponse"] = AudioTranscriptionResponse
    _REGISTRY["openai.AudioTranslationResponse"] = AudioTranslationResponse
    _REGISTRY["openai.AudioStreamEvent"] = AudioStreamEvent
    _REGISTRY["openai.TranscriptionStreamEvent"] = TranscriptionStreamEvent

    # Register Gemini schemas
    _REGISTRY["gemini.GenerateContentResponse"] = GenerateContentResponse
    _REGISTRY["gemini.GeminiStreamChunk"] = GeminiStreamChunk
    _REGISTRY["gemini.EmbedContentResponse"] = EmbedContentResponse
    _REGISTRY["gemini.BatchCreateResponse"] = BatchCreateResponse
    _REGISTRY["gemini.CountTokensResponse"] = CountTokensResponse

    # Register Anthropic schemas
    _REGISTRY["anthropic.MessagesResponse"] = MessagesResponse
    _REGISTRY["anthropic.AnthropicStreamChunk"] = AnthropicStreamChunk

    # Register xAI schemas
    _REGISTRY["xai.ChatCompletionResponse"] = XAIChatResponse
    # xAI uses OpenAI-compatible format; streaming schema is the same as OpenAI.
    _REGISTRY["xai.ChatCompletionChunkResponse"] = ChatCompletionChunkResponse

    _INITIALIZED = True


def get_schema(name: str | None) -> type[BaseModel] | None:
    """Get a schema class by name.

    Args:
        name: schema name, formatted as "provider.SchemaClass"

    Returns:
        The corresponding Pydantic model class, or None if not found.
    """
    if not name:
        return None

    _init_registry()
    return _REGISTRY.get(name)


def register_schema(name: str, schema_class: type[BaseModel]) -> None:
    """Register a new schema.

    Args:
        name: schema name
        schema_class: Pydantic model class
    """
    _init_registry()
    _REGISTRY[name] = schema_class


def list_schemas() -> list[str]:
    """List all registered schema names."""
    _init_registry()
    return list(_REGISTRY.keys())
