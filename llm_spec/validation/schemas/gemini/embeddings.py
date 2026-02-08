"""Google Gemini EmbedContent API Pydantic schemas"""

from typing import Literal

from pydantic import BaseModel, Field

# Import Content type (embedContent uses the same Content structure)
from llm_spec.validation.schemas.gemini.generate_content import Content

TaskType = Literal[
    "TASK_TYPE_UNSPECIFIED",
    "RETRIEVAL_QUERY",
    "RETRIEVAL_DOCUMENT",
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
    "QUESTION_ANSWERING",
    "FACT_VERIFICATION",
    "CODE_RETRIEVAL_QUERY",
]


class EmbedContentRequest(BaseModel):
    """EmbedContent request parameters."""

    content: Content
    task_type: TaskType | None = Field(None, alias="taskType")
    title: str | None = None
    output_dimensionality: int | None = Field(None, alias="outputDimensionality")


class Embedding(BaseModel):
    """Embedding vector."""

    values: list[float]


class EmbedContentResponse(BaseModel):
    """EmbedContent response."""

    embedding: Embedding


class BatchEmbedContentsResponse(BaseModel):
    """BatchEmbedContents response."""

    embeddings: list[Embedding]
