"""Suite domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SpecTestCase:
    """A single test case."""

    name: str
    """Test name."""

    description: str = ""
    """Test description."""

    params: dict[str, Any] = field(default_factory=dict)
    """Test params (merged with suite baseline_params)."""

    focus_param: dict[str, Any] | None = None
    """Primary parameter to display for this test: {"name": "...", "value": ...}."""

    baseline: bool = False
    """Whether this is a baseline test (records all params)."""

    check_stream: Any = False
    """Whether runner should execute this case in streaming mode."""

    stream_expectations: dict[str, Any] | None = None
    """Streaming validation rules (e.g. required events)."""

    endpoint_override: str | None = None
    """Override the suite endpoint for this test."""

    files: dict[str, str] | None = None
    """File upload mapping: {"param_name": "file_path"}."""

    schemas: dict[str, str] | None = None
    """Test-level schema overrides."""

    required_fields: list[str] | None = None
    """List of fields that MUST be present and not None in the response."""

    method: str | None = None
    """Optional HTTP method override for this test."""

    tags: list[str] = field(default_factory=list)
    """Optional test tags for filtering (e.g. core, expensive)."""


@dataclass
class SpecTestSuite:
    """A suite loaded from a JSON5 config."""

    provider: str
    """Provider name (openai, gemini, anthropic, xai)."""

    endpoint: str
    """API endpoint path."""

    schemas: dict[str, str] = field(default_factory=dict)
    """Schema references, e.g. {"response": "openai.ChatCompletionResponse"}."""

    baseline_params: dict[str, Any] = field(default_factory=dict)
    """Default params sourced from the baseline test params."""

    tests: list[SpecTestCase] = field(default_factory=list)
    """List of test cases."""

    required_fields: list[str] = field(default_factory=list)
    """Suite-level required fields."""

    stream_expectations: dict[str, Any] | None = None
    """Suite-level stream rules (can be overridden per test)."""

    config_path: Path | None = None
    """Config file path."""

    method: str = "POST"
    """Default HTTP method for this suite."""

    suite_name: str | None = None
    """Optional human-friendly suite name."""


@dataclass
class ExecutableCase:
    """Fully-prepared executable test case.

    Unlike ``SpecTestCase`` (config semantics), this object is execution-ready:
    request params are already complete and include baseline/model/test overrides.
    """

    case_id: str
    test_name: str
    description: str
    provider: str
    route: str | None
    model: str | None
    request_method: str
    request_endpoint: str
    request_params: dict[str, Any] = field(default_factory=dict)
    request_files: dict[str, str] | None = None
    check_stream: bool = False
    response_schema: str | None = None
    stream_chunk_schema: str | None = None
    required_fields: list[str] = field(default_factory=list)
    stream_expectations: dict[str, Any] | None = None
    parameter_name: str | None = None
    parameter_value: Any = None
    parameter_value_type: str = "none"
    is_baseline: bool = False
    tags: list[str] = field(default_factory=list)
    run_case_id: str | None = None
