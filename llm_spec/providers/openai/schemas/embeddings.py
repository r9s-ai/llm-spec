"""OpenAI Embeddings API schema definitions.

API Reference: https://platform.openai.com/docs/api-reference/embeddings
- Create Embeddings: POST /v1/embeddings
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class EmbeddingRequest(BaseModel):
    """Request body for POST /v1/embeddings.

    Creates an embedding vector representing the input text.
    """

    input: str | list[str] | list[int] | list[list[int]] = Field(
        ...,
        description="Input text to embed. String, array of strings, array of tokens, or array of token arrays. Max 8192 tokens per input, 300000 total tokens per request",
    )
    model: str = Field(
        ...,
        description="Model ID to use (e.g., 'text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002')",
    )
    encoding_format: Literal["float", "base64"] | None = Field(
        default=None, description="Format for embeddings. Default: float"
    )
    dimensions: int | None = Field(
        default=None,
        description="Number of dimensions for output embeddings. Only supported in text-embedding-3 and later models",
    )
    user: str | None = Field(default=None, description="Unique end-user identifier")


# ============================================================================
# Response Models
# ============================================================================


class EmbeddingData(BaseModel):
    """Single embedding in the response."""

    object: Literal["embedding"] = Field(
        default="embedding", description="Object type, always 'embedding'"
    )
    embedding: list[float] | str = Field(
        ...,
        description="The embedding vector (list of floats) or base64 string depending on encoding_format",
    )
    index: int = Field(..., description="Index of this embedding in the list")


class EmbeddingUsage(BaseModel):
    """Token usage for embedding request."""

    prompt_tokens: int = Field(..., description="Number of tokens in the input")
    total_tokens: int = Field(..., description="Total tokens used (same as prompt_tokens for embeddings)")


class EmbeddingResponse(BaseModel):
    """Response body for POST /v1/embeddings."""

    object: Literal["list"] = Field(default="list", description="Object type, always 'list'")
    data: list[EmbeddingData] = Field(..., description="List of embedding objects")
    model: str = Field(..., description="Model used for embedding")
    usage: EmbeddingUsage = Field(..., description="Token usage information")
