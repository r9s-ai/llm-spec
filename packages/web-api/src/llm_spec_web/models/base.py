"""Base model and common utilities for ORM models."""

from __future__ import annotations

from llm_spec_web.core.db import Base
from llm_spec_web.core.utils import new_id, now_utc

__all__ = ["Base", "new_id", "now_utc"]
