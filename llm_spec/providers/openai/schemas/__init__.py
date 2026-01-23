"""OpenAI API schema definitions.

This package contains Pydantic models for OpenAI API requests and responses.

Modules:
- chat_completions: /v1/chat/completions API schemas
- responses: /v1/responses API schemas
- audio: /v1/audio/* API schemas (speech, transcriptions, translations)
- images: /v1/images/* API schemas (generations, edits, variations)
- embeddings: /v1/embeddings API schemas
"""

from __future__ import annotations

from llm_spec.providers.openai.schemas.audio import (
    DiarizedSegment,
    ServerVadConfig,
    SpeechRequest,
    TranscriptionDiarizedResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
    TranscriptionVerboseResponse,
    TranscriptionWord,
    TranslationRequest,
    TranslationResponse,
    TranslationVerboseResponse,
)
from llm_spec.providers.openai.schemas.chat_completions import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    ChatMessage,
    ChatMessageContent,
    Choice,
    DeltaMessage,
    ResponseMessage,
    StreamChoice,
    Usage,
)
from llm_spec.providers.openai.schemas.embeddings import (
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingUsage,
)
from llm_spec.providers.openai.schemas.images import (
    ImageData,
    ImageEditCompletedEvent,
    ImageEditPartialImageEvent,
    ImageEditRequest,
    ImageGenerationCompletedEvent,
    ImageGenerationPartialImageEvent,
    ImageGenerationRequest,
    ImageResponse,
    ImageStreamEvent,
    ImageUsage,
    ImageUsageDetails,
    ImageVariationRequest,
)
from llm_spec.providers.openai.schemas.responses import (
    CodeInterpreterTool,
    ContentPartAddedEvent,
    ContentPartDoneEvent,
    FileSearchCallOutput,
    FunctionCallOutput,
    FunctionTool,
    ImageGenerationTool,
    McpTool,
    OutputItemAddedEvent,
    OutputItemDoneEvent,
    OutputMessage,
    OutputTextContent,
    OutputTextDeltaEvent,
    OutputTextDoneEvent,
    ReasoningConfig,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseInProgressEvent,
    ResponseInputMessage,
    ResponseInputMessageContent,
    ResponseInputTokensDetails,
    ResponseObject,
    ResponseOutputTokensDetails,
    ResponseRequest,
    ResponseStreamEvent,
    ResponseUsage,
    WebSearchCallOutput,
    WebSearchTool,
)

__all__ = [
    # Chat Completions API
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatCompletionStreamResponse",
    "ChatMessage",
    "ChatMessageContent",
    "Choice",
    "DeltaMessage",
    "ResponseMessage",
    "StreamChoice",
    "Usage",
    # Responses API - Request
    "ResponseRequest",
    "ResponseInputMessage",
    "ResponseInputMessageContent",
    "ReasoningConfig",
    # Responses API - Tools
    "FunctionTool",
    "WebSearchTool",
    "CodeInterpreterTool",
    "McpTool",
    "ImageGenerationTool",
    # Responses API - Response
    "ResponseObject",
    "ResponseUsage",
    "ResponseInputTokensDetails",
    "ResponseOutputTokensDetails",
    "OutputMessage",
    "OutputTextContent",
    "FunctionCallOutput",
    "WebSearchCallOutput",
    "FileSearchCallOutput",
    # Responses API - Streaming
    "ResponseStreamEvent",
    "ResponseCreatedEvent",
    "ResponseInProgressEvent",
    "ResponseCompletedEvent",
    "ResponseFailedEvent",
    "OutputItemAddedEvent",
    "OutputItemDoneEvent",
    "ContentPartAddedEvent",
    "ContentPartDoneEvent",
    "OutputTextDeltaEvent",
    "OutputTextDoneEvent",
    # Audio API - Speech (TTS)
    "SpeechRequest",
    # Audio API - Transcription
    "TranscriptionRequest",
    "TranscriptionResponse",
    "TranscriptionVerboseResponse",
    "TranscriptionDiarizedResponse",
    "TranscriptionWord",
    "TranscriptionSegment",
    "DiarizedSegment",
    "ServerVadConfig",
    # Audio API - Translation
    "TranslationRequest",
    "TranslationResponse",
    "TranslationVerboseResponse",
    # Images API
    "ImageGenerationRequest",
    "ImageEditRequest",
    "ImageVariationRequest",
    "ImageResponse",
    "ImageData",
    "ImageUsage",
    "ImageUsageDetails",
    # Images API - Streaming Events
    "ImageStreamEvent",
    "ImageGenerationPartialImageEvent",
    "ImageGenerationCompletedEvent",
    "ImageEditPartialImageEvent",
    "ImageEditCompletedEvent",
    # Embeddings API
    "EmbeddingRequest",
    "EmbeddingResponse",
    "EmbeddingData",
    "EmbeddingUsage",
]
