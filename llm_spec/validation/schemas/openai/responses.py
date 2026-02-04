"""OpenAI Responses API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel

# ============================================================================
# Token Usage Model
# ============================================================================


class ResponseUsage(BaseModel):
    """Token usage statistics"""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_tokens_details: dict[str, Any] | None = None
    output_tokens_details: dict[str, Any] | None = None


# ============================================================================
# Non-streaming Response Model
# ============================================================================


class ResponseObject(BaseModel):
    """Response API non-streaming response model"""

    id: str
    object: Literal["response"]
    created_at: int
    model: str
    status: str | None = None
    background: bool | None = None
    completed_at: int | None = None
    error: dict[str, Any] | None = None
    output: list[dict[str, Any]]  # Flexible for polymorphic output items
    usage: ResponseUsage | None = None
    metadata: dict[str, str] | None = None
    service_tier: str | None = None
    store: bool | None = None
    # Additional fields from actual response
    billing: dict[str, Any] | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    instructions: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None
    text: dict[str, Any] | None = None
    reasoning: dict[str, Any] | None = None
    truncation: str | None = None
    previous_response_id: str | None = None
    prompt_cache_key: str | None = None
    prompt_cache_retention: str | None = None
    safety_identifier: str | None = None
    user: str | None = None
    incomplete_details: dict[str, Any] | None = None
    top_logprobs: int | None = None


# ============================================================================
# Streaming Response Model
# ============================================================================


class ResponseChunkObject(BaseModel):
    """Response API streaming chunk model"""

    id: str
    object: Literal["response.chunk"]
    created: int
    model: str
    delta: dict[str, Any] | None = None  # Incremental changes
    usage: ResponseUsage | None = None  # Only in final chunk
    metadata: dict[str, str] | None = None
    system_fingerprint: str | None = None
