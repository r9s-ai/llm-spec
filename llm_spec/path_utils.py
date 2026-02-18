"""Shared helpers for dotted/bracketed JSON-like paths."""

from __future__ import annotations

import re
from typing import Any

_INDEXED_PART_RE = re.compile(r"^(\w+)\[(\d+)\]$")


def get_value_at_path(obj: Any, path: str | None) -> Any:
    """Get a nested value by path.

    Supports paths like:
    - ``choices[0].message.content``
    - ``generationConfig.temperature``
    """
    if not path:
        return None

    current = obj
    for part in path.split("."):
        indexed = _INDEXED_PART_RE.match(part)
        if indexed:
            key, idx_str = indexed.groups()
            if not (isinstance(current, dict) and key in current):
                return None
            current = current[key]
            if not isinstance(current, list):
                return None
            idx = int(idx_str)
            if idx >= len(current):
                return None
            current = current[idx]
            continue

        if isinstance(current, dict) and part in current:
            current = current[part]
            continue

        return None

    return current


def extract_param_paths(
    params: dict[str, Any],
    *,
    prefix: str = "",
    max_depth: int = 10,
    target_path: str = "",
) -> set[str]:
    """Recursively extract parameter paths from nested params."""
    if max_depth <= 0:
        return set()

    paths: set[str] = set()
    for key, value in params.items():
        current_path = f"{prefix}.{key}" if prefix else key
        paths.add(current_path)

        if target_path and current_path == target_path:
            continue

        if isinstance(value, dict) and value:
            paths.update(
                extract_param_paths(
                    value,
                    prefix=current_path,
                    max_depth=max_depth - 1,
                    target_path=target_path,
                )
            )
        elif isinstance(value, list) and value:
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    paths.update(
                        extract_param_paths(
                            item,
                            prefix=f"{current_path}[{i}]",
                            max_depth=max_depth - 1,
                            target_path=target_path,
                        )
                    )

    return paths
