from __future__ import annotations

from typing import Mapping, MutableMapping, Sequence, TypeAlias

JSONPrimitive: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = (
    JSONPrimitive
    | Sequence["JSONValue"]
    | Mapping[str, "JSONValue"]
)

Headers: TypeAlias = Mapping[str, str]
MutableHeaders: TypeAlias = MutableMapping[str, str]

