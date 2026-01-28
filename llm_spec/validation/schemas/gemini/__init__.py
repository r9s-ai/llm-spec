"""Google Gemini API Pydantic schemas

此模块导出所有 Gemini API 相关的 Pydantic schema。
"""

# GenerateContent schemas
from llm_spec.validation.schemas.gemini.generate_content import (
    BlockReason,
    Candidate,
    CitationMetadata,
    CitationSource,
    CodeExecution,
    CodeExecutionResult,
    Content,
    ExecutableCode,
    FileData,
    FinishReason,
    FunctionCall,
    FunctionCallingConfig,
    FunctionDeclaration,
    FunctionResponse,
    GenerateContentResponse,
    GenerationConfig,
    GroundingAttribution,
    HarmBlockThreshold,
    HarmCategory,
    HarmProbability,
    InlineData,
    ModelStage,
    ModelStatus,
    Part,
    PromptFeedback,
    SafetyRating,
    SafetySetting,
    SystemInstruction,
    Tool,
    ToolConfig,
    UsageMetadata,
)

# Embeddings schemas
from llm_spec.validation.schemas.gemini.embeddings import (
    BatchEmbedContentsResponse,
    EmbedContentRequest,
    EmbedContentResponse,
    Embedding,
    TaskType,
)

# Tokens schemas
from llm_spec.validation.schemas.gemini.tokens import (
    CountTokensResponse,
    ModalityTokenDetails,
)

__all__ = [
    # GenerateContent - Request
    "Part",
    "Content",
    "InlineData",
    "FileData",
    "FunctionCall",
    "FunctionResponse",
    "ExecutableCode",
    "CodeExecutionResult",
    "Tool",
    "FunctionDeclaration",
    "CodeExecution",
    "FunctionCallingConfig",
    "ToolConfig",
    "SafetySetting",
    "GenerationConfig",
    "SystemInstruction",
    "HarmCategory",
    "HarmBlockThreshold",
    # GenerateContent - Response
    "Candidate",
    "SafetyRating",
    "CitationSource",
    "CitationMetadata",
    "GroundingAttribution",
    "PromptFeedback",
    "UsageMetadata",
    "ModelStatus",
    "GenerateContentResponse",
    "HarmProbability",
    "FinishReason",
    "BlockReason",
    "ModelStage",
    # Embeddings
    "TaskType",
    "EmbedContentRequest",
    "Embedding",
    "EmbedContentResponse",
    "BatchEmbedContentsResponse",
    # Tokens
    "CountTokensResponse",
    "ModalityTokenDetails",
]
