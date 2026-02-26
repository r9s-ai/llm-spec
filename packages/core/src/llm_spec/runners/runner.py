"""Config-driven test runner."""

from __future__ import annotations

import copy
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from pydantic import BaseModel

import json5

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.logger import RequestLogger, current_test_name
from llm_spec.path_utils import get_value_at_path
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.report_types import TestedParameter, TestExecutionResult
from llm_spec.runners.parsers import ResponseParser, StreamResponseParser
from llm_spec.runners.stream_rules import extract_observations, validate_stream
from llm_spec.validation.validator import ResponseValidator, ValidationResult

from .schema_registry import get_schema


@dataclass
class SpecTestCase:
    """A single test case."""

    name: str
    """Test name."""

    description: str = ""
    """Test description."""

    params: dict[str, Any] = field(default_factory=dict)
    """Test params (merged with suite base_params)."""

    test_param: dict[str, Any] | None = None
    """Target parameter for this test: {"name": "...", "value": ...}."""

    is_baseline: bool = False
    """Whether this is a baseline test (records all params)."""

    stream: Any = False
    """Whether this is a streaming test."""

    stream_rules: dict[str, Any] | None = None
    """Streaming validation rules (e.g. required events)."""

    override_base: bool = False
    """Whether to fully override base_params."""

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

    base_params: dict[str, Any] = field(default_factory=dict)
    """Baseline params (required params)."""

    tests: list[SpecTestCase] = field(default_factory=list)
    """List of test cases."""

    required_fields: list[str] = field(default_factory=list)
    """Suite-level required fields."""

    stream_rules: dict[str, Any] | None = None
    """Suite-level stream rules (can be overridden per test)."""

    config_path: Path | None = None
    """Config file path."""

    method: str = "POST"
    """Default HTTP method for this suite."""

    suite_name: str | None = None
    """Optional human-friendly suite name."""


