"""Config-driven test runner."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from pydantic import BaseModel

import json5

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.logger import RequestLogger, current_test_name
from llm_spec.reporting.collector import ReportCollector
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

    stream: bool = False
    """Whether this is a streaming test."""

    stream_rules: dict[str, Any] | None = None
    """Streaming validation rules (e.g. required events)."""

    override_base: bool = False
    """Whether to fully override base_params."""

    no_wrapper: bool = False
    """Whether to skip applying param_wrapper."""

    endpoint_override: str | None = None
    """Override the suite endpoint for this test."""

    files: dict[str, str] | None = None
    """File upload mapping: {"param_name": "file_path"}."""

    schemas: dict[str, str] | None = None
    """Test-level schema overrides."""

    required_fields: list[str] | None = None
    """List of fields that MUST be present and not None in the response."""


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

    param_wrapper: str | None = None
    """Optional wrapper key, e.g. Gemini "generationConfig"."""

    tests: list[SpecTestCase] = field(default_factory=list)
    """List of test cases."""

    required_fields: list[str] = field(default_factory=list)
    """Suite-level required fields."""

    stream_rules: dict[str, Any] | None = None
    """Suite-level stream rules (can be overridden per test)."""

    config_path: Path | None = None
    """Config file path."""


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
            # If it's a dict, try to find a descriptive label
            label = (
                value.get("media_type")
                or value.get("label")
                or value.get("name")
                or value.get("key")
            )
            if label:
                # Use the label, but sanitize it for any potential slashes
                suffix = str(label).replace("/", "_")
            else:
                # Fallback to a shortened string representation
                val_str = str(value)
                suffix = val_str[:20] + "..." if len(val_str) > 20 else val_str
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

        yield SpecTestCase(
            name=variant_name,
            description=test_config.get("description", ""),
            params=params,
            test_param=test_param,
            is_baseline=test_config.get("is_baseline", False),
            stream=test_config.get("stream", False),
            stream_rules=test_config.get("stream_rules", test_config.get("stream_validation")),
            override_base=test_config.get("override_base", False),
            no_wrapper=test_config.get("no_wrapper", False),
            endpoint_override=test_config.get("endpoint_override"),
            files=test_config.get("files"),
            schemas=test_config.get("schemas"),
            required_fields=test_config.get("required_fields"),
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


def load_test_suite(config_path: Path) -> SpecTestSuite:
    """Load a suite configuration file (JSON5).

    Args:
        config_path: JSON5 config file path

    Returns:
        Parsed SpecTestSuite
    """
    with open(config_path, encoding="utf-8") as f:
        data = json5.load(f)

    tests: list[SpecTestCase] = []

    for t in data.get("tests", []):
        # Validation: check for mandatory fields
        test_name = t.get("name")
        if not test_name:
            raise ValueError(f"Missing 'name' for test in suite: {config_path}")

        is_baseline = t.get("is_baseline", False)
        if not is_baseline:
            # Non-baseline tests must have params and test_param
            if "params" not in t:
                raise ValueError(
                    f"Missing 'params' for non-baseline test '{test_name}' in suite: {config_path}"
                )
            if "test_param" not in t:
                raise ValueError(
                    f"Missing 'test_param' for non-baseline test '{test_name}' in suite: {config_path}"
                )

        # Expand parameterized tests
        if "parameterize" in t:
            tests.extend(expand_parameterized_tests(t))
        else:
            tests.append(
                SpecTestCase(
                    name=test_name,
                    description=t.get("description", ""),
                    params=t.get("params", {}),
                    test_param=t.get("test_param"),
                    is_baseline=is_baseline,
                    stream=t.get("stream", False),
                    stream_rules=t.get("stream_rules", t.get("stream_validation")),
                    override_base=t.get("override_base", False),
                    no_wrapper=t.get("no_wrapper", False),
                    endpoint_override=t.get("endpoint_override"),
                    files=t.get("files"),
                    schemas=t.get("schemas"),
                    required_fields=t.get("required_fields"),
                )
            )

    return SpecTestSuite(
        provider=data["provider"],
        endpoint=data["endpoint"],
        schemas=data.get("schemas", {}),
        base_params=data.get("base_params", {}),
        param_wrapper=data.get("param_wrapper"),
        tests=tests,
        required_fields=data.get("required_fields", []),
        stream_rules=data.get("stream_rules", data.get("stream_validation")),
        config_path=config_path,
    )


def get_value_at_path(obj: dict[str, Any], path: str) -> Any:
    """Get a nested value by a dotted path.

    Args:
        obj: dict object
        path: dotted path, e.g. ``"response_format.type"``

    Returns:
        The value at the given path, or None if missing.
    """
    parts = path.split(".")
    current = obj

    for part in parts:
        # Handle array index, e.g. "tools[0]"
        match = re.match(r"(\w+)\[(\d+)\]", part)
        if match:
            key, idx = match.groups()
            if isinstance(current, dict) and key in current:
                current = current[key]
                if isinstance(current, list) and int(idx) < len(current):
                    current = current[int(idx)]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


class ConfigDrivenTestRunner:
    """Config-driven test runner.

    Responsibilities:
    1. Build request params (merge base_params with test params)
    2. Execute requests (non-streaming or streaming)
    3. Validate responses (schema + stream rules)
    4. Record results into ReportCollector
    """

    def __init__(
        self,
        suite: SpecTestSuite,
        client: ProviderAdapter,
        collector: ReportCollector,
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

        # Apply param_wrapper (e.g. Gemini generationConfig)
        if self.suite.param_wrapper and not test.no_wrapper and test_params:
            # Wrap test params into the configured container key
            wrapped = {self.suite.param_wrapper: test_params}
            base.update(wrapped)
        else:
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

            if test.stream:
                return self._run_stream_test(test, endpoint, params)
            else:
                # Resolve schema overrides
                response_schema = self.response_schema
                if test.schemas and "response" in test.schemas:
                    response_schema = get_schema(test.schemas["response"])

                return self._run_normal_test(test, endpoint, params, response_schema)
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
    ) -> bool:
        """Run a non-streaming request test (with optional logging)."""
        files = None
        opened_files = []
        request_id = self.logger.generate_request_id() if self.logger else None

        # Prepare file uploads
        if test.files:
            files = {}
            for param_name, file_path_str in test.files.items():
                path = Path(file_path_str).expanduser()
                if (
                    not path.is_absolute()
                    and not path.exists()
                    and self.suite.config_path is not None
                ):
                    rel = path
                    base = self.suite.config_path.parent
                    candidates = [
                        base / rel,
                        base.parent / rel,
                        base.parent.parent / rel,
                    ]
                    for c in candidates:
                        if c.exists():
                            path = c
                            break
                if not path.exists():
                    raise FileNotFoundError(f"Test file not found: {file_path_str}")
                # Open files early so we can close them reliably later.
                f = open(path, "rb")  # noqa: SIM115
                opened_files.append(f)
                # Simple (filename, file) tuple for now.
                files[param_name] = (path.name, f)

        # Log request
        if self.logger and request_id:
            # Build full URL
            base_url = getattr(self.client, "get_base_url", lambda: "")()
            url = base_url.rstrip("/") + endpoint
            # Get headers (redacted)
            headers = {}
            if hasattr(self.client, "prepare_headers"):
                headers = self.client.prepare_headers()
                # Redact secrets
                headers = {
                    k: v if k.lower() != "authorization" and "key" not in k.lower() else "***"
                    for k, v in headers.items()
                }

            self.logger.log_request(
                request_id=request_id,
                method="POST",
                url=url,
                headers=headers,
                body=params if not files else None,  # Don't log body when uploading files
            )

        try:
            response = self.client.request(endpoint=endpoint, params=params, files=files)
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

        if response_schema and http_success:
            # HTTP success: validate schema
            # Optimization: if response_body is already a dict, validate JSON directly.
            if isinstance(response_body, dict):
                result = ResponseValidator.validate_json(response_body, response_schema)
            else:
                result = ResponseValidator.validate_response(response, response_schema)

            # Log validation errors
            if not result.is_valid:
                schema_valid = False
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
            expected_fields = []
            missing_fields = []
        else:
            # HTTP success
            error_message = "; ".join(validation_errors) if validation_errors else None
            # For backward compatibility with record_test we need individual parts
            # but record_test takes 'error' string.
            expected_fields = []  # result.expected_fields if we had one
            missing_fields = missing_required

        # Build tested_param (if test_param is configured)
        tested_param: tuple[str, Any] | None = None
        if test.test_param:
            # New format: test_param is {"name": "param.name", "value": "..."}
            param_name = test.test_param.get("name")
            param_value = test.test_param.get("value")
            if param_name is not None:
                tested_param = (param_name, param_value)

        # Record test result (collector handles parameter support bookkeeping)
        self.collector.record_test(
            test_name=test.name,
            params=params,
            status_code=status_code,
            response_body=response_body,
            error=error_message,
            missing_fields=missing_fields,
            expected_fields=expected_fields,
            tested_param=tested_param,
            is_baseline=test.is_baseline,
        )

        return http_success and is_valid

    # _format_stream_response removed (moved to StreamParser.format_stream_response)

    def _run_stream_test(self, test: SpecTestCase, endpoint: str, params: dict[str, Any]) -> bool:
        """Run a streaming request test (this layer collects chunks and logs)."""

        # Build tested_param (if test_param is configured)
        tested_param: tuple[str, Any] | None = None
        if test.test_param:
            param_name = test.test_param.get("name")
            param_value = test.test_param.get("value")
            if param_name is not None:
                tested_param = (param_name, param_value)

        # Collect the full streaming response
        all_raw_chunks: list[bytes] = []
        http_status_code = 200
        request_id = self.logger.generate_request_id() if self.logger else None
        # Reuse a single parser across stages to avoid duplicate parsing.
        parser = StreamResponseParser(self.suite.provider)
        parsed_chunks: list[dict[str, Any]] = []

        # Log request
        if self.logger and request_id:
            base_url = getattr(self.client, "get_base_url", lambda: "")()
            url = base_url.rstrip("/") + endpoint
            headers = {}
            if hasattr(self.client, "prepare_headers"):
                headers = self.client.prepare_headers()
                headers = {
                    k: v if k.lower() != "authorization" and "key" not in k.lower() else "***"
                    for k, v in headers.items()
                }

            self.logger.log_request(
                request_id=request_id,
                method="POST",
                url=url,
                headers=headers,
                body=params,
            )

        try:
            # Stage 1: establish connection and collect all raw chunks
            try:
                # Transport layer streams bytes; runner collects them.
                for chunk_bytes in self.client.stream(endpoint=endpoint, params=params):
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
                    self.collector.record_test(
                        test_name=test.name,
                        params=params,
                        status_code=http_status_code,
                        response_body=None,
                        error="No chunks received",
                        tested_param=tested_param,
                        is_baseline=test.is_baseline,
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
                self.collector.record_test(
                    test_name=test.name,
                    params=params,
                    status_code=http_status_code,
                    response_body=error_body,
                    error=f"HTTP {http_status_code}: {e.response.text}",
                    tested_param=tested_param,
                    is_baseline=test.is_baseline,
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
                self.collector.record_test(
                    test_name=test.name,
                    params=params,
                    status_code=0,
                    response_body=None,
                    error=f"Connection error: {e}",
                    tested_param=tested_param,
                    is_baseline=test.is_baseline,
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
                    self.collector.record_test(
                        test_name=test.name,
                        params=params,
                        status_code=http_status_code,
                        response_body=error_body,
                        error=f"Stream parse error: {e}",
                        tested_param=tested_param,
                        is_baseline=test.is_baseline,
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
                    self.collector.record_test(
                        test_name=test.name,
                        params=params,
                        status_code=http_status_code,
                        response_body=error_body,
                        error="No chunks received",
                        tested_param=tested_param,
                        is_baseline=test.is_baseline,
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
                    self.collector.record_test(
                        test_name=test.name,
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
                        is_baseline=test.is_baseline,
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
                self.collector.record_test(
                    test_name=test.name,
                    params=params,
                    status_code=http_status_code,
                    response_body={
                        "chunks_count": len(parser.all_chunks),
                        "content_length": len(content),
                        "validation_errors": validation_errors,
                    },
                    error="; ".join(validation_errors),
                    tested_param=tested_param,
                    is_baseline=test.is_baseline,
                )
                return False

            # Record success
            self.collector.record_test(
                test_name=test.name,
                params=params,
                status_code=http_status_code,
                response_body={
                    "chunks_count": len(parser.all_chunks),
                    "content_length": len(content),
                },
                error=None,
                tested_param=tested_param,
                is_baseline=test.is_baseline,
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
            self.collector.record_test(
                test_name=test.name,
                params=params,
                status_code=500,
                response_body=None,
                error=f"Unexpected error: {e}",
                tested_param=tested_param,
                is_baseline=test.is_baseline,
            )
            return False

    def run_all(self) -> dict[str, bool]:
        """Run all tests in the suite.

        Returns:
            Mapping of test name -> pass/fail
        """
        results = {}

        for test in self.suite.tests:
            results[test.name] = self.run_test(test)

        return results
