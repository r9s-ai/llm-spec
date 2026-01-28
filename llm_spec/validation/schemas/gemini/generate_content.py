"""Google Gemini GenerateContent API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== Request Related Schemas ====================


class InlineData(BaseModel):
    """内联数据（base64编码）"""

    mime_type: str = Field(..., alias="mimeType")
    data: str


class FileData(BaseModel):
    """文件数据（File API引用）"""

    mime_type: str = Field(..., alias="mimeType")
    file_uri: str = Field(..., alias="fileUri")


class FunctionCall(BaseModel):
    """函数调用"""

    name: str
    args: dict[str, Any] | None = None


class FunctionResponse(BaseModel):
    """函数响应"""

    name: str
    response: dict[str, Any]


class ExecutableCode(BaseModel):
    """可执行代码"""

    language: Literal["PYTHON"] = "PYTHON"
    code: str


class CodeExecutionResult(BaseModel):
    """代码执行结果"""

    outcome: Literal["OUTCOME_OK", "OUTCOME_FAILED", "OUTCOME_DEADLINE_EXCEEDED"]
    output: str | None = None


class Part(BaseModel):
    """内容部分（支持多种类型）"""

    text: str | None = None
    inline_data: InlineData | None = Field(None, alias="inlineData")
    file_data: FileData | None = Field(None, alias="fileData")
    function_call: FunctionCall | None = Field(None, alias="functionCall")
    function_response: FunctionResponse | None = Field(None, alias="functionResponse")
    executable_code: ExecutableCode | None = Field(None, alias="executableCode")
    code_execution_result: CodeExecutionResult | None = Field(
        None, alias="codeExecutionResult"
    )


class Content(BaseModel):
    """内容（包含多个部分）"""

    parts: list[Part]
    role: str | None = None


class FunctionDeclaration(BaseModel):
    """函数声明"""

    name: str
    description: str
    parameters: dict[str, Any] | None = None


class CodeExecution(BaseModel):
    """代码执行工具"""

    pass


class Tool(BaseModel):
    """工具定义"""

    function_declarations: list[FunctionDeclaration] | None = Field(
        None, alias="functionDeclarations"
    )
    code_execution: CodeExecution | None = Field(None, alias="codeExecution")


class FunctionCallingConfig(BaseModel):
    """函数调用配置"""

    mode: Literal["AUTO", "ANY", "NONE"] | None = None
    allowed_function_names: list[str] | None = Field(None, alias="allowedFunctionNames")


class ToolConfig(BaseModel):
    """工具配置"""

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
    """安全设置"""

    category: HarmCategory
    threshold: HarmBlockThreshold


class GenerationConfig(BaseModel):
    """生成配置"""

    candidate_count: int | None = Field(None, alias="candidateCount")
    stop_sequences: list[str] | None = Field(None, alias="stopSequences")
    max_output_tokens: int | None = Field(None, alias="maxOutputTokens")
    temperature: float | None = None
    top_p: float | None = Field(None, alias="topP")
    top_k: int | None = Field(None, alias="topK")
    response_mime_type: str | None = Field(None, alias="responseMimeType")
    response_schema: dict[str, Any] | None = Field(None, alias="responseSchema")


class SystemInstruction(BaseModel):
    """系统指令"""

    parts: list[Part]


# ==================== Response Related Schemas ====================


HarmProbability = Literal[
    "HARM_PROBABILITY_UNSPECIFIED", "NEGLIGIBLE", "LOW", "MEDIUM", "HIGH"
]


class SafetyRating(BaseModel):
    """安全评级"""

    category: HarmCategory
    probability: HarmProbability
    blocked: bool | None = None


class CitationSource(BaseModel):
    """引用来源"""

    start_index: int | None = Field(None, alias="startIndex")
    end_index: int | None = Field(None, alias="endIndex")
    uri: str | None = None
    license: str | None = None


class CitationMetadata(BaseModel):
    """引用元数据"""

    citation_sources: list[CitationSource] | None = Field(None, alias="citationSources")


class GroundingAttribution(BaseModel):
    """接地归因（用于搜索增强）"""

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
]


class Candidate(BaseModel):
    """候选响应"""

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
    """提示词反馈"""

    block_reason: BlockReason | None = Field(None, alias="blockReason")
    safety_ratings: list[SafetyRating] | None = Field(None, alias="safetyRatings")


class UsageMetadata(BaseModel):
    """使用量元数据"""

    prompt_token_count: int = Field(..., alias="promptTokenCount")
    candidates_token_count: int | None = Field(None, alias="candidatesTokenCount")
    total_token_count: int = Field(..., alias="totalTokenCount")
    cached_content_token_count: int | None = Field(
        None, alias="cachedContentTokenCount"
    )


ModelStage = Literal["MODEL_STAGE_UNSPECIFIED", "STABLE", "LATEST"]


class ModelStatus(BaseModel):
    """模型状态"""

    stage: ModelStage | None = None


class GenerateContentResponse(BaseModel):
    """Generate Content 响应模型"""

    candidates: list[Candidate] | None = None
    prompt_feedback: PromptFeedback | None = Field(None, alias="promptFeedback")
    usage_metadata: UsageMetadata | None = Field(None, alias="usageMetadata")
    model_version: str | None = Field(None, alias="modelVersion")
    response_id: str | None = Field(None, alias="responseId")
    model_status: ModelStatus | None = Field(None, alias="modelStatus")
