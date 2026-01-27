"""Google Gemini Content 响应 Pydantic schemas"""

from typing import Literal

from pydantic import BaseModel


class Part(BaseModel):
    """内容部分"""

    text: str


class Content(BaseModel):
    """内容"""

    parts: list[Part]
    role: str


class Candidate(BaseModel):
    """候选响应"""

    content: Content
    finishReason: str | None = None
    index: int | None = None


class UsageMetadata(BaseModel):
    """使用量元数据"""

    promptTokenCount: int
    candidatesTokenCount: int | None = None
    totalTokenCount: int


class GenerateContentResponse(BaseModel):
    """Generate Content 响应模型"""

    candidates: list[Candidate]
    usageMetadata: UsageMetadata | None = None
