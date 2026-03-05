"""Test runner — executes TestCase objects and returns TestVerdict results."""

from __future__ import annotations

import base64
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
from llm_spec.results.result_types import FailureInfo, TestVerdict
from llm_spec.runners.parsers import ResponseParser, StreamResponseParser
from llm_spec.runners.stream_rules import extract_observations, validate_stream
from llm_spec.suites.types import TestCase
from llm_spec.validation.validator import ResponseValidator

from .schema_registry import get_schema


class TestRunner:
    """Executes TestCase objects and produces TestVerdict results.

    Responsibilities:
    1. Resolve asset placeholders in request params
    2. Execute HTTP requests (normal or streaming)
    3. Validate responses (schema + required fields + stream rules)
    4. Return TestVerdict (no reporting side effects)
    """

    def __init__(
        self,
        client: ProviderAdapter,
        source_path: Path | None = None,
    ):
        self.client = client
        self.source_path = source_path
        self._asset_bytes_cache: dict[Path, bytes] = {}

    # ── Public API ────────────────────────────────────────

    def run(self, case: TestCase) -> TestVerdict:
        """Execute a TestCase synchronously and return a TestVerdict."""
        set_test_name = getattr(self.client, "set_current_test_name", None)
        if callable(set_test_name):
            set_test_name(case.test_name)
        try:
            if case.request.stream:
                return self._run_stream(case)
            return self._run_normal(case)
        finally:
            if callable(set_test_name):
                set_test_name(None)

    async def run_async(self, case: TestCase) -> TestVerdict:
        """Execute a TestCase asynchronously and return a TestVerdict."""
        set_test_name = getattr(self.client, "set_current_test_name", None)
        if callable(set_test_name):
            set_test_name(case.test_name)
        try:
            if case.request.stream:
                return await self._run_stream_async(case)
            return await self._run_normal_async(case)
        finally:
            if callable(set_test_name):
                set_test_name(None)

    # ── Asset resolution ──────────────────────────────────

    @staticmethod
    def _strip_optional_quotes(text: str) -> str:
        s = text.strip()
        if len(s) >= 2 and (
            (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))
        ):
            return s[1:-1]
        return s

    def _read_asset_bytes(self, path_str: str) -> tuple[Path, bytes]:
        resolved = self._resolve_file_path(path_str)
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

    def _detect_registry_root(self) -> Path | None:
        if self.source_path is not None:
            for parent in [self.source_path.parent, *self.source_path.parents]:
                if parent.name == "suites-registry":
                    return parent
                if (parent / "suites-registry").is_dir():
                    return parent / "suites-registry"

        cwd = Path.cwd()
        if (cwd / "suites-registry").is_dir():
            return cwd / "suites-registry"
        for parent in cwd.parents:
            if parent.name == "suites-registry":
                return parent
            if (parent / "suites-registry").is_dir():
                return parent / "suites-registry"
        return None

    def _resolve_file_path(self, file_path_str: str) -> Path:
        raw = Path(file_path_str).expanduser()
        if raw.is_absolute():
            return raw

        rel = raw
        candidates: list[Path] = []

        if self.source_path is not None:
            cfg_dir = self.source_path.parent
            candidates.append(cfg_dir / rel)

            registry_root = self._detect_registry_root()
            cur = cfg_dir
            while True:
                candidates.append(cur / rel)
                if registry_root is not None and cur == registry_root:
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent

            if registry_root is not None:
                candidates.append(registry_root / rel)

        registry_root = self._detect_registry_root()
        if registry_root is not None:
            candidates.append(registry_root / rel)

        candidates.append(Path.cwd() / rel)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return raw

    # ── File uploads ──────────────────────────────────────

    def _prepare_upload_files(self, case: TestCase) -> tuple[dict[str, Any] | None, list[Any]]:
        if not case.request.files:
            return None, []

        files: dict[str, Any] = {}
        opened: list[Any] = []
        for param_name, file_path_str in case.request.files.items():
            path = self._resolve_file_path(file_path_str)
            if not path.exists():
                raise FileNotFoundError(f"Test file not found: {file_path_str}")
            f = open(path, "rb")  # noqa: SIM115
            opened.append(f)
            files[param_name] = (path.name, f)
        return files, opened

    # ── Verdict builder ───────────────────────────────────

    def _build_verdict(
        self,
        case: TestCase,
        *,
        http_status: int,
        schema_ok: bool | None = None,
        required_fields_ok: bool | None = None,
        stream_rules_ok: bool | None = None,
        error_message: str | None = None,
        fail_stage: str | None = None,
        fail_code: str | None = None,
        missing_fields: list[str] | None = None,
        missing_events: list[str] | None = None,
        started_at: str = "",
        finished_at: str = "",
        latency_ms: int | None = None,
    ) -> TestVerdict:
        """Build a TestVerdict from check results."""
        req_ok = 200 <= http_status < 300 if http_status else False
        schema_ok_val = schema_ok if schema_ok is not None else (error_message is None)
        required_ok_val = required_fields_ok if required_fields_ok is not None else True
        stream_ok_val = stream_rules_ok if stream_rules_ok is not None else True

        status: str = "pass"
        stage: str | None = fail_stage
        code: str | None = fail_code

        if not req_ok:
            status = "fail"
            stage = stage or "request"
            code = code or (f"HTTP_{http_status}" if http_status else "REQUEST_ERROR")
        elif not schema_ok_val:
            status = "fail"
            stage = stage or "schema"
            code = code or "SCHEMA_MISMATCH"
        elif not required_ok_val:
            status = "fail"
            stage = stage or "required_fields"
            code = code or "MISSING_FIELDS"
        elif not stream_ok_val:
            status = "fail"
            stage = stage or "stream_rules"
            code = code or "STREAM_RULES_FAILED"

        failure = None
        if status != "pass":
            failure = FailureInfo(
                stage=stage or "unknown",
                code=code,
                message=error_message or "",
                missing_fields=list(missing_fields or []),
                missing_events=list(missing_events or []),
            )

        return TestVerdict(
            case_id=case.case_id,
            test_name=case.test_name,
            focus=case.focus,
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=latency_ms,
            http_status=http_status if http_status else None,
            schema_ok=schema_ok if schema_ok is not None else (True if req_ok else None),
            required_fields_ok=required_fields_ok
            if required_fields_ok is not None
            else (True if req_ok else None),
            stream_rules_ok=stream_rules_ok,
            failure=failure,
        )

    def _error_verdict(
        self,
        case: TestCase,
        *,
        error_message: str,
        started_at: str,
        finished_at: str,
        latency_ms: int,
        http_status: int = 0,
    ) -> TestVerdict:
        """Shorthand for building an error verdict."""
        return TestVerdict(
            case_id=case.case_id,
            test_name=case.test_name,
            focus=case.focus,
            status="error",
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=latency_ms,
            http_status=http_status if http_status else None,
            failure=FailureInfo(
                stage="request",
                code="CONNECTION_ERROR" if not http_status else f"HTTP_{http_status}",
                message=error_message,
            ),
        )

    # ── Normal (non-streaming) test execution ─────────────

    def _run_normal(self, case: TestCase) -> TestVerdict:
        started_at = datetime.now(UTC).isoformat()
        start_mono = time.monotonic()

        params = self._resolve_asset_placeholders(case.request.params)
        files, opened = self._prepare_upload_files(case)

        try:
            response = self.client.request(
                endpoint=case.request.endpoint,
                params=params,
                files=files,
                method=case.request.method,
                additional_headers=case.request.headers or None,
            )
        except Exception as e:
            finished_at = datetime.now(UTC).isoformat()
            latency_ms = int((time.monotonic() - start_mono) * 1000)
            return self._error_verdict(
                case,
                error_message=f"Connection error: {e}",
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
            )
        finally:
            for f in opened:
                f.close()

        status_code = response.status_code
        response_body = ResponseParser.parse_response(response)
        http_success = 200 <= status_code < 300

        # Schema validation
        schema_valid = True
        validation_errors: list[str] = []
        schema_missing: list[str] = []

        response_schema: type[BaseModel] | None = get_schema(case.checks.response_schema)
        if response_schema and http_success:
            if isinstance(response_body, dict):
                result = ResponseValidator.validate_json(response_body, response_schema)
            else:
                result = ResponseValidator.validate_response(response, response_schema)
            if not result.is_valid:
                schema_valid = False
                schema_missing = list(result.missing_fields)
                validation_errors.append(result.error_message or "Schema validation failed")

        # Required fields check
        missing_required: list[str] = []
        if http_success and isinstance(response_body, dict):
            for field_path in case.checks.required_fields:
                val = get_value_at_path(response_body, field_path)
                if val is None:
                    missing_required.append(field_path)
                    validation_errors.append(f"Missing required field: {field_path}")

        all_missing = schema_missing + missing_required
        error_msg = None
        if not http_success:
            error_msg = f"HTTP {status_code}: {response_body}"
        elif validation_errors:
            error_msg = "; ".join(validation_errors)

        finished_at = datetime.now(UTC).isoformat()
        latency_ms = int((time.monotonic() - start_mono) * 1000)

        return self._build_verdict(
            case,
            http_status=status_code,
            schema_ok=http_success and schema_valid,
            required_fields_ok=http_success and not bool(all_missing),
            error_message=error_msg,
            missing_fields=all_missing,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=latency_ms,
        )

    async def _run_normal_async(self, case: TestCase) -> TestVerdict:
        started_at = datetime.now(UTC).isoformat()
        start_mono = time.monotonic()

        params = self._resolve_asset_placeholders(case.request.params)
        files, opened = self._prepare_upload_files(case)

        try:
            response = await self.client.request_async(
                endpoint=case.request.endpoint,
                params=params,
                files=files,
                method=case.request.method,
                additional_headers=case.request.headers or None,
            )
        except Exception as e:
            finished_at = datetime.now(UTC).isoformat()
            latency_ms = int((time.monotonic() - start_mono) * 1000)
            return self._error_verdict(
                case,
                error_message=f"Connection error: {e}",
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
            )
        finally:
            for f in opened:
                f.close()

        status_code = response.status_code
        response_body = ResponseParser.parse_response(response)
        http_success = 200 <= status_code < 300

        schema_valid = True
        validation_errors: list[str] = []
        schema_missing: list[str] = []

        response_schema: type[BaseModel] | None = get_schema(case.checks.response_schema)
        if response_schema and http_success:
            if isinstance(response_body, dict):
                result = ResponseValidator.validate_json(response_body, response_schema)
            else:
                result = ResponseValidator.validate_response(response, response_schema)
            if not result.is_valid:
                schema_valid = False
                schema_missing = list(result.missing_fields)
                validation_errors.append(result.error_message or "Schema validation failed")

        missing_required: list[str] = []
        if http_success and isinstance(response_body, dict):
            for field_path in case.checks.required_fields:
                val = get_value_at_path(response_body, field_path)
                if val is None:
                    missing_required.append(field_path)
                    validation_errors.append(f"Missing required field: {field_path}")

        all_missing = schema_missing + missing_required
        error_msg = None
        if not http_success:
            error_msg = f"HTTP {status_code}: {response_body}"
        elif validation_errors:
            error_msg = "; ".join(validation_errors)

        finished_at = datetime.now(UTC).isoformat()
        latency_ms = int((time.monotonic() - start_mono) * 1000)

        return self._build_verdict(
            case,
            http_status=status_code,
            schema_ok=http_success and schema_valid,
            required_fields_ok=http_success and not bool(all_missing),
            error_message=error_msg,
            missing_fields=all_missing,
            started_at=started_at,
            finished_at=finished_at,
            latency_ms=latency_ms,
        )

    # ── Streaming test execution ──────────────────────────

    def _run_stream(self, case: TestCase) -> TestVerdict:
        started_at = datetime.now(UTC).isoformat()
        start_mono = time.monotonic()
        finished_timing: tuple[str, int] | None = None

        def _finish() -> tuple[str, int]:
            nonlocal finished_timing
            if finished_timing is None:
                finished_timing = (
                    datetime.now(UTC).isoformat(),
                    int((time.monotonic() - start_mono) * 1000),
                )
            return finished_timing

        params = self._resolve_asset_placeholders(case.request.params)
        files, opened = self._prepare_upload_files(case)
        parser = StreamResponseParser(case.provider)
        all_raw_chunks: list[bytes] = []
        parsed_chunks: list[dict[str, Any]] = []
        http_status_code = 200

        try:
            # Stage 1: collect raw chunks
            try:
                for chunk_bytes in self.client.stream(
                    endpoint=case.request.endpoint,
                    params=params,
                    method=case.request.method,
                    files=files,
                ):
                    all_raw_chunks.append(chunk_bytes)

                http_client = getattr(self.client, "http_client", None)
                status = getattr(http_client, "stream_status_code", None)
                if isinstance(status, int):
                    http_status_code = status

                if not all_raw_chunks:
                    ft, lat = _finish()
                    return self._error_verdict(
                        case,
                        error_message="No chunks received",
                        started_at=started_at,
                        finished_at=ft,
                        latency_ms=lat,
                    )
            except httpx.HTTPStatusError as e:
                http_status_code = e.response.status_code
                ft, lat = _finish()
                return self._error_verdict(
                    case,
                    error_message=f"HTTP {http_status_code}: {e.response.text}",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                    http_status=http_status_code,
                )
            except Exception as e:
                ft, lat = _finish()
                return self._error_verdict(
                    case,
                    error_message=f"Connection error: {e}",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Stage 2: parse chunks
            try:
                _formatted, parsed_chunks = parser.format_stream_response(all_raw_chunks)
            except Exception as e:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=False,
                    stream_rules_ok=False,
                    error_message=f"Stream parse error: {e}",
                    fail_stage="schema",
                    fail_code="PARSE_ERROR",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            if not parsed_chunks:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=False,
                    stream_rules_ok=False,
                    error_message="No parsed chunks received",
                    fail_stage="schema",
                    fail_code="EMPTY_STREAM",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Stage 3: validate chunk schemas
            chunk_schema: type[BaseModel] | None = get_schema(case.checks.stream_chunk_schema)
            validation_errors: list[str] = []
            if chunk_schema and parsed_chunks:
                for i, parsed in enumerate(parsed_chunks):
                    if isinstance(parsed, dict) and parsed.get("done") is True:
                        continue
                    result = ResponseValidator.validate_json(parsed, chunk_schema)
                    if not result.is_valid:
                        err = result.error_message or "Chunk schema validation failed"
                        validation_errors.append(f"Chunk {i}: {err}")

                if validation_errors:
                    ft, lat = _finish()
                    return self._build_verdict(
                        case,
                        http_status=http_status_code,
                        schema_ok=False,
                        required_fields_ok=True,
                        stream_rules_ok=True,
                        error_message="; ".join(validation_errors),
                        fail_stage="schema",
                        fail_code="SCHEMA_MISMATCH",
                        started_at=started_at,
                        finished_at=ft,
                        latency_ms=lat,
                    )

            # Stage 4: validate stream rules
            stream_rules = case.checks.stream_rules
            missing_events: list[str] = []
            if stream_rules:
                observations = extract_observations(
                    provider=case.provider,
                    endpoint=case.request.endpoint,
                    parsed_chunks=parsed_chunks,
                    raw_chunks=all_raw_chunks,
                    stream_rules=stream_rules,
                )
                missing_events = validate_stream(
                    provider=case.provider,
                    endpoint=case.request.endpoint,
                    observations=observations,
                    stream_rules=stream_rules,
                )
                if missing_events:
                    validation_errors.append(
                        f"Missing required stream events: {', '.join(missing_events)}"
                    )

            if validation_errors:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=True,
                    required_fields_ok=True,
                    stream_rules_ok=False,
                    error_message="; ".join(validation_errors),
                    missing_events=missing_events,
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Success
            ft, lat = _finish()
            return self._build_verdict(
                case,
                http_status=http_status_code,
                schema_ok=True,
                required_fields_ok=True,
                stream_rules_ok=True,
                started_at=started_at,
                finished_at=ft,
                latency_ms=lat,
            )

        except Exception as e:
            ft, lat = _finish()
            return self._error_verdict(
                case,
                error_message=f"Unexpected error: {e}",
                started_at=started_at,
                finished_at=ft,
                latency_ms=lat,
                http_status=500,
            )
        finally:
            for f in opened:
                f.close()

    async def _run_stream_async(self, case: TestCase) -> TestVerdict:
        started_at = datetime.now(UTC).isoformat()
        start_mono = time.monotonic()
        finished_timing: tuple[str, int] | None = None

        def _finish() -> tuple[str, int]:
            nonlocal finished_timing
            if finished_timing is None:
                finished_timing = (
                    datetime.now(UTC).isoformat(),
                    int((time.monotonic() - start_mono) * 1000),
                )
            return finished_timing

        params = self._resolve_asset_placeholders(case.request.params)
        files, opened = self._prepare_upload_files(case)
        parser = StreamResponseParser(case.provider)
        all_raw_chunks: list[bytes] = []
        parsed_chunks: list[dict[str, Any]] = []
        http_status_code = 200

        try:
            # Stage 1: collect raw chunks
            try:
                async for chunk_bytes in self.client.stream_async(
                    endpoint=case.request.endpoint,
                    params=params,
                    method=case.request.method,
                    files=files,
                ):
                    all_raw_chunks.append(chunk_bytes)

                http_client = getattr(self.client, "http_client", None)
                status = getattr(http_client, "stream_status_code", None)
                if isinstance(status, int):
                    http_status_code = status

                if not all_raw_chunks:
                    ft, lat = _finish()
                    return self._error_verdict(
                        case,
                        error_message="No chunks received",
                        started_at=started_at,
                        finished_at=ft,
                        latency_ms=lat,
                    )
            except httpx.HTTPStatusError as e:
                http_status_code = e.response.status_code
                ft, lat = _finish()
                return self._error_verdict(
                    case,
                    error_message=f"HTTP {http_status_code}: {e.response.text}",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                    http_status=http_status_code,
                )
            except Exception as e:
                ft, lat = _finish()
                return self._error_verdict(
                    case,
                    error_message=f"Connection error: {e}",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Stage 2: parse chunks
            try:
                _formatted, parsed_chunks = parser.format_stream_response(all_raw_chunks)
            except Exception as e:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=False,
                    stream_rules_ok=False,
                    error_message=f"Stream parse error: {e}",
                    fail_stage="schema",
                    fail_code="PARSE_ERROR",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            if not parsed_chunks:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=False,
                    stream_rules_ok=False,
                    error_message="No parsed chunks received",
                    fail_stage="schema",
                    fail_code="EMPTY_STREAM",
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Stage 3: validate chunk schemas
            chunk_schema: type[BaseModel] | None = get_schema(case.checks.stream_chunk_schema)
            validation_errors: list[str] = []
            if chunk_schema and parsed_chunks:
                for i, parsed in enumerate(parsed_chunks):
                    if isinstance(parsed, dict) and parsed.get("done") is True:
                        continue
                    result = ResponseValidator.validate_json(parsed, chunk_schema)
                    if not result.is_valid:
                        err = result.error_message or "Chunk schema validation failed"
                        validation_errors.append(f"Chunk {i}: {err}")

                if validation_errors:
                    ft, lat = _finish()
                    return self._build_verdict(
                        case,
                        http_status=http_status_code,
                        schema_ok=False,
                        required_fields_ok=True,
                        stream_rules_ok=True,
                        error_message="; ".join(validation_errors),
                        fail_stage="schema",
                        fail_code="SCHEMA_MISMATCH",
                        started_at=started_at,
                        finished_at=ft,
                        latency_ms=lat,
                    )

            # Stage 4: validate stream rules
            stream_rules = case.checks.stream_rules
            missing_events: list[str] = []
            if stream_rules:
                observations = extract_observations(
                    provider=case.provider,
                    endpoint=case.request.endpoint,
                    parsed_chunks=parsed_chunks,
                    raw_chunks=all_raw_chunks,
                    stream_rules=stream_rules,
                )
                missing_events = validate_stream(
                    provider=case.provider,
                    endpoint=case.request.endpoint,
                    observations=observations,
                    stream_rules=stream_rules,
                )
                if missing_events:
                    validation_errors.append(
                        f"Missing required stream events: {', '.join(missing_events)}"
                    )

            if validation_errors:
                ft, lat = _finish()
                return self._build_verdict(
                    case,
                    http_status=http_status_code,
                    schema_ok=True,
                    required_fields_ok=True,
                    stream_rules_ok=False,
                    error_message="; ".join(validation_errors),
                    missing_events=missing_events,
                    started_at=started_at,
                    finished_at=ft,
                    latency_ms=lat,
                )

            # Success
            ft, lat = _finish()
            return self._build_verdict(
                case,
                http_status=http_status_code,
                schema_ok=True,
                required_fields_ok=True,
                stream_rules_ok=True,
                started_at=started_at,
                finished_at=ft,
                latency_ms=lat,
            )

        except Exception as e:
            ft, lat = _finish()
            return self._error_verdict(
                case,
                error_message=f"Unexpected error: {e}",
                started_at=started_at,
                finished_at=ft,
                latency_ms=lat,
                http_status=500,
            )
        finally:
            for f in opened:
                f.close()
