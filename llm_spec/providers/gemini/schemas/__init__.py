"""Google Gemini API schema definitions.

This package contains Pydantic models for Google Gemini API requests and responses.

Modules:
- generate_content: generateContent API schemas
"""

from __future__ import annotations

from llm_spec.providers.gemini.schemas.generate_content import (
    Candidate,
    CitationMetadata,
    CitationSource,
    Content,
    GenerateContentRequest,
    GenerateContentResponse,
    GenerationConfig,
    InlineDataPart,
    PromptFeedback,
    ResponseContent,
    ResponsePart,
    SafetyRating,
    SafetySetting,
    TextPart,
    UsageMetadata,
)

__all__ = [
    # Request
    "GenerateContentRequest",
    "Content",
    "TextPart",
    "InlineDataPart",
    "GenerationConfig",
    "SafetySetting",
    # Response
    "GenerateContentResponse",
    "Candidate",
    "ResponseContent",
    "ResponsePart",
    "SafetyRating",
    "CitationMetadata",
    "CitationSource",
    "PromptFeedback",
    "UsageMetadata",
]
