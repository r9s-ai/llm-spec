"""Common response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Error detail structure.

    Attributes:
        code: Machine-readable error code.
        message: Human-readable error message.
    """

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response.

    Attributes:
        error: Error detail.
    """

    error: ErrorDetail
