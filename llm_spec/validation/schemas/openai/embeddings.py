"""OpenAI Embeddings 响应 Pydantic schemas"""

from typing import Annotated, Union

from pydantic import BaseModel, Field


# 允许原始浮点数组或 base64 字符串（编码格式通过 encoding_format 控制）
EmbeddingValue = Union[
    list[float],
    Annotated[str, Field(pattern=r"^[A-Za-z0-9+/]+={0,2}$")],
]


class EmbeddingData(BaseModel):
    """单个嵌入向量数据"""

    object: str = "embedding"
    index: int
    embedding: EmbeddingValue


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
