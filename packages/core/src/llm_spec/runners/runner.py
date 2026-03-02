"""Config-driven test runner."""

from __future__ import annotations

import base64
import copy
import mimetypes
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from pydantic import BaseModel

from llm_spec.adapters.base import ProviderAdapter
from llm_spec.path_utils import get_value_at_path
from llm_spec.results.result_types import CaseResult
from llm_spec.runners.parsers import ResponseParser, StreamResponseParser
from llm_spec.runners.stream_rules import extract_observations, validate_stream
from llm_spec.suites import (
    SpecTestCase,
    SpecTestSuite,
)
from llm_spec.validation.validator import ResponseValidator

from .schema_registry import get_schema


class ConfigDrivenTestRunner:
    """Config-driven test runner.

    Responsibilities:
    1. Build request params (merge baseline_params with test params)
    2. Execute requests (non-streaming or streaming)
    3. Validate responses (schema + stream rules)
    4. Return normalized case results (no reporting side effects)
    """

    def __init__(
        self,
        suite: SpecTestSuite,
        client: ProviderAdapter,
    ):
        """Initialize the runner.

        Args:
            suite: test suite
            client: provider adapter instance
        """
        self.suite = suite
        self.client = client
        self._asset_bytes_cache: dict[Path, bytes] = {}

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
        # Test params override same-name keys in suite baseline_params.
        base = copy.deepcopy(self.suite.baseline_params)

        test_params = copy.deepcopy(test.params)
        base.update(test_params)

        return self._resolve_asset_placeholders(base)

    @staticmethod
    def _strip_optional_quotes(text: str) -> str:
        s = text.strip()
        if len(s) >= 2 and (
            (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))
        ):
            return s[1:-1]
        return s

    def _read_asset_bytes(self, path_str: str) -> tuple[Path, bytes]:
        resolved = self._resolve_test_file_path(path_str)
        if not resolved.exists():
            raise FileNotFoundError(f"Asset file not found: {path_str}")
        cached = self._asset_bytes_cache.get(resolved)
        if cached is not None:
            return resolved, cached
        data = resolved.read_bytes()
        self._asset_bytes_cache[resolved] = data
        return resolved, data

    def _resolve_asset_function_string(self, text: str) -> str:
        stripped = text.strip()

        m_base64 = re.fullmatch(r"\$asset_base64\((.+)\)", stripped)
        if m_base64:
            raw_path = self._strip_optional_quotes(m_base64.group(1))
            _path, data = self._read_asset_bytes(raw_path)
            return base64.b64encode(data).decode("ascii")

        m_data_uri = re.fullmatch(r"\$asset_data_uri\((.+)\)", stripped)
        if m_data_uri:
            arg_str = m_data_uri.group(1)
            path_part, sep, mime_part = arg_str.partition(",")
            raw_path = self._strip_optional_quotes(path_part)
            resolved, data = self._read_asset_bytes(raw_path)
            mime = self._strip_optional_quotes(mime_part) if sep else ""
            if not mime:
                mime = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"

        return text

    def _resolve_asset_placeholders(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._resolve_asset_placeholders(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve_asset_placeholders(v) for v in value]
        if isinstance(value, str):
            return self._resolve_asset_function_string(value)
        return value

    @staticmethod
    def _build_tested_param(test: SpecTestCase) -> Any | None:
        """Build normalized tested_param value."""
        if not test.focus_param:
            return None
        param_name = test.focus_param.get("name")
        if not isinstance(param_name, str) or not param_name:
            return None
        return test.focus_param.get("value")

    def _make_test_result(
        self,
        *,
        test: SpecTestCase,
        params: dict[str, Any],
        status_code: int,
        response_body: Any,
        error: str | None = None,
        missing_fields: list[str] | None = None,
        expected_fields: list[str] | None = None,
        tested_param: Any | None = None,
        request_ok: bool | None = None,
        schema_ok: bool | None = None,
        required_fields_ok: bool | None = None,
        stream_rules_ok: bool | None = None,
        missing_events: list[str] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        latency_ms: int | None = None,
    ) -> CaseResult:
        """Create one stable case result object."""
        endpoint = test.endpoint_override or self.suite.endpoint
        path = endpoint.lstrip("/")
        http_status = int(status_code)
        req_ok = bool(request_ok) if request_ok is not None else (200 <= http_status < 300)
        schema_ok_value = bool(schema_ok) if schema_ok is not None else error is None
        required_ok_value = (
            bool(required_fields_ok) if required_fields_ok is not None else not bool(missing_fields)
        )
        stream_ok_value = bool(stream_rules_ok) if stream_rules_ok is not None else True

        status: str = "pass"
        fail_stage: str | None = None
        reason_code: str | None = None
        if not req_ok:
            status = "fail"
            fail_stage = "request"
            reason_code = f"HTTP_{http_status}" if http_status else "REQUEST_ERROR"
        elif not schema_ok_value:
            status = "fail"
            fail_stage = "schema"
            reason_code = "SCHEMA_INVALID"
        elif not required_ok_value:
            status = "fail"
            fail_stage = "required_fields"
            reason_code = "REQUIRED_FIELDS_MISSING"
        elif not stream_ok_value:
            status = "fail"
            fail_stage = "stream_rules"
            reason_code = "STREAM_RULES_FAILED"

        param_name = test.focus_param.get("name") if isinstance(test.focus_param, dict) else None
        model_value = params.get("model")
        return {
            "version": "case_result.v1",
            "test_id": f"{self.suite.provider}/{path}::{test.name}",
            "test_name": test.name,
            "is_baseline": test.baseline,
            "provider": self.suite.provider,
            "model": str(model_value) if isinstance(model_value, str) else None,
            "route": None,
            "endpoint": endpoint,
            "parameter": {
                "name": str(param_name) if isinstance(param_name, str) else None,
                "value": tested_param,
                "value_type": type(tested_param).__name__ if tested_param is not None else "none",
            },
            "request": {
                "method": test.method or self.suite.method,
                "endpoint": endpoint,
                "params": params,
                "ok": req_ok,
                "http_status": http_status,
                "latency_ms": latency_ms or 0,
            },
            "response": {
                "http_status": http_status,
                "body": response_body,
            },
            "validation": {
                "schema_ok": schema_ok_value,
                "required_fields_ok": required_ok_value,
                "stream_rules_ok": stream_ok_value,
                "missing_fields": list(missing_fields or []),
                "missing_events": list(missing_events or []),
            },
            "result": {
                "status": status,
                "fail_stage": fail_stage,
                "reason_code": reason_code,
                "reason": error,
            },
            "started_at": started_at or "",
            "finished_at": finished_at or "",
            "meta": {
                "expected_fields": list(expected_fields or []),
                "check_stream": bool(test.check_stream),
            },
        }

    def _prepare_upload_files(
        self, test: SpecTestCase
    ) -> tuple[dict[str, Any] | None, list[Any], list[dict[str, Any]]]:
        """Prepare multipart files and file metadata."""
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

    def run_test(self, test: SpecTestCase) -> CaseResult:
        """Run a single test.

        Args:
            test: test case

        Returns:
            Normalized case result
        """
        endpoint = test.endpoint_override or self.suite.endpoint
        params = self.build_params(test)
        method = test.method or self.suite.method

        set_test_name = getattr(self.client, "set_current_test_name", None)
        if callable(set_test_name):
            set_test_name(test.name)
        try:
            if test.check_stream:
                return self._run_stream_test(test, endpoint, params, method=method)
            # Resolve schema overrides
            response_schema = self.response_schema
            if test.schemas and "response" in test.schemas:
                response_schema = get_schema(test.schemas["response"])
            return self._run_normal_test(test, endpoint, params, response_schema, method=method)
        finally:
            if callable(set_test_name):
                set_test_name(None)

    def _run_normal_test(
        self,
        test: SpecTestCase,
        endpoint: str,
        params: dict[str, Any],
        response_schema: type[BaseModel] | None = None,
        *,
        method: str,
    ) -> CaseResult:
        """Run a non-streaming request test."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        files, opened_files, _file_entries = self._prepare_upload_files(test)

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
        # Parse response body
        response_body = ResponseParser.parse_response(response)

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
        return self._make_test_result(
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

    # _format_stream_response removed (moved to StreamParser.format_stream_response)

    def _run_stream_test(
        self, test: SpecTestCase, endpoint: str, params: dict[str, Any], *, method: str
    ) -> CaseResult:
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
        # Reuse a single parser across stages to avoid duplicate parsing.
        parser = StreamResponseParser(self.suite.provider)
        parsed_chunks: list[dict[str, Any]] = []

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
                    return self._make_test_result(
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
            except httpx.HTTPStatusError as e:
                # HTTP error (4xx/5xx)
                http_status_code = e.response.status_code
                error_body = ResponseParser.parse_response(e.response)
                return self._make_test_result(
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
            except Exception as e:
                # Other errors (network/timeout/etc.)
                return self._make_test_result(
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
                    return self._make_test_result(
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

                # Stage 2: if parsing produced no structured chunks, fail early.
                if not parsed_chunks:
                    error_body = {
                        "raw_chunks_count": len(all_raw_chunks),
                        "raw_size_bytes": sum(len(c) for c in all_raw_chunks),
                        "error": "No parsed chunks received",
                        "formatted": formatted_response,
                    }
                    return self._make_test_result(
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
                if validation_errors:
                    # Stage 3 failed: return early to avoid duplicate summary logs in stage 4.
                    content = parser.get_complete_content()
                    return self._make_test_result(
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

            # Stage 4: validate required observations/events
            effective_stream_rules = test.stream_expectations or self.suite.stream_expectations
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
            # Extract complete text content
            content = parser.get_complete_content()

            # If there are validation errors, record failure
            if validation_errors:
                return self._make_test_result(
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

            # Record success
            return self._make_test_result(
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

        except Exception as e:
            # Fallback: unexpected error
            return self._make_test_result(
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
        finally:
            for f in opened_files:
                f.close()

    def run_all(self) -> dict[str, CaseResult]:
        """Run all tests in the suite.

        Returns:
            Mapping of test name -> case result
        """
        results = {}

        for test in self.suite.tests:
            results[test.name] = self.run_test(test)

        return results

    # ==================== Async Methods ====================

    async def run_test_async(self, test: SpecTestCase) -> CaseResult:
        """Run a single test asynchronously.

        Args:
            test: test case

        Returns:
            Normalized case result
        """
        endpoint = test.endpoint_override or self.suite.endpoint
        params = self.build_params(test)
        method = test.method or self.suite.method

        set_test_name = getattr(self.client, "set_current_test_name", None)
        if callable(set_test_name):
            set_test_name(test.name)
        try:
            if test.check_stream:
                return await self._run_stream_test_async(test, endpoint, params, method=method)
            # Resolve schema overrides
            response_schema = self.response_schema
            if test.schemas and "response" in test.schemas:
                response_schema = get_schema(test.schemas["response"])
            return await self._run_normal_test_async(
                test, endpoint, params, response_schema, method=method
            )
        finally:
            if callable(set_test_name):
                set_test_name(None)

    async def _run_normal_test_async(
        self,
        test: SpecTestCase,
        endpoint: str,
        params: dict[str, Any],
        response_schema: type[BaseModel] | None = None,
        *,
        method: str,
    ) -> CaseResult:
        """Run a non-streaming request test asynchronously."""
        started_at = datetime.now(UTC).isoformat()
        start_monotonic = time.monotonic()
        files, opened_files, _file_entries = self._prepare_upload_files(test)

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
        # Parse response body
        response_body = ResponseParser.parse_response(response)

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
        return self._make_test_result(
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

    async def _run_stream_test_async(
        self, test: SpecTestCase, endpoint: str, params: dict[str, Any], *, method: str
    ) -> CaseResult:
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
        parser = StreamResponseParser(self.suite.provider)
        parsed_chunks: list[dict[str, Any]] = []

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
                    return self._make_test_result(
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
            except httpx.HTTPStatusError as e:
                # HTTP error (4xx/5xx)
                http_status_code = e.response.status_code
                error_body = ResponseParser.parse_response(e.response)
                return self._make_test_result(
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
            except Exception as e:
                # Other errors (network/timeout/etc.)
                return self._make_test_result(
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

            # Stage 2: parse all chunks
            try:
                formatted_response, parsed_chunks = parser.format_stream_response(all_raw_chunks)
            except Exception as e:
                return self._make_test_result(
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

            # Log the aggregated stream response
            # Stage 3: validate stream rules
            stream_rules_ok = True
            stream_errors: list[str] = []
            stream_rules = test.stream_expectations or self.suite.stream_expectations

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
                except Exception as e:
                    stream_rules_ok = False
                    stream_errors = [str(e)]
            # Build final result
            error_msg = "; ".join(stream_errors) if stream_errors else None
            return self._make_test_result(
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
        except Exception as e:
            # Catch-all for unexpected errors
            return self._make_test_result(
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
        finally:
            for f in opened_files:
                f.close()
