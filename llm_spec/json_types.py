from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from typing import TypeAlias

JSONPrimitive: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONPrimitive | Sequence["JSONValue"] | Mapping[str, "JSONValue"]

Headers: TypeAlias = Mapping[str, str]
MutableHeaders: TypeAlias = MutableMapping[str, str]

__all__ = ["Headers", "MutableHeaders", "JSONPrimitive", "JSONValue"]
