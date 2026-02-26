"""Global exception handlers for FastAPI application."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from llm_spec_web.core.exceptions import LlmSpecError


async def llm_spec_exception_handler(request: Request, exc: LlmSpecError) -> JSONResponse:
    """Handle LlmSpecError exceptions and return JSON response.

    Args:
        request: The FastAPI request object.
        exc: The LlmSpecError exception.

    Returns:
        JSONResponse with error details.
    """
    status_code = _get_status_code(exc)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


def _get_status_code(exc: LlmSpecError) -> int:
    """Map error codes to HTTP status codes.

    Args:
        exc: The LlmSpecError exception.

    Returns:
        HTTP status code.
    """
    status_code_map: dict[str, int] = {
        "NOT_FOUND": 404,
        "VALIDATION_ERROR": 400,
        "DUPLICATE": 409,
        "CONFIGURATION_ERROR": 500,
        "EXECUTION_ERROR": 500,
    }
    return status_code_map.get(exc.code, 500)
