"""Google Gemini GenerateContent API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ==================== Request Related Schemas ====================


class InlineData(BaseModel):
    """Inline data (base64 encoded)."""

    mime_type: str = Field(..., alias="mimeType")
    data: str


class FileData(BaseModel):
    """File data (File API reference)."""

    mime_type: str = Field(..., alias="mimeType")
    file_uri: str = Field(..., alias="fileUri")


class FunctionCall(BaseModel):
    """Function call."""

    name: str
    args: dict[str, Any] | None = None


class FunctionResponse(BaseModel):
    """Function response."""

    name: str
    response: dict[str, Any]


class ExecutableCode(BaseModel):
    """Executable code."""

    language: Literal["PYTHON"] = "PYTHON"
    code: str


class CodeExecutionResult(BaseModel):
    """Code execution result."""

    outcome: Literal["OUTCOME_OK", "OUTCOME_FAILED", "OUTCOME_DEADLINE_EXCEEDED"]
    output: str | None = None


class Part(BaseModel):
    """Content part (supports multiple types)."""

    text: str | None = None
    inline_data: InlineData | None = Field(None, alias="inlineData")
    file_data: FileData | None = Field(None, alias="fileData")
    function_call: FunctionCall | None = Field(None, alias="functionCall")
    function_response: FunctionResponse | None = Field(None, alias="functionResponse")
    executable_code: ExecutableCode | None = Field(None, alias="executableCode")
    code_execution_result: CodeExecutionResult | None = Field(None, alias="codeExecutionResult")
    thought: bool | None = None  # whether this is model "thinking" content (thinking models)


class Content(BaseModel):
    """Content (contains multiple parts)."""

    parts: list[Part]
    role: str | None = None


class FunctionDeclaration(BaseModel):
    """Function declaration."""

    name: str
    description: str
    parameters: dict[str, Any] | None = None


class CodeExecution(BaseModel):
    """Code execution tool."""

    pass


class Tool(BaseModel):
    """Tool definition."""

    function_declarations: list[FunctionDeclaration] | None = Field(
        None, alias="functionDeclarations"
    )
    code_execution: CodeExecution | None = Field(None, alias="codeExecution")


class FunctionCallingConfig(BaseModel):
    """Function calling config."""

    mode: Literal["AUTO", "ANY", "NONE"] | None = None
    allowed_function_names: list[str] | None = Field(None, alias="allowedFunctionNames")


class ToolConfig(BaseModel):
    """Tool config."""

    function_calling_config: FunctionCallingConfig | None = Field(
        None, alias="functionCallingConfig"
    )


HarmCategory = Literal[
    "HARM_CATEGORY_UNSPECIFIED",
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_CIVIC_INTEGRITY",
]

HarmBlockThreshold = Literal[
    "HARM_BLOCK_THRESHOLD_UNSPECIFIED",
    "BLOCK_NONE",
    "BLOCK_ONLY_HIGH",
    "BLOCK_MEDIUM_AND_ABOVE",
    "BLOCK_LOW_AND_ABOVE",
]


class SafetySetting(BaseModel):
    """Safety setting."""

    category: HarmCategory
    threshold: HarmBlockThreshold


class GenerationConfig(BaseModel):
    """Generation config."""

    candidate_count: int | None = Field(None, alias="candidateCount")
    stop_sequences: list[str] | None = Field(None, alias="stopSequences")
    max_output_tokens: int | None = Field(None, alias="maxOutputTokens")
    temperature: float | None = None
    top_p: float | None = Field(None, alias="topP")
    top_k: int | None = Field(None, alias="topK")
    response_mime_type: str | None = Field(None, alias="responseMimeType")
    response_schema: dict[str, Any] | None = Field(None, alias="responseSchema")


class SystemInstruction(BaseModel):
    """System instruction."""

    parts: list[Part]


# ==================== Response Related Schemas ====================


HarmProbability = Literal["HARM_PROBABILITY_UNSPECIFIED", "NEGLIGIBLE", "LOW", "MEDIUM", "HIGH"]


class SafetyRating(BaseModel):
    """Safety rating."""

    category: HarmCategory
    probability: HarmProbability
    blocked: bool | None = None


class CitationSource(BaseModel):
    """Citation source."""

    start_index: int | None = Field(None, alias="startIndex")
    end_index: int | None = Field(None, alias="endIndex")
    uri: str | None = None
    license: str | None = None


class CitationMetadata(BaseModel):
    """Citation metadata."""

    citation_sources: list[CitationSource] | None = Field(None, alias="citationSources")


class GroundingAttribution(BaseModel):
    """Grounding attribution (used for search augmentation)."""

    segment: dict[str, Any] | None = None
    confidence_score: float | None = Field(None, alias="confidenceScore")


FinishReason = Literal[
    "FINISH_REASON_UNSPECIFIED",
    "STOP",
    "MAX_TOKENS",
    "SAFETY",
    "RECITATION",
    "OTHER",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "MALFORMED_FUNCTION_CALL",
    "IMAGE_SAFETY",  # image generation safety check failed
]


class Candidate(BaseModel):
    """Candidate response."""

    content: Content | None = None
    finish_reason: FinishReason | None = Field(None, alias="finishReason")
    safety_ratings: list[SafetyRating] | None = Field(None, alias="safetyRatings")
    citation_metadata: CitationMetadata | None = Field(None, alias="citationMetadata")
    token_count: int | None = Field(None, alias="tokenCount")
    grounding_attributions: list[GroundingAttribution] | None = Field(
        None, alias="groundingAttributions"
    )
    index: int | None = None


BlockReason = Literal[
    "BLOCK_REASON_UNSPECIFIED", "SAFETY", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT"
]


class PromptFeedback(BaseModel):
    """Prompt feedback."""

    block_reason: BlockReason | None = Field(None, alias="blockReason")
    safety_ratings: list[SafetyRating] | None = Field(None, alias="safetyRatings")


class ModalityTokenCount(BaseModel):
    """Token count by modality."""

    modality: (
        Literal["MODALITY_UNSPECIFIED", "TEXT", "IMAGE", "VIDEO", "AUDIO", "DOCUMENT"] | None
    ) = None
    token_count: int | None = Field(None, alias="tokenCount")


class UsageMetadata(BaseModel):
    """Usage metadata."""

    prompt_token_count: int = Field(..., alias="promptTokenCount")
    candidates_token_count: int | None = Field(None, alias="candidatesTokenCount")
    total_token_count: int = Field(..., alias="totalTokenCount")
    cached_content_token_count: int | None = Field(None, alias="cachedContentTokenCount")
    tool_use_prompt_token_count: int | None = Field(None, alias="toolUsePromptTokenCount")
    thoughts_token_count: int | None = Field(None, alias="thoughtsTokenCount")
    prompt_tokens_details: list[ModalityTokenCount] | None = Field(
        None, alias="promptTokensDetails"
    )
    cache_tokens_details: list[ModalityTokenCount] | None = Field(None, alias="cacheTokensDetails")
    candidates_tokens_details: list[ModalityTokenCount] | None = Field(
        None, alias="candidatesTokensDetails"
    )


ModelStage = Literal["MODEL_STAGE_UNSPECIFIED", "STABLE", "LATEST"]


class ModelStatus(BaseModel):
    """Model status."""

    stage: ModelStage | None = None


class GenerateContentResponse(BaseModel):
    """GenerateContent response model.

    Used for both unary and streaming responses. In streaming, each chunk is a full
    GenerateContentResponse, but typically contains incremental content only.
    """

    candidates: list[Candidate] | None = None
    prompt_feedback: PromptFeedback | None = Field(None, alias="promptFeedback")
    usage_metadata: UsageMetadata | None = Field(None, alias="usageMetadata")
    model_version: str | None = Field(None, alias="modelVersion")
    response_id: str | None = Field(None, alias="responseId")
    model_status: ModelStatus | None = Field(None, alias="modelStatus")


# Streaming uses the same schema; keep an alias for clarity.
GeminiStreamChunk = GenerateContentResponse
