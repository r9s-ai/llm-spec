"""Google Gemini CountTokens API Pydantic schemas"""

from pydantic import BaseModel, Field


class ModalityTokenDetails(BaseModel):
    """Token counts broken down by modality."""

    modality: str  # "text", "image", "video", "audio"
    token_count: int = Field(..., alias="tokenCount")


class CountTokensResponse(BaseModel):
    """CountTokens response."""

    total_tokens: int = Field(..., alias="totalTokens")
    cached_content_token_count: int | None = Field(None, alias="cachedContentTokenCount")
    prompt_tokens_details: list[ModalityTokenDetails] | None = Field(
        None, alias="promptTokensDetails"
    )
    cache_tokens_details: list[ModalityTokenDetails] | None = Field(
        None, alias="cacheTokensDetails"
    )
