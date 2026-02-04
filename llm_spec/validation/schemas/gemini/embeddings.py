"""Google Gemini EmbedContent API Pydantic schemas"""

from typing import Literal

from pydantic import BaseModel, Field

# 导入 Content 类型（embedContent 使用相同的 Content 结构）
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
    """EmbedContent 请求参数"""

    content: Content
    task_type: TaskType | None = Field(None, alias="taskType")
    title: str | None = None
    output_dimensionality: int | None = Field(None, alias="outputDimensionality")


class Embedding(BaseModel):
    """嵌入向量"""

    values: list[float]


class EmbedContentResponse(BaseModel):
    """EmbedContent 响应"""

    embedding: Embedding


class BatchEmbedContentsResponse(BaseModel):
    """BatchEmbedContents 响应"""

    embeddings: list[Embedding]
