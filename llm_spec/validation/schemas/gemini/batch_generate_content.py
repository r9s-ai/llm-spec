"""Google Gemini Batch Generate Content API Pydantic schemas"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ==================== Batch Request Structures ====================


class GenerateContentRequest(BaseModel):
    """Generate Content 请求（用于批处理中）"""

    contents: list[dict[str, Any]]
    generation_config: dict[str, Any] | None = Field(None, alias="generationConfig")
    safety_settings: list[dict[str, Any]] | None = Field(None, alias="safetySettings")
    system_instruction: dict[str, Any] | None = Field(None, alias="systemInstruction")
    tools: list[dict[str, Any]] | None = None
    tool_config: dict[str, Any] | None = Field(None, alias="toolConfig")


class BatchRequestConfig(BaseModel):
    """批处理请求配置"""

    display_name: str | None = Field(None, alias="displayName")
    timeout: str | None = None  # RFC 3339 格式，如 "3600s"


class BatchCreateRequest(BaseModel):
    """创建批任务的请求"""

    requests: list[GenerateContentRequest]
    config: BatchRequestConfig | None = None


# ==================== Batch Response Structures ====================


class BatchStats(BaseModel):
    """批任务统计信息"""

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
    """创建批任务的响应"""

    name: str  # 批任务的完整资源名称，如 "batches/0123456789"
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")  # RFC 3339 时间戳
    update_time: str = Field(..., alias="updateTime")  # RFC 3339 时间戳
    completion_time: str | None = Field(None, alias="completionTime")  # RFC 3339 时间戳
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None
    expire_time: str | None = Field(None, alias="expireTime")  # RFC 3339 时间戳


class BatchGetResponse(BaseModel):
    """查询批任务的响应（与 BatchCreateResponse 相同）"""

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
    """批任务中单个请求的结果"""

    request_index: int = Field(..., alias="requestIndex")
    status: dict[str, Any] | None = None  # gRPC 状态信息
    response: dict[str, Any] | None = None  # GenerateContentResponse 对象


class BatchListItem(BaseModel):
    """批任务列表中的单项"""

    name: str
    display_name: str | None = Field(None, alias="displayName")
    state: BatchJobState
    create_time: str = Field(..., alias="createTime")
    update_time: str = Field(..., alias="updateTime")
    completion_time: str | None = Field(None, alias="completionTime")
    request_count: int | None = Field(None, alias="requestCount")
    stats: BatchStats | None = None


class BatchListResponse(BaseModel):
    """列出批任务的响应"""

    batches: list[BatchListItem]
    next_page_token: str | None = Field(None, alias="nextPageToken")


class BatchCancelRequest(BaseModel):
    """取消批任务的请求"""

    pass


class BatchCancelResponse(BaseModel):
    """取消批任务的响应"""

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
    """获取批任务结果的响应"""

    results: list[BatchResult]
