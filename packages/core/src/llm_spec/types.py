"""Backward-compatible re-export of JSON/Headers type aliases.

Prefer importing from `llm_spec.json_types`.
"""

from __future__ import annotations

from llm_spec.json_types import Headers, JSONPrimitive, JSONValue, MutableHeaders

__all__ = ["Headers", "MutableHeaders", "JSONPrimitive", "JSONValue"]
