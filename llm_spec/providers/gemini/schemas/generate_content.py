"""Google Gemini generateContent API schema definitions.

API Reference: https://ai.google.dev/api/rest/v1beta/models/generateContent
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class TextPart(BaseModel):
    """Text part of content."""

    text: str = Field(..., description="Text content")


class InlineDataPart(BaseModel):
    """Inline data (e.g., image) part."""

    inline_data: dict[str, str] = Field(..., description="mime_type and data")


class Content(BaseModel):
    """Content with parts and role."""

    parts: list[TextPart | InlineDataPart | dict[str, Any]] = Field(
        ..., description="Content parts"
    )
    role: Literal["user", "model"] | None = Field(default=None, description="Role")


class GenerationConfig(BaseModel):
    """Generation configuration."""

    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None)
    stop_sequences: list[str] | None = Field(default=None)
    candidate_count: int | None = Field(default=None)
    response_mime_type: str | None = Field(default=None)
    response_schema: dict[str, Any] | None = Field(default=None)


class SafetySetting(BaseModel):
    """Safety setting configuration."""

    category: str = Field(..., description="Harm category")
    threshold: str = Field(..., description="Block threshold")


class GenerateContentRequest(BaseModel):
    """Request body for generateContent."""

    contents: list[Content] = Field(..., description="Input content")
    generation_config: GenerationConfig | None = Field(default=None)
    safety_settings: list[SafetySetting] | None = Field(default=None)
    system_instruction: Content | None = Field(default=None)
    tools: list[dict[str, Any]] | None = Field(default=None)
    tool_config: dict[str, Any] | None = Field(default=None)


# ============================================================================
# Response Models
# ============================================================================


class ResponsePart(BaseModel):
    """Part in response content."""

    text: str | None = Field(default=None, description="Text content")
    function_call: dict[str, Any] | None = Field(default=None, description="Function call")


class ResponseContent(BaseModel):
    """Content in response candidate."""

    parts: list[ResponsePart] = Field(..., description="Response parts")
    role: str = Field(..., description="Always 'model'")


class SafetyRating(BaseModel):
    """Safety rating for content."""

    category: str = Field(..., description="Harm category")
    probability: str = Field(..., description="Probability level")
    blocked: bool | None = Field(default=None)


class CitationSource(BaseModel):
    """Citation source."""

    start_index: int | None = Field(default=None)
    end_index: int | None = Field(default=None)
    uri: str | None = Field(default=None)
    license: str | None = Field(default=None)


class CitationMetadata(BaseModel):
    """Citation metadata."""

    citation_sources: list[CitationSource] = Field(default_factory=list)


class Candidate(BaseModel):
    """A response candidate."""

    content: ResponseContent = Field(..., description="Generated content")
    finish_reason: str | None = Field(default=None, description="Completion reason")
    index: int | None = Field(default=None, description="Candidate index")
    safety_ratings: list[SafetyRating] | None = Field(default=None)
    citation_metadata: CitationMetadata | None = Field(default=None)
    token_count: int | None = Field(default=None)


class PromptFeedback(BaseModel):
    """Feedback about the prompt."""

    block_reason: str | None = Field(default=None)
    safety_ratings: list[SafetyRating] | None = Field(default=None)


class UsageMetadata(BaseModel):
    """Token usage metadata."""

    prompt_token_count: int = Field(..., description="Prompt tokens")
    candidates_token_count: int | None = Field(default=None, description="Response tokens")
    total_token_count: int = Field(..., description="Total tokens")


class GenerateContentResponse(BaseModel):
    """Response body for generateContent."""

    candidates: list[Candidate] | None = Field(default=None, description="Response candidates")
    prompt_feedback: PromptFeedback | None = Field(default=None)
    usage_metadata: UsageMetadata | None = Field(default=None, description="Token usage")
    model_version: str | None = Field(default=None)
