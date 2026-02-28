"""Runtime context helpers."""

import contextvars

# Context variable for current test name (used to tag logs)
current_test_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "test_name", default=None
)
