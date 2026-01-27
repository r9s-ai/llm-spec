"""OpenAI Embeddings 响应 Pydantic schemas"""

from pydantic import BaseModel, Field


class EmbeddingData(BaseModel):
    """单个嵌入向量数据"""

    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    """使用量模型"""

    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Embeddings 响应模型"""

    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage
