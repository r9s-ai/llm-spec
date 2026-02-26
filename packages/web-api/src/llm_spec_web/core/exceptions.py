"""Custom exceptions for llm-spec web service."""

from __future__ import annotations


class LlmSpecError(Exception):
    """Base exception for llm-spec web.

    All custom exceptions should inherit from this class.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code for programmatic handling.
    """

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(LlmSpecError):
    """Resource not found exception.

    Raised when a requested resource does not exist.

    Attributes:
        resource: Type of the resource (e.g., "Suite", "Run").
        identifier: Resource identifier (e.g., ID, name).
    """

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="NOT_FOUND",
        )
        self.resource = resource
        self.identifier = identifier


class ValidationError(LlmSpecError):
    """Validation failed exception.

    Raised when input data fails validation rules.

    Attributes:
        message: Detailed validation error message.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR")


class DuplicateError(LlmSpecError):
    """Resource already exists exception.

    Raised when attempting to create a resource that already exists.

    Attributes:
        resource: Type of the resource (e.g., "Suite", "Provider").
        identifier: Resource identifier that caused the conflict.
    """

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            code="DUPLICATE",
        )
        self.resource = resource
        self.identifier = identifier


class ConfigurationError(LlmSpecError):
    """Configuration error exception.

    Raised when a required configuration is missing or invalid.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CONFIGURATION_ERROR")


class ExecutionError(LlmSpecError):
    """Execution error exception.

    Raised when a run execution fails.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="EXECUTION_ERROR")
