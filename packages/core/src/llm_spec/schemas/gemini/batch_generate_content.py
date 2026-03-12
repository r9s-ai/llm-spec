"""Google Gemini Batch Generate Content API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ==================== Batch Request Structures ====================


class GenerateContentRequest(BaseModel):
    """GenerateContent request (used in batch jobs)."""

    contents: list[dict[str, Any]]
    generation_config: dict[str, Any] | None = Field(None, alias="generationConfig")
    safety_settings: list[dict[str, Any]] | None = Field(None, alias="safetySettings")
    system_instruction: dict[str, Any] | None = Field(None, alias="systemInstruction")
    tools: list[dict[str, Any]] | None = None
    tool_config: dict[str, Any] | None = Field(None, alias="toolConfig")


class BatchRequestConfig(BaseModel):
    """Batch request config."""

    display_name: str | None = Field(None, alias="displayName")
    timeout: str | None = None  # RFC 3339 duration, e.g. "3600s"


class BatchCreateRequest(BaseModel):
    """Create batch job request."""

    requests: list[GenerateContentRequest]
    config: BatchRequestConfig | None = None


# ==================== Batch Response Structures ====================


class BatchStats(BaseModel):
    """Batch job stats."""

    total_request_count: int = Field(..., alias="totalRequestCount")
    processed_request_count: int = Field(..., alias="processedRequestCount")
    failed_request_count: int = Field(..., alias="failedRequestCount")


BatchJobState = Literal[
    "JOB_STATE_UNSPECIFIED",
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
]


class BatchCreateResponse(BaseModel):
    """Create batch job response."""

    name: str  # full batch resource name, e.g. "batches/0123456789"
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")  # RFC 3339 timestamp
    update_time: str = Field(..., alias="updateTime")  # RFC 3339 timestamp
    completion_time: str | None = Field(None, alias="completionTime")  # RFC 3339 timestamp
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None
    expire_time: str | None = Field(None, alias="expireTime")  # RFC 3339 timestamp


class BatchGetResponse(BaseModel):
    """Get batch job response (same shape as BatchCreateResponse)."""

    name: str
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")
    completion_time: str | None = Field(None, alias="completionTime")
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None
    expire_time: str | None = Field(None, alias="expireTime")


class BatchResult(BaseModel):
    """Single request result in a batch job."""

    request_index: int = Field(..., alias="requestIndex")
    status: dict[str, Any] | None = None  # gRPC status
    response: dict[str, Any] | None = None  # GenerateContentResponse object


class BatchListItem(BaseModel):
    """Item in a batch job list."""

    name: str
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")
    completion_time: str | None = Field(None, alias="completionTime")
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None


class BatchListResponse(BaseModel):
    """List batch jobs response."""

    batches: list[BatchListItem]
    next_page_token: str | None = Field(None, alias="nextPageToken")


class BatchCancelRequest(BaseModel):
    """Cancel batch job request."""

    pass


class BatchCancelResponse(BaseModel):
    """Cancel batch job response."""

    name: str
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")
    completion_time: str | None = Field(None, alias="completionTime")
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None
    expire_time: str | None = Field(None, alias="expireTime")


# ==================== Batch Results Retrieval ====================


class BatchResultsResponse(BaseModel):
    """Get batch job results response."""

    results: list[BatchResult]
