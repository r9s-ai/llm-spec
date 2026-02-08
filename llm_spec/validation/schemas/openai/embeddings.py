"""OpenAI Embeddings response Pydantic schemas."""

from typing import Annotated

from pydantic import BaseModel, Field

# Allow raw float arrays or base64 strings (controlled by encoding_format)
EmbeddingValue = list[float] | Annotated[str, Field(pattern=r"^[A-Za-z0-9+/]+={0,2}$")]


class EmbeddingData(BaseModel):
    """A single embedding vector."""

    object: str = "embedding"
    index: int
    embedding: EmbeddingValue


class EmbeddingUsage(BaseModel):
    """Usage."""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Embeddings response model."""

    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage
