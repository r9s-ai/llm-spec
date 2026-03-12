"""Suite domain types — 4-layer data model.

Layer 1: Config Specs (ProviderSpec, RouteSpec, ModelSpec, TestDef)
Layer 2: SuiteSpec (expanded provider × model × route)
Layer 3: ExecutableCase (self-contained executable test) with HttpRequest + ValidationSpec
Layer 4: Results (TestVerdict, RunResult) — see results/result_types.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Value objects ──────────────────────────────────────────


@dataclass(frozen=True)
class FocusParam:
    """Marks which parameter this test is exercising."""

    name: str
    value: Any


@dataclass(frozen=True)
class SchemaRef:
    """Schema reference names for validation."""

    response: str | None = None
    stream_chunk: str | None = None


# ── Layer 1: Config Specs ─────────────────────────────────


@dataclass(frozen=True)
class ProviderSpec:
    """Loaded from provider.toml."""

    provider_id: str
    api_family: str | None = None
    routes_from: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class TestDef:
    """A single test definition within a route."""

    name: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    focus_param: FocusParam | None = None
    baseline: bool = False
    check_stream: bool = False
    stream_rules: dict[str, Any] | None = None
    endpoint_override: str | None = None
    files: dict[str, str] | None = None
    schemas: SchemaRef | None = None
    required_fields: list[str] | None = None
    method: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class RouteSpec:
    """Loaded from routes/*.json5."""

    route_id: str
    endpoint: str
    method: str = "POST"
    schemas: SchemaRef = field(default_factory=SchemaRef)
    required_fields: list[str] = field(default_factory=list)
    stream_rules: dict[str, Any] | None = None
    tests: list[TestDef] = field(default_factory=list)
    suite_label: str | None = None
    source_path: Path | None = None


@dataclass
class ModelSpec:
    """Loaded from models/*.toml."""

    model_id: str
    routes: list[str] = field(default_factory=list)
    include_tests: list[str] | None = None
    exclude_tests: list[str] | None = None
    baseline_params_override: dict[str, Any] = field(default_factory=dict)


# ── Layer 2: SuiteSpec ────────────────────────────────────


@dataclass
class SuiteSpec:
    """Expanded (provider, model, route) test suite — cached by web-api."""

    suite_id: str
    suite_name: str  # "openai/gpt-4o-mini/chat_completions"

    # Identity triple
    provider_id: str
    model_id: str
    route_id: str
    api_family: str

    # Request template
    endpoint: str
    method: str = "POST"
    provider_headers: dict[str, str] = field(default_factory=dict)

    # Validation defaults
    schemas: SchemaRef = field(default_factory=SchemaRef)
    required_fields: list[str] = field(default_factory=list)
    stream_rules: dict[str, Any] | None = None

    # Baseline params (model-injected)
    baseline_params: dict[str, Any] = field(default_factory=dict)

    # Expanded & filtered test definitions
    tests: list[TestDef] = field(default_factory=list)

    source_path: Path | None = None


# ── Layer 3: ExecutableCase (execution-ready) ───────────────────


@dataclass
class HttpRequest:
    """Fully resolved HTTP request description."""

    method: str
    endpoint: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] | None = None
    stream: bool = False


@dataclass
class ValidationSpec:
    """Validation rules for a test case."""

    response_schema: str | None = None
    stream_chunk_schema: str | None = None
    required_fields: list[str] = field(default_factory=list)
    stream_rules: dict[str, Any] | None = None


@dataclass
class ExecutableCase:
    """Self-contained executable test case."""

    case_id: str

    # Test identity
    test_name: str
    description: str = ""
    is_baseline: bool = False
    tags: list[str] = field(default_factory=list)

    # Focus parameter
    focus: FocusParam | None = None

    # Full request
    request: HttpRequest = field(default_factory=lambda: HttpRequest(method="POST", endpoint=""))

    # Validation rules
    checks: ValidationSpec = field(default_factory=ValidationSpec)

    # Provenance (needed for retry / adapter construction)
    provider: str = ""
    model: str | None = None
    route: str | None = None
    api_family: str = ""