class _RawTestCase(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    test_param: dict[str, Any] | None = None
    is_baseline: bool = False
    stream: Any = False
    stream_rules: dict[str, Any] | None = None
    stream_validation: dict[str, Any] | None = None
    override_base: bool = False
    endpoint_override: str | None = None
    files: dict[str, str] | None = None
    schemas: dict[str, str] | None = None
    required_fields: list[str] | None = None
    parameterize: dict[str, list[Any]] | None = None
    method: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "stream_rules" not in data and "stream_validation" in data:
            data = dict(data)
            data["stream_rules"] = data.get("stream_validation")
        return data

    @model_validator(mode="after")
    def _validate_required_non_baseline_fields(self) -> _RawTestCase:
        if self.is_baseline:
            if isinstance(self.stream, str) and not self.parameterize:
                raise ValueError(
                    f"Invalid stream value for baseline test '{self.name}': {self.stream}"
                )
            return self
        if self.test_param is None:
            raise ValueError(f"Missing 'test_param' for non-baseline test '{self.name}'")
        if "name" not in self.test_param:
            raise ValueError(f"Missing test_param.name for test '{self.name}'")
        if isinstance(self.stream, str) and not self.parameterize:
            raise ValueError(f"Invalid stream value for test '{self.name}': {self.stream}")
        return self


class _RawSuite(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    endpoint: str
    schemas: dict[str, str] = Field(default_factory=dict)
    base_params: dict[str, Any] = Field(default_factory=dict)
    tests: list[_RawTestCase] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    stream_rules: dict[str, Any] | None = None
    stream_validation: dict[str, Any] | None = None
    method: str = "POST"
    suite_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "stream_rules" not in data and "stream_validation" in data:
            data = dict(data)
            data["stream_rules"] = data.get("stream_validation")
        return data


def expand_parameterized_tests(test_config: dict[str, Any]) -> Iterator[SpecTestCase]:
    """Expand a parameterized test into multiple SpecTestCase instances.

    Config example:
        {
            "name": "test_stop_sequences",
            "parameterize": {
                "stop_value": [["END"], ["STOP", "DONE"], "###"]
            },
            "params": {"stop": "$stop_value"}
        }

    Expands to:
        test_stop_sequences[END]
        test_stop_sequences[STOP,DONE]
        test_stop_sequences[###]
    """
    parameterize = test_config.get("parameterize", {})
    if not parameterize:
        return

    # Currently only supports a single parameterized variable.
    param_name, param_values = next(iter(parameterize.items()))

    for value in param_values:
        # Build a test name suffix
        if isinstance(value, dict):
            # Dict values must have a 'suffix' field for test name generation
            if "suffix" not in value:
                raise ValueError(
                    f"Parameterized dict value must have 'suffix' field in test "
                    f"'{test_config['name']}': {value}"
                )
            suffix = str(value["suffix"]).replace("/", "_")
        elif isinstance(value, list):
            suffix = ",".join(str(v) for v in value)
        else:
            suffix = str(value)

        # Replace $param_name references inside params and test_param
        params = copy.deepcopy(test_config.get("params", {}))
        replace_parameter_references(params, param_name, value)

        test_param = copy.deepcopy(test_config.get("test_param"))
        if test_param:
            replace_parameter_references(test_param, param_name, value)

        # Build variant test name
        variant_name = f"{test_config['name']}[{suffix}]"

        # Resolve stream from parameterized value or test config
        stream = test_config.get("stream", False)
        if isinstance(value, dict) and "stream" in value:
            stream = value["stream"]

        yield SpecTestCase(
            name=variant_name,
            description=test_config.get("description", ""),
            params=params,
            test_param=test_param,
            is_baseline=test_config.get("is_baseline", False),
            stream=stream,
            stream_rules=test_config.get("stream_rules", test_config.get("stream_validation")),
            override_base=test_config.get("override_base", False),
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
                    # Extract field name (e.g., $var.field -> field)
                    field = val[len(ref_name) + 2 :]
                    if isinstance(ref_value, dict) and field in ref_value:
                        obj[key] = ref_value[field]

            # Recurse into nested structures
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

            # Recurse into nested structures
            if isinstance(obj[i], (dict, list)):
                replace_parameter_references(obj[i], ref_name, ref_value)


def load_test_suite_from_dict(
    data: dict[str, Any], config_path: Path | None = None
) -> SpecTestSuite:
    """Load a suite configuration from a dictionary.

    Args:
        data: Parsed suite configuration dictionary.
        config_path: Optional config file path for reference.

    Returns:
        Parsed SpecTestSuite
    """
    raw_suite = _RawSuite.model_validate(data)

    tests: list[SpecTestCase] = []

    for t in raw_suite.tests:
        t_dict = t.model_dump()
        # Expand parameterized tests
        if t.parameterize:
            tests.extend(expand_parameterized_tests(t_dict))
        else:
            tests.append(
                SpecTestCase(
                    name=t.name,
                    description=t.description,
                    params=t.params,
                    test_param=t.test_param,
                    is_baseline=t.is_baseline,
                    stream=t.stream if isinstance(t.stream, bool) else False,
                    stream_rules=t.stream_rules,
                    override_base=t.override_base,
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
        base_params=raw_suite.base_params,
        tests=tests,
        required_fields=raw_suite.required_fields,
        stream_rules=raw_suite.stream_rules,
        config_path=config_path,
        method=raw_suite.method,
        suite_name=raw_suite.suite_name,
    )


def load_test_suite(config_path: Path) -> SpecTestSuite:
    """Load a suite configuration file (JSON5).

    Args:
        config_path: JSON5 config file path

    Returns:
        Parsed SpecTestSuite
    """
    with open(config_path, encoding="utf-8") as f:
        raw_data = json5.load(f)

    return load_test_suite_from_dict(raw_data, config_path)


class ConfigDrivenTestRunner:
    """Config-driven test runner.

    Responsibilities:
    1. Build request params (merge base_params with test params)
    2. Execute requests (non-streaming or streaming)
    3. Validate responses (schema + stream rules)
    4. Record results into EndpointResultBuilder
    """

    def __init__(
        self,
        suite: SpecTestSuite,
        client: ProviderAdapter,
        collector: EndpointResultBuilder,
        logger: RequestLogger | None = None,
    ):
        """Initialize the runner.

        Args:
            suite: test suite
            client: provider adapter (OpenAIAdapter, GeminiAdapter, ...)
            collector: report collector
            logger: request logger
        """
        self.suite = suite
        self.client = client
        self.collector = collector
        self.logger = logger

        # Resolve schema classes
        self.response_schema: type[BaseModel] | None = get_schema(suite.schemas.get("response"))
        self.chunk_schema: type[BaseModel] | None = get_schema(suite.schemas.get("stream_chunk"))

    def build_params(self, test: SpecTestCase) -> dict[str, Any]:
        """Build the final request params for a test.

        Args:
            test: test case

        Returns:
            merged request params
        """
        # If override_base is set, skip suite base_params.
        base = {} if test.override_base else copy.deepcopy(self.suite.base_params)

        test_params = copy.deepcopy(test.params)
        base.update(test_params)

        return base

    def _log_validation_error(
        self,
        test_name: str,
        result: ValidationResult,
        status_code: int,
        response_body: Any,
    ) -> None:
        """Log schema validation errors.

        Args:
            test_name: test name
            result: validation result
            status_code: HTTP status code
            response_body: response body
        """
        # Build structured error details
        error_details = {
            "test_name": test_name,
            "type": "schema_validation_error",
            "status_code": status_code,
            "error": result.error_message,
            "missing_fields": result.missing_fields,
            "expected_fields": result.expected_fields,
            "response_body": response_body,
        }

        # Emit via logger (error level)
        if self.logger:
            import json

            self.logger.logger.error(json.dumps(error_details, ensure_ascii=False))

    @staticmethod
    def _build_tested_param(test: SpecTestCase) -> TestedParameter | None:
        """Build normalized tested_param payload."""
        if not test.test_param:
            return None
        param_name = test.test_param.get("name")
        if not isinstance(param_name, str) or not param_name:
            return None
        return {"name": param_name, "value": test.test_param.get("value")}

    @staticmethod
    def _make_test_result(
        *,
        test: SpecTestCase,
        params: dict[str, Any],
        status_code: int,
        response_body: Any,
        error: str | None = None,
        missing_fields: list[str] | None = None,
        expected_fields: list[str] | None = None,
        tested_param: TestedParameter | None = None,
        request_ok: bool | None = None,
        schema_ok: bool | None = None,
        required_fields_ok: bool | None = None,
        stream_rules_ok: bool | None = None,
        missing_events: list[str] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        latency_ms: int | None = None,
    ) -> TestExecutionResult:
        """Create one stable result object used by reporting."""
        result: TestExecutionResult = {
            "test_name": test.name,
            "params": params,
            "status_code": status_code,
            "response_body": response_body,
            "error": error,
            "missing_fields": missing_fields or [],
            "expected_fields": expected_fields or [],
            "tested_param": tested_param,
            "is_baseline": test.is_baseline,
            "missing_events": missing_events or [],
        }
        if request_ok is not None:
            result["request_ok"] = request_ok
        if schema_ok is not None:
            result["schema_ok"] = schema_ok
        if required_fields_ok is not None:
            result["required_fields_ok"] = required_fields_ok
        if stream_rules_ok is not None:
            result["stream_rules_ok"] = stream_rules_ok
        if started_at is not None:
            result["started_at"] = started_at
        if finished_at is not None:
            result["finished_at"] = finished_at
        if latency_ms is not None:
            result["latency_ms"] = latency_ms
        return result

    def _build_redacted_request_headers(self) -> dict[str, Any]:
        """Build request headers with sensitive values redacted."""
        if not hasattr(self.client, "prepare_headers"):
            return {}
        headers = self.client.prepare_headers() or {}
        if not isinstance(headers, dict):
            return {}
        return {
            k: v if k.lower() != "authorization" and "key" not in k.lower() else "***"
            for k, v in headers.items()
        }

    def _log_outbound_request(
        self,
        *,
        request_id: str | None,
        endpoint: str,
        method: str,
        params: dict[str, Any],
        file_entries: list[dict[str, Any]] | None = None,
    ) -> None:
        """Log request metadata and a safe body snapshot."""
        if not self.logger or not request_id:
            return

        base_url = getattr(self.client, "get_base_url", lambda: "")() or ""
        endpoint_path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = base_url.rstrip("/") + endpoint_path
        headers = self._build_redacted_request_headers()
        body: Any = params
        if file_entries:
            body = {
                "params": params,
                "files": file_entries,
            }

        self.logger.log_request(
            request_id=request_id,
            method=method,
            url=url,
            headers=headers,
            body=body,
        )

    def _prepare_upload_files(
        self, test: SpecTestCase
    ) -> tuple[dict[str, Any] | None, list[Any], list[dict[str, Any]]]:
        """Prepare multipart files and safe file metadata for logging."""
        files: dict[str, Any] | None = None
        opened_files: list[Any] = []
        file_entries: list[dict[str, Any]] = []
        if not test.files:
            return files, opened_files, file_entries

        files = {}
        for param_name, file_path_str in test.files.items():
            path = self._resolve_test_file_path(file_path_str)
            if not path.exists():
                raise FileNotFoundError(f"Test file not found: {file_path_str}")
            f = open(path, "rb")  # noqa: SIM115
            opened_files.append(f)
            files[param_name] = (path.name, f)
            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = None
            file_entries.append(
                {
                    "field": param_name,
                    "filename": path.name,
                    "size_bytes": size_bytes,
                }
            )
        return files, opened_files, file_entries

    def _detect_registry_root(self) -> Path | None:
        """Best-effort detect suites-registry root directory."""
        # Prefer suite config path ancestry.
        if self.suite.config_path is not None:
            for parent in [self.suite.config_path.parent, *self.suite.config_path.parents]:
                if parent.name == "suites-registry":
                    return parent
                if (parent / "suites-registry").is_dir():
                    return parent / "suites-registry"

        # Fallback to current working directory ancestry.
        cwd = Path.cwd()
        if (cwd / "suites-registry").is_dir():
            return cwd / "suites-registry"
        for parent in cwd.parents:
            if parent.name == "suites-registry":
                return parent
            if (parent / "suites-registry").is_dir():
                return parent / "suites-registry"
        return None

    def _resolve_test_file_path(self, file_path_str: str) -> Path:
        """Resolve test file path according to suites-registry asset rules."""
        raw = Path(file_path_str).expanduser()
        if raw.is_absolute():
            return raw

        rel = raw
        candidates: list[Path] = []

        # 1) Relative to current config file directory.
        if self.suite.config_path is not None:
            cfg_dir = self.suite.config_path.parent
            candidates.append(cfg_dir / rel)

            # 2) Recursively walk up to registry root.
            registry_root = self._detect_registry_root()
            cur = cfg_dir
            while True:
                candidates.append(cur / rel)
                if registry_root is not None and cur == registry_root:
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent

            # 3) Relative to suites-registry root.
            if registry_root is not None:
                candidates.append(registry_root / rel)

        # DB-loaded suites may not have config_path; still try registry root.
        registry_root = self._detect_registry_root()
        if registry_root is not None:
            candidates.append(registry_root / rel)

        # Backward-compatible fallback: current working directory.
        candidates.append(Path.cwd() / rel)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return raw

    def run_test(self, test: SpecTestCase) -> bool:
        """Run a single test.

        Args:
            test: test case

        Returns:
            True if the test passes
        """
        # Full test name: provider/endpoint::test_name
        endpoint_path = (test.endpoint_override or self.suite.endpoint).lstrip("/")
        test_full_name = f"{self.suite.provider}/{endpoint_path}::{test.name}"

        # Set context
        token = current_test_name.set(test_full_name)
        try:
            endpoint = test.endpoint_override or self.suite.endpoint
            params = self.build_params(test)
            method = test.method or self.suite.method

            if test.stream:
                return self._run_stream_test(test, endpoint, params, method=method)
            else:
                # Resolve schema overrides
                response_schema = self.response_schema
                if test.schemas and "response" in test.schemas:
                    response_schema = get_schema(test.schemas["response"])

                return self._run_normal_test(test, endpoint, params, response_schema, method=method)
        finally:
            # Clear context
            current_test_name.reset(token)

    # _get_logger removed

    def _run_normal_test(
        self,
        test: SpecTestCase,
        endpoint: str,
        params: dict[str, Any],
        response_schema: type[BaseModel] | None = None,
        *,
        method: str,
    ) -> bool:
        """Run a non-streaming request test (with optional logging)."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        files, opened_files, file_entries = self._prepare_upload_files(test)
        request_id = self.logger.generate_request_id() if self.logger else None

        self._log_outbound_request(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            params=params,
            file_entries=file_entries or None,
        )

        try:
            response = self.client.request(
                endpoint=endpoint,
                params=params,
                files=files,
                method=method,
            )
        finally:
            # Ensure files are closed
            for f in opened_files:
                f.close()
        status_code = response.status_code
        # Parse response body (needed regardless of logging)
        response_body = ResponseParser.parse_response(response)

        # Log response
        if self.logger and request_id:
            self.logger.log_response(
                request_id=request_id,
                status_code=status_code,
                body=response_body,
            )

        # Validate response (schema only on HTTP success)
        http_success = 200 <= status_code < 300
        schema_valid = True
        validation_errors: list[str] = []
        schema_missing_fields: list[str] = []
        expected_fields: list[str] = []

        if response_schema and http_success:
            # HTTP success: validate schema
            # Optimization: if response_body is already a dict, validate JSON directly.
            if isinstance(response_body, dict):
                result = ResponseValidator.validate_json(response_body, response_schema)
            else:
                result = ResponseValidator.validate_response(response, response_schema)
            expected_fields = result.expected_fields

            # Log validation errors
            if not result.is_valid:
                schema_valid = False
                schema_missing_fields = list(result.missing_fields)
                validation_errors.append(result.error_message or "Schema validation failed")
                self._log_validation_error(test.name, result, status_code, response_body)

        # Check required fields (both suite-level and test-level)
        all_required_fields = list(self.suite.required_fields)
        if test.required_fields:
            all_required_fields.extend(test.required_fields)

        missing_required: list[str] = []
        if http_success and isinstance(response_body, dict):
            for field_path in all_required_fields:
                val = get_value_at_path(response_body, field_path)
                if val is None:
                    missing_required.append(field_path)
                    validation_errors.append(f"Missing required field: {field_path}")

        is_valid = schema_valid and not missing_required

        if not http_success:
            # HTTP failure: skip schema validation
            error_message = f"HTTP {status_code}: {response_body}"
            missing_fields = []
        else:
            # HTTP success
            error_message = "; ".join(validation_errors) if validation_errors else None
            missing_fields = schema_missing_fields + missing_required

        tested_param = self._build_tested_param(test)
        finished_at = datetime.now(UTC).isoformat()
        latency_ms = int((time.monotonic() - start_monotonic) * 1000)
        http_success = 200 <= status_code < 300
        schema_ok = http_success and schema_valid
        required_fields_ok = http_success and not bool(missing_fields)
        self.collector.record_result(
            self._make_test_result(
                test=test,
                params=params,
                status_code=status_code,
                response_body=response_body,
                error=error_message,
                missing_fields=missing_fields,
                expected_fields=expected_fields,
                tested_param=tested_param,
                request_ok=http_success,
                schema_ok=schema_ok,
                required_fields_ok=required_fields_ok,
                stream_rules_ok=True,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
            )
        )

        return http_success and is_valid

    # _format_stream_response removed (moved to StreamParser.format_stream_response)

    def _run_stream_test(
        self, test: SpecTestCase, endpoint: str, params: dict[str, Any], *, method: str
    ) -> bool:
        """Run a streaming request test (this layer collects chunks and logs)."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        finished_timing: tuple[str, int] | None = None

        def _finish_timing() -> tuple[str, int]:
            nonlocal finished_timing
            if finished_timing is None:
                finished_timing = (
                    datetime.now(UTC).isoformat(),
                    int((time.monotonic() - start_monotonic) * 1000),
                )
            return finished_timing

        tested_param = self._build_tested_param(test)

        # Collect the full streaming response
        all_raw_chunks: list[bytes] = []
        http_status_code = 200
        files, opened_files, file_entries = self._prepare_upload_files(test)
        request_id = self.logger.generate_request_id() if self.logger else None
        # Reuse a single parser across stages to avoid duplicate parsing.
        parser = StreamResponseParser(self.suite.provider)
        parsed_chunks: list[dict[str, Any]] = []

        self._log_outbound_request(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            params=params,
            file_entries=file_entries or None,
        )

        try:
            # Stage 1: establish connection and collect all raw chunks
            try:
                # Transport layer streams bytes; runner collects them.
                for chunk_bytes in self.client.stream(
                    endpoint=endpoint, params=params, method=method, files=files
                ):
                    all_raw_chunks.append(chunk_bytes)
                # Try to read the real status code (HTTPClient.stream sets stream_status_code).
                http_client = getattr(self.client, "http_client", None)
                status = getattr(http_client, "stream_status_code", None)
                if isinstance(status, int):
                    http_status_code = status

                # If we did not receive any chunks at all, fail early.
                if not all_raw_chunks:
                    if self.logger and request_id:
                        self.logger.log_response(
                            request_id=request_id,
                            status_code=http_status_code,
                            body={"error": "No raw chunks received"},
                        )
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage1_no_raw_chunks",
                            error_message="No raw chunks received",
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                            },
                        )
                    self.collector.record_result(
                        self._make_test_result(
                            test=test,
                            params=params,
                            status_code=http_status_code,
                            response_body=None,
                            error="No chunks received",
                            tested_param=tested_param,
                            request_ok=False,
                            schema_ok=False,
                            required_fields_ok=False,
                            stream_rules_ok=False,
                            started_at=started_at,
                            finished_at=_finish_timing()[0],
                            latency_ms=_finish_timing()[1],
                        )
                    )
                    return False
            except httpx.HTTPStatusError as e:
                # HTTP error (4xx/5xx)
                http_status_code = e.response.status_code
                error_body = ResponseParser.parse_response(e.response)
                if self.logger and request_id:
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=http_status_code,
                        body=error_body,
                    )
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage1_http_error",
                        error_message=f"HTTP {http_status_code}",
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "response_body": error_body,
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=http_status_code,
                        response_body=error_body,
                        error=f"HTTP {http_status_code}: {e.response.text}",
                        tested_param=tested_param,
                        request_ok=False,
                        schema_ok=False,
                        required_fields_ok=False,
                        stream_rules_ok=False,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False
            except Exception as e:
                # Other errors (network/timeout/etc.)
                if self.logger and request_id:
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=0,
                        body={"error": f"Connection error: {e}"},
                    )
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage1_connection_error",
                        error_message=str(e),
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=0,
                        response_body=None,
                        error=f"Connection error: {e}",
                        tested_param=tested_param,
                        request_ok=False,
                        schema_ok=False,
                        required_fields_ok=False,
                        stream_rules_ok=False,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False

            # Stage 2: log the full response (runner responsibility).
            # Convert raw SSE/stream bytes into a human-friendly JSON structure (single pass).
            if all_raw_chunks:
                try:
                    formatted_response, parsed_chunks = parser.format_stream_response(
                        all_raw_chunks
                    )
                except Exception as e:
                    error_body = {
                        "raw_chunks_count": len(all_raw_chunks),
                        "raw_size_bytes": sum(len(c) for c in all_raw_chunks),
                        "parse_error": str(e),
                    }
                    if self.logger and request_id:
                        self.logger.log_response(
                            request_id=request_id,
                            status_code=http_status_code,
                            body=error_body,
                        )
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage2_parse_error",
                            error_message=str(e),
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                                "raw_chunks_count": len(all_raw_chunks),
                            },
                        )
                    self.collector.record_result(
                        self._make_test_result(
                            test=test,
                            params=params,
                            status_code=http_status_code,
                            response_body=error_body,
                            error=f"Stream parse error: {e}",
                            tested_param=tested_param,
                            request_ok=True,
                            schema_ok=False,
                            required_fields_ok=True,
                            stream_rules_ok=False,
                            started_at=started_at,
                            finished_at=_finish_timing()[0],
                            latency_ms=_finish_timing()[1],
                        )
                    )
                    return False

                # Stage 2: if parsing produced no structured chunks, fail early.
                if not parsed_chunks:
                    error_body = {
                        "raw_chunks_count": len(all_raw_chunks),
                        "raw_size_bytes": sum(len(c) for c in all_raw_chunks),
                        "error": "No parsed chunks received",
                        "formatted": formatted_response,
                    }
                    if self.logger and request_id:
                        self.logger.log_response(
                            request_id=request_id,
                            status_code=http_status_code,
                            body=error_body,
                        )
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage2_no_parsed_chunks",
                            error_message="No parsed chunks received",
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                                "raw_chunks_count": len(all_raw_chunks),
                            },
                        )
                    self.collector.record_result(
                        self._make_test_result(
                            test=test,
                            params=params,
                            status_code=http_status_code,
                            response_body=error_body,
                            error="No chunks received",
                            tested_param=tested_param,
                            request_ok=True,
                            schema_ok=False,
                            required_fields_ok=True,
                            stream_rules_ok=False,
                            started_at=started_at,
                            finished_at=_finish_timing()[0],
                            latency_ms=_finish_timing()[1],
                        )
                    )
                    return False
                if self.logger and request_id:
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=http_status_code,
                        body=formatted_response,
                    )

            # Stage 3: validate stream chunks against schema (if configured)
            validation_errors: list[str] = []
            if self.chunk_schema and parsed_chunks:
                invalid_chunks: list[dict[str, Any]] = []
                for i, parsed in enumerate(parsed_chunks):
                    # The SSE `data: [DONE]` marker is parsed into a synthetic chunk like
                    # {"status":"completed","done":true}; it is not a real schema chunk.
                    if isinstance(parsed, dict) and parsed.get("done") is True:
                        continue
                    result = ResponseValidator.validate_json(parsed, self.chunk_schema)
                    if not result.is_valid:
                        error_message = result.error_message or "Chunk schema validation failed"
                        validation_errors.append(f"Chunk {i}: {error_message}")
                        invalid_chunks.append(
                            {
                                "chunk_index": i,
                                "error_message": error_message,
                                "chunk": parsed,
                            }
                        )
                if validation_errors and self.logger and request_id:
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage3_chunk_schema_invalid",
                        error_message="Chunk schema validation failed",
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "errors": validation_errors[:20],
                            "invalid_chunks": invalid_chunks[:5],
                            "total_errors": len(validation_errors),
                        },
                    )
                if validation_errors:
                    # Stage 3 failed: return early to avoid duplicate summary logs in stage 4.
                    content = parser.get_complete_content()
                    self.collector.record_result(
                        self._make_test_result(
                            test=test,
                            params=params,
                            status_code=http_status_code,
                            response_body={
                                "chunks_count": len(parser.all_chunks),
                                "content_length": len(content),
                                "validation_errors": validation_errors,
                                "invalid_chunks": invalid_chunks[:5],
                            },
                            error="; ".join(validation_errors),
                            tested_param=tested_param,
                            request_ok=True,
                            schema_ok=False,
                            required_fields_ok=True,
                            stream_rules_ok=True,
                            started_at=started_at,
                            finished_at=_finish_timing()[0],
                            latency_ms=_finish_timing()[1],
                        )
                    )
                    return False

            # Stage 4: validate required observations/events
            effective_stream_rules = test.stream_rules or self.suite.stream_rules
            observations = extract_observations(
                provider=self.suite.provider,
                endpoint=endpoint,
                parsed_chunks=parsed_chunks,
                raw_chunks=all_raw_chunks,
                stream_rules=effective_stream_rules,
            )
            missing_events = validate_stream(
                provider=self.suite.provider,
                endpoint=endpoint,
                observations=observations,
                stream_rules=effective_stream_rules,
            )
            if missing_events:
                validation_errors.append(
                    f"Missing required stream events: {', '.join(missing_events)}"
                )
                if self.logger and request_id:
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage4_required_events_missing",
                        error_message="Missing required stream events",
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "missing": missing_events,
                        },
                    )

            # Extract complete text content
            content = parser.get_complete_content()

            # If there are validation errors, record failure
            if validation_errors:
                if self.logger and request_id:
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_validation_failed",
                        error_message="Stream validation failed",
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "errors": validation_errors[:50],
                            "total_errors": len(validation_errors),
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=http_status_code,
                        response_body={
                            "chunks_count": len(parser.all_chunks),
                            "content_length": len(content),
                            "validation_errors": validation_errors,
                        },
                        error="; ".join(validation_errors),
                        tested_param=tested_param,
                        request_ok=True,
                        schema_ok=True,
                        required_fields_ok=True,
                        stream_rules_ok=False,
                        missing_events=missing_events,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False

            # Record success
            self.collector.record_result(
                self._make_test_result(
                    test=test,
                    params=params,
                    status_code=http_status_code,
                    response_body={
                        "chunks_count": len(parser.all_chunks),
                        "content_length": len(content),
                    },
                    error=None,
                    tested_param=tested_param,
                    request_ok=True,
                    schema_ok=True,
                    required_fields_ok=True,
                    stream_rules_ok=True,
                    started_at=started_at,
                    finished_at=_finish_timing()[0],
                    latency_ms=_finish_timing()[1],
                )
            )

            return True

        except Exception as e:
            # Fallback: unexpected error
            if self.logger and request_id:
                self.logger.log_response(
                    request_id=request_id,
                    status_code=500,
                    body={"error": f"Unexpected error: {e}"},
                )
                self.logger.log_error(
                    request_id=request_id,
                    error_type="stream_unexpected_error",
                    error_message=str(e),
                    details={
                        "provider": self.suite.provider,
                        "endpoint": endpoint,
                        "test_name": test.name,
                    },
                )
            self.collector.record_result(
                self._make_test_result(
                    test=test,
                    params=params,
                    status_code=500,
                    response_body=None,
                    error=f"Unexpected error: {e}",
                    tested_param=tested_param,
                    request_ok=False,
                    schema_ok=False,
                    required_fields_ok=False,
                    stream_rules_ok=False,
                    started_at=started_at,
                    finished_at=_finish_timing()[0],
                    latency_ms=_finish_timing()[1],
                )
            )
            return False
        finally:
            for f in opened_files:
                f.close()

    def run_all(self) -> dict[str, bool]:
        """Run all tests in the suite.

        Returns:
            Mapping of test name -> pass/fail
        """
        results = {}

        for test in self.suite.tests:
            results[test.name] = self.run_test(test)

        return results

    # ==================== Async Methods ====================

    async def run_test_async(self, test: SpecTestCase) -> bool:
        """Run a single test asynchronously.

        Args:
            test: test case

        Returns:
            True if the test passes
        """
        # Full test name: provider/endpoint::test_name
        endpoint_path = (test.endpoint_override or self.suite.endpoint).lstrip("/")
        test_full_name = f"{self.suite.provider}/{endpoint_path}::{test.name}"

        # Set context
        token = current_test_name.set(test_full_name)
        try:
            endpoint = test.endpoint_override or self.suite.endpoint
            params = self.build_params(test)
            method = test.method or self.suite.method

            if test.stream:
                return await self._run_stream_test_async(test, endpoint, params, method=method)
            else:
                # Resolve schema overrides
                response_schema = self.response_schema
                if test.schemas and "response" in test.schemas:
                    response_schema = get_schema(test.schemas["response"])

                return await self._run_normal_test_async(
                    test, endpoint, params, response_schema, method=method
                )
        finally:
            # Clear context
            current_test_name.reset(token)

    async def _run_normal_test_async(
        self,
        test: SpecTestCase,
        endpoint: str,
        params: dict[str, Any],
        response_schema: type[BaseModel] | None = None,
        *,
        method: str,
    ) -> bool:
        """Run a non-streaming request test asynchronously."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        files, opened_files, file_entries = self._prepare_upload_files(test)
        request_id = self.logger.generate_request_id() if self.logger else None

        self._log_outbound_request(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            params=params,
            file_entries=file_entries or None,
        )

        try:
            response = await self.client.request_async(
                endpoint=endpoint,
                params=params,
                files=files,
                method=method,
            )
        finally:
            # Ensure files are closed
            for f in opened_files:
                f.close()
        status_code = response.status_code
        # Parse response body (needed regardless of logging)
        response_body = ResponseParser.parse_response(response)

        # Log response
        if self.logger and request_id:
            self.logger.log_response(
                request_id=request_id,
                status_code=status_code,
                body=response_body,
            )

        # Validate response (schema only on HTTP success)
        http_success = 200 <= status_code < 300
        schema_valid = True
        validation_errors: list[str] = []
        schema_missing_fields: list[str] = []
        expected_fields: list[str] = []

        if response_schema and http_success:
            # HTTP success: validate schema
            if isinstance(response_body, dict):
                result = ResponseValidator.validate_json(response_body, response_schema)
            else:
                result = ResponseValidator.validate_response(response, response_schema)
            expected_fields = result.expected_fields

            # Log validation errors
            if not result.is_valid:
                schema_valid = False
                schema_missing_fields = list(result.missing_fields)
                validation_errors.append(result.error_message or "Schema validation failed")
                self._log_validation_error(test.name, result, status_code, response_body)

        # Check required fields (both suite-level and test-level)
        all_required_fields = list(self.suite.required_fields)
        if test.required_fields:
            all_required_fields.extend(test.required_fields)

        missing_required: list[str] = []
        if http_success and isinstance(response_body, dict):
            for field_path in all_required_fields:
                val = get_value_at_path(response_body, field_path)
                if val is None:
                    missing_required.append(field_path)
                    validation_errors.append(f"Missing required field: {field_path}")

        is_valid = schema_valid and not missing_required

        if not http_success:
            # HTTP failure: skip schema validation
            error_message = f"HTTP {status_code}: {response_body}"
            missing_fields = []
        else:
            # HTTP success
            error_message = "; ".join(validation_errors) if validation_errors else None
            missing_fields = schema_missing_fields + missing_required

        tested_param = self._build_tested_param(test)
        finished_at = datetime.now(UTC).isoformat()
        latency_ms = int((time.monotonic() - start_monotonic) * 1000)
        http_success = 200 <= status_code < 300
        schema_ok = http_success and schema_valid
        required_fields_ok = http_success and not bool(missing_fields)
        self.collector.record_result(
            self._make_test_result(
                test=test,
                params=params,
                status_code=status_code,
                response_body=response_body,
                error=error_message,
                missing_fields=missing_fields,
                expected_fields=expected_fields,
                tested_param=tested_param,
                request_ok=http_success,
                schema_ok=schema_ok,
                required_fields_ok=required_fields_ok,
                stream_rules_ok=True,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
            )
        )

        return http_success and is_valid

    async def _run_stream_test_async(
        self, test: SpecTestCase, endpoint: str, params: dict[str, Any], *, method: str
    ) -> bool:
        """Run a streaming request test asynchronously."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        finished_timing: tuple[str, int] | None = None

        def _finish_timing() -> tuple[str, int]:
            nonlocal finished_timing
            if finished_timing is None:
                finished_timing = (
                    datetime.now(UTC).isoformat(),
                    int((time.monotonic() - start_monotonic) * 1000),
                )
            return finished_timing

        tested_param = self._build_tested_param(test)

        # Collect the full streaming response
        all_raw_chunks: list[bytes] = []
        http_status_code = 200
        files, opened_files, file_entries = self._prepare_upload_files(test)
        request_id = self.logger.generate_request_id() if self.logger else None
        parser = StreamResponseParser(self.suite.provider)
        parsed_chunks: list[dict[str, Any]] = []

        self._log_outbound_request(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            params=params,
            file_entries=file_entries or None,
        )

        try:
            # Stage 1: establish connection and collect all raw chunks
            try:
                # Transport layer streams bytes; runner collects them.
                async for chunk_bytes in self.client.stream_async(
                    endpoint=endpoint, params=params, method=method, files=files
                ):
                    all_raw_chunks.append(chunk_bytes)
                # Try to read the real status code
                http_client = getattr(self.client, "http_client", None)
                status = getattr(http_client, "stream_status_code", None)
                if isinstance(status, int):
                    http_status_code = status

                # If we did not receive any chunks at all, fail early.
                if not all_raw_chunks:
                    if self.logger and request_id:
                        self.logger.log_response(
                            request_id=request_id,
                            status_code=http_status_code,
                            body={"error": "No raw chunks received"},
                        )
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage1_no_raw_chunks",
                            error_message="No raw chunks received",
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                            },
                        )
                    self.collector.record_result(
                        self._make_test_result(
                            test=test,
                            params=params,
                            status_code=http_status_code,
                            response_body=None,
                            error="No chunks received",
                            tested_param=tested_param,
                            request_ok=False,
                            schema_ok=False,
                            required_fields_ok=False,
                            stream_rules_ok=False,
                            started_at=started_at,
                            finished_at=_finish_timing()[0],
                            latency_ms=_finish_timing()[1],
                        )
                    )
                    return False
            except httpx.HTTPStatusError as e:
                # HTTP error (4xx/5xx)
                http_status_code = e.response.status_code
                error_body = ResponseParser.parse_response(e.response)
                if self.logger and request_id:
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=http_status_code,
                        body=error_body,
                    )
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage1_http_error",
                        error_message=f"HTTP {http_status_code}",
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "response_body": error_body,
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=http_status_code,
                        response_body=error_body,
                        error=f"HTTP {http_status_code}: {e.response.text}",
                        tested_param=tested_param,
                        request_ok=False,
                        schema_ok=False,
                        required_fields_ok=False,
                        stream_rules_ok=False,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False
            except Exception as e:
                # Other errors (network/timeout/etc.)
                if self.logger and request_id:
                    self.logger.log_response(
                        request_id=request_id,
                        status_code=0,
                        body={"error": f"Connection error: {e}"},
                    )
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage1_connection_error",
                        error_message=str(e),
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=0,
                        response_body=None,
                        error=f"Connection error: {e}",
                        tested_param=tested_param,
                        request_ok=False,
                        schema_ok=False,
                        required_fields_ok=False,
                        stream_rules_ok=False,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False

            # Stage 2: parse all chunks
            try:
                formatted_response, parsed_chunks = parser.format_stream_response(all_raw_chunks)
            except Exception as e:
                if self.logger and request_id:
                    self.logger.log_error(
                        request_id=request_id,
                        error_type="stream_stage2_parse_error",
                        error_message=str(e),
                        details={
                            "provider": self.suite.provider,
                            "endpoint": endpoint,
                            "test_name": test.name,
                            "raw_chunks_count": len(all_raw_chunks),
                        },
                    )
                self.collector.record_result(
                    self._make_test_result(
                        test=test,
                        params=params,
                        status_code=http_status_code,
                        response_body=None,
                        error=f"Parse error: {e}",
                        tested_param=tested_param,
                        request_ok=True,
                        schema_ok=False,
                        required_fields_ok=False,
                        stream_rules_ok=False,
                        started_at=started_at,
                        finished_at=_finish_timing()[0],
                        latency_ms=_finish_timing()[1],
                    )
                )
                return False

            # Log the aggregated stream response
            if self.logger and request_id:
                self.logger.log_response(
                    request_id=request_id,
                    status_code=http_status_code,
                    body={"chunks": parsed_chunks},
                )

            # Stage 3: validate stream rules
            stream_rules_ok = True
            stream_errors: list[str] = []
            stream_rules = test.stream_rules or self.suite.stream_rules

            if stream_rules:
                try:
                    observations = extract_observations(
                        provider=self.suite.provider,
                        endpoint=endpoint,
                        parsed_chunks=parsed_chunks,
                        raw_chunks=all_raw_chunks,
                        stream_rules=stream_rules,
                    )
                    missing_events = validate_stream(
                        provider=self.suite.provider,
                        endpoint=endpoint,
                        observations=observations,
                        stream_rules=stream_rules,
                    )
                    stream_rules_ok = len(missing_events) == 0
                    stream_errors = (
                        [f"Missing required stream events: {', '.join(missing_events)}"]
                        if missing_events
                        else []
                    )
                    if not stream_rules_ok and self.logger and request_id:
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage3_validation_error",
                            error_message="Stream rules validation failed",
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                                "errors": stream_errors,
                            },
                        )
                except Exception as e:
                    stream_rules_ok = False
                    stream_errors = [str(e)]
                    if self.logger and request_id:
                        self.logger.log_error(
                            request_id=request_id,
                            error_type="stream_stage3_exception",
                            error_message=str(e),
                            details={
                                "provider": self.suite.provider,
                                "endpoint": endpoint,
                                "test_name": test.name,
                            },
                        )

            # Build final result
            error_msg = "; ".join(stream_errors) if stream_errors else None
            self.collector.record_result(
                self._make_test_result(
                    test=test,
                    params=params,
                    status_code=http_status_code,
                    response_body={"chunks": parsed_chunks},
                    error=error_msg,
                    tested_param=tested_param,
                    request_ok=True,
                    schema_ok=True,
                    required_fields_ok=True,
                    stream_rules_ok=stream_rules_ok,
                    started_at=started_at,
                    finished_at=_finish_timing()[0],
                    latency_ms=_finish_timing()[1],
                )
            )

            return stream_rules_ok
        except Exception as e:
            # Catch-all for unexpected errors
            if self.logger and request_id:
                self.logger.log_error(
                    request_id=request_id,
                    error_type="stream_unexpected_error",
                    error_message=str(e),
                    details={
                        "provider": self.suite.provider,
                        "endpoint": endpoint,
                        "test_name": test.name,
                    },
                )
            self.collector.record_result(
                self._make_test_result(
                    test=test,
                    params=params,
                    status_code=500,
                    response_body=None,
                    error=f"Unexpected error: {e}",
                    tested_param=tested_param,
                    request_ok=False,
                    schema_ok=False,
                    required_fields_ok=False,
                    stream_rules_ok=False,
                    started_at=started_at,
                    finished_at=_finish_timing()[0],
                    latency_ms=_finish_timing()[1],
                )
            )
            return False
        finally:
            for f in opened_files:
                f.close()
