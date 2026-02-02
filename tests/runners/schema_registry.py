"""Schema 注册表 - 统一管理所有响应 Schema"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from pydantic import BaseModel

# 延迟导入，避免循环依赖
_REGISTRY: dict[str, Type["BaseModel"]] = {}
_INITIALIZED = False


def _init_registry() -> None:
    """初始化 Schema 注册表"""
    global _INITIALIZED
    if _INITIALIZED:
        return

    # 导入所有 schema
    from llm_spec.validation.schemas.openai.chat import (
        ChatCompletionResponse,
        ChatCompletionChunkResponse,
    )
    from llm_spec.validation.schemas.gemini import (
        GenerateContentResponse,
    )
    from llm_spec.validation.schemas.anthropic import (
        MessagesResponse,
    )
    from llm_spec.validation.schemas.xai import (
        ChatCompletionResponse as XAIChatResponse,
    )
    from llm_spec.validation.schemas.openai.responses import ResponseObject
    from llm_spec.validation.schemas.openai.embeddings import EmbeddingResponse as OpenAIEmbeddingResponse
    from llm_spec.validation.schemas.openai.audio import AudioTranscriptionResponse, AudioTranslationResponse
    from llm_spec.validation.schemas.gemini import GenerateContentResponse, EmbedContentResponse, BatchCreateResponse, CountTokensResponse

    # 注册 OpenAI schemas
    _REGISTRY["openai.ChatCompletionResponse"] = ChatCompletionResponse
    _REGISTRY["openai.ChatCompletionChunkResponse"] = ChatCompletionChunkResponse
    _REGISTRY["openai.ResponseObject"] = ResponseObject
    _REGISTRY["openai.EmbeddingResponse"] = OpenAIEmbeddingResponse
    _REGISTRY["openai.ImageResponse"] = ImageResponse
    _REGISTRY["openai.AudioTranscriptionResponse"] = AudioTranscriptionResponse
    _REGISTRY["openai.AudioTranslationResponse"] = AudioTranslationResponse

    # 注册 Gemini schemas
    _REGISTRY["gemini.GenerateContentResponse"] = GenerateContentResponse
    _REGISTRY["gemini.EmbedContentResponse"] = EmbedContentResponse
    _REGISTRY["gemini.BatchCreateResponse"] = BatchCreateResponse
    _REGISTRY["gemini.CountTokensResponse"] = CountTokensResponse

    # 注册 Anthropic schemas
    _REGISTRY["anthropic.MessagesResponse"] = MessagesResponse
    # TODO: 添加 Anthropic 流式 schema

    # 注册 xAI schemas
    _REGISTRY["xai.ChatCompletionResponse"] = XAIChatResponse


    _INITIALIZED = True


def get_schema(name: str | None) -> Type["BaseModel"] | None:
    """获取 schema 类

    Args:
        name: schema 名称，格式为 "provider.SchemaClass"

    Returns:
        对应的 Pydantic 模型类，如果不存在则返回 None
    """
    if not name:
        return None

    _init_registry()
    return _REGISTRY.get(name)


def register_schema(name: str, schema_class: Type["BaseModel"]) -> None:
    """注册新的 schema

    Args:
        name: schema 名称
        schema_class: Pydantic 模型类
    """
    _init_registry()
    _REGISTRY[name] = schema_class


def list_schemas() -> list[str]:
    """列出所有已注册的 schema 名称"""
    _init_registry()
    return list(_REGISTRY.keys())
