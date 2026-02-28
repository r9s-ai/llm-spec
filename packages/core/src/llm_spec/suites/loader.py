"""Suite loader and parameterization expansion."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import json5
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, model_validator

from .types import SpecTestCase, SpecTestSuite


class _RawTestCase(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    focus_param: dict[str, Any] | None = None
    baseline: bool = False
    check_stream: Any = False
    stream_expectations: dict[str, Any] | None = None
    endpoint_override: str | None = None
    files: dict[str, str] | None = None
    schemas: dict[str, str] | None = None
    required_fields: list[str] | None = None
    variants: dict[str, list[Any]] | None = None
    method: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_required_non_baseline_fields(self) -> _RawTestCase:
        if self.baseline:
            if isinstance(self.check_stream, str) and not self.variants:
                raise ValueError(
                    f"Invalid check_stream value for baseline test '{self.name}': {self.check_stream}"
                )
            return self
        if self.focus_param is None:
            raise ValueError(f"Missing 'focus_param' for non-baseline test '{self.name}'")
        if "name" not in self.focus_param:
            raise ValueError(f"Missing focus_param.name for test '{self.name}'")
        if isinstance(self.check_stream, str) and not self.variants:
            raise ValueError(
                f"Invalid check_stream value for test '{self.name}': {self.check_stream}"
            )
        return self


class _RawSuite(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    endpoint: str
    schemas: dict[str, str] = Field(default_factory=dict)
    tests: list[_RawTestCase] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    stream_expectations: dict[str, Any] | None = None
    method: str = "POST"
    suite_name: str | None = None

    @model_validator(mode="after")
    def _validate_baseline_exists_once(self) -> _RawSuite:
        baseline_tests = [t for t in self.tests if t.baseline]
        if len(baseline_tests) != 1:
            raise ValueError(
                f"Suite '{self.endpoint}' must contain exactly one baseline test, got {len(baseline_tests)}"
            )
        return self


def expand_parameterized_tests(test_config: dict[str, Any]) -> Iterator[SpecTestCase]:
    """Expand a variants-based test into multiple SpecTestCase instances."""
    variants = test_config.get("variants", {})
    if not variants:
        return

    # Currently only supports a single parameterized variable.
    param_name, param_values = next(iter(variants.items()))

    for value in param_values:
        if isinstance(value, dict):
            if "variant_id" not in value:
                raise ValueError(
                    f"Parameterized dict value must have 'variant_id' field in test "
                    f"'{test_config['name']}': {value}"
                )
            variant_id = value["variant_id"]
            suffix = str(variant_id).replace("/", "_")
        elif isinstance(value, list):
            suffix = ",".join(str(v) for v in value)
        else:
            suffix = str(value)

        params = copy.deepcopy(test_config.get("params", {}))
        replace_parameter_references(params, param_name, value)

        focus_param = copy.deepcopy(test_config.get("focus_param"))
        if focus_param:
            replace_parameter_references(focus_param, param_name, value)

        variant_name = f"{test_config['name']}[{suffix}]"

        check_stream = test_config.get("check_stream", False)
        if isinstance(value, dict) and "check_stream" in value:
            check_stream = value["check_stream"]

        yield SpecTestCase(
            name=variant_name,
            description=test_config.get("description", ""),
            params=params,
            focus_param=focus_param,
            baseline=test_config.get("baseline", False),
            check_stream=check_stream,
            stream_expectations=test_config.get("stream_expectations"),
            endpoint_override=test_config.get("endpoint_override"),
            files=test_config.get("files"),
            schemas=test_config.get("schemas"),
            required_fields=test_config.get("required_fields"),
            method=test_config.get("method"),
            tags=list(test_config.get("tags", []) or []),
        )


def replace_parameter_references(obj: Any, ref_name: str, ref_value: Any) -> None:
    """Recursively replace parameter references like ``$ref_name`` or ``$ref_name.field``."""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if isinstance(val, str):
                if val == f"${ref_name}":
                    obj[key] = ref_value
                elif val.startswith(f"${ref_name}."):
                    field = val[len(ref_name) + 2 :]
                    if isinstance(ref_value, dict) and field in ref_value:
                        obj[key] = ref_value[field]

            new_val = obj.get(key)
            if isinstance(new_val, (dict, list)):
                replace_parameter_references(new_val, ref_name, ref_value)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                if item == f"${ref_name}":
                    obj[i] = ref_value
                elif item.startswith(f"${ref_name}."):
                    field = item[len(ref_name) + 2 :]
                    if isinstance(ref_value, dict) and field in ref_value:
                        obj[i] = ref_value[field]

            if isinstance(obj[i], (dict, list)):
                replace_parameter_references(obj[i], ref_name, ref_value)


def load_test_suite_from_dict(
    data: dict[str, Any], config_path: Path | None = None
) -> SpecTestSuite:
    """Load a suite configuration from a dictionary."""
    raw_suite = _RawSuite.model_validate(data)

    tests: list[SpecTestCase] = []
    baseline_params: dict[str, Any] = {}

    for t in raw_suite.tests:
        t_dict = t.model_dump()
        if t.baseline:
            baseline_params = copy.deepcopy(t.params)
        if t.variants:
            tests.extend(expand_parameterized_tests(t_dict))
        else:
            tests.append(
                SpecTestCase(
                    name=t.name,
                    description=t.description,
                    params=t.params,
                    focus_param=t.focus_param,
                    baseline=t.baseline,
                    check_stream=t.check_stream if isinstance(t.check_stream, bool) else False,
                    stream_expectations=t.stream_expectations,
                    endpoint_override=t.endpoint_override,
                    files=t.files,
                    schemas=t.schemas,
                    required_fields=t.required_fields,
                    method=t.method,
                    tags=t.tags,
                )
            )

    return SpecTestSuite(
        provider=raw_suite.provider,
        endpoint=raw_suite.endpoint,
        schemas=raw_suite.schemas,
        baseline_params=baseline_params,
        tests=tests,
        required_fields=raw_suite.required_fields,
        stream_expectations=raw_suite.stream_expectations,
        config_path=config_path,
        method=raw_suite.method,
        suite_name=raw_suite.suite_name,
    )


def load_test_suite(config_path: Path) -> SpecTestSuite:
    """Load a suite configuration file (JSON5)."""
    with open(config_path, encoding="utf-8") as f:
        raw_data = json5.load(f)

    return load_test_suite_from_dict(raw_data, config_path)
