"""Utility functions for llm-spec web service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def now_utc() -> datetime:
    """Get current UTC datetime.

    Returns:
        datetime: Current UTC datetime with timezone info.
    """
    return datetime.now(UTC)


def new_id() -> str:
    """Generate a new UUID string.

    Returns:
        str: UUID string (36 characters).
    """
    return str(uuid.uuid4())
