"""Google Gemini CountTokens API Pydantic schemas"""

from pydantic import BaseModel, Field


class ModalityTokenDetails(BaseModel):
    """按模态分类的 token 统计"""

    modality: str  # "text", "image", "video", "audio"
    token_count: int = Field(..., alias="tokenCount")


class CountTokensResponse(BaseModel):
    """CountTokens 响应"""

    total_tokens: int = Field(..., alias="totalTokens")
    cached_content_token_count: int | None = Field(None, alias="cachedContentTokenCount")
    prompt_tokens_details: list[ModalityTokenDetails] | None = Field(
        None, alias="promptTokensDetails"
    )
    cache_tokens_details: list[ModalityTokenDetails] | None = Field(
        None, alias="cacheTokensDetails"
    )
