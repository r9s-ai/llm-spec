"""Report collector for accumulating test results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.json_types import JSONValue
from llm_spec.reporting.report_types import (
    ParameterSupportInfo,
    ReportData,
    SupportedParameter,
    UnsupportedParameter,
)


class ReportCollector:
    """Per-endpoint report collector."""

    def __init__(self, provider: str, endpoint: str, base_url: str):
        """Initialize the report collector.

        Args:
            provider: provider name
            endpoint: API endpoint path
            base_url: base URL
        """
        self.provider = provider
        self.endpoint = endpoint
        self.base_url = base_url
        self.test_time = datetime.now().isoformat()

        # Test summary
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

        # Parameter tracking
        self.tested_params: set[str] = set()
        self.supported_params: list[SupportedParameter] = []
        self.unsupported_params: list[UnsupportedParameter] = []

        # Response field tracking
        self.expected_fields: set[str] = set()
        self.unsupported_fields: list[dict[str, Any]] = []  # TODO: add typed schema later

        # Error tracking
        self.errors: list[dict[str, Any]] = []  # TODO: add typed schema later

        # Parameter support details (separates request status from validation status)
        self.param_support_details: list[ParameterSupportInfo] = []

    @staticmethod
    def _extract_param_paths(
        params: dict[str, Any],
        prefix: str = "",
        max_depth: int = 10,
        target_param: str = "",
    ) -> set[str]:
        """Recursively extract parameter paths (supports nested structures).

        Args:
            params: params dict
            prefix: path prefix
            max_depth: max recursion depth (prevents infinite recursion)
            target_param: if set, stop recursion at this exact path

        Returns:
            A set of parameter paths.

        Examples:
            >>> ReportCollector._extract_param_paths({"temperature": 0.7})
            {'temperature'}

            >>> ReportCollector._extract_param_paths({
            ...     "generationConfig": {"temperature": 0.7, "topP": 0.9}
            ... })
            {'generationConfig', 'generationConfig.temperature', 'generationConfig.topP'}

            >>> ReportCollector._extract_param_paths({
            ...     "messages": [{"role": "user", "content": "Hello"}]
            ... })
            {'messages', 'messages[0].role', 'messages[0].content'}
        """
        if max_depth <= 0:
            return set()

        paths = set()

        for key, value in params.items():
            # Build current path
            current_path = f"{prefix}.{key}" if prefix else key
            paths.add(current_path)

            # If target_param is specified and matched, stop expanding this branch.
            if target_param and current_path == target_param:
                continue

            # Dict: recurse
            if isinstance(value, dict) and value:  # skip empty dicts
                nested_paths = ReportCollector._extract_param_paths(
                    value, current_path, max_depth - 1, target_param
                )
                paths.update(nested_paths)

            # List: recurse into dict elements
            elif isinstance(value, list) and value:  # skip empty lists
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        nested_paths = ReportCollector._extract_param_paths(
                            item, f"{current_path}[{i}]", max_depth - 1, target_param
                        )
                        paths.update(nested_paths)

        return paths

    @staticmethod
    def _extract_toplevel_params(params: dict[str, Any]) -> set[str]:
        """Extract only top-level parameter keys.

        Args:
            params: params dict

        Returns:
            Set of top-level keys.
        """
        return set(params.keys())

    def record_test(
        self,
        test_name: str,
        params: dict[str, Any],
        status_code: int,
        response_body: JSONValue | str | None,
        error: str | None = None,
        missing_fields: list[str] | None = None,
        expected_fields: list[str] | None = None,
        tested_param: tuple[str, Any] | None = None,
        is_baseline: bool = False,
    ) -> None:
        """Record a single test result and derive parameter support information.

        Args:
            test_name: test name
            params: request params
            status_code: HTTP status code
            response_body: response body
            error: error message (if any)
            missing_fields: missing response fields
            expected_fields: expected fields extracted from schema
            tested_param: target parameter (param_name, param_value); for baseline tests, None
            is_baseline: whether this is a baseline test (records all params)
        """
        self.total_tests += 1

        # Record tested params
        if is_baseline:
            # Baseline: extract all nested param paths
            param_paths = self._extract_param_paths(params)
            self.tested_params.update(param_paths)
        elif tested_param:
            # Non-baseline: record only the explicitly tested param
            self.tested_params.add(tested_param[0])

        # Record expected fields
        if expected_fields:
            for field in expected_fields:
                self.expected_fields.add(field)

        # Determine success
        http_success = 200 <= status_code < 300
        is_success = http_success and error is None

        if is_success:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

            # Record errors
            if error or status_code >= 400:
                if 400 <= status_code < 500:
                    error_type = "http_error"
                elif 500 <= status_code < 600:
                    error_type = "server_error"
                else:
                    error_type = "validation_error"

                self.errors.append(
                    {
                        "test_name": test_name,
                        "type": error_type,
                        "status_code": status_code,
                        "error": error,
                        "response_body": response_body,
                    }
                )

        # Record missing fields
        if missing_fields:
            for field in missing_fields:
                self.unsupported_fields.append(
                    {
                        "field": field,
                        "test_name": test_name,
                        "reason": "Field missing in response",
                    }
                )

        # Parameter support details (separate request status from validation status)
        if is_baseline:
            # Baseline: process all params
            all_param_paths = self._extract_param_paths(params)
            for param_path in all_param_paths:
                param_value = self._get_nested_value(params, param_path)
                self._record_param_support(
                    param_name=param_path,
                    param_value=param_value,
                    test_name=test_name,
                    http_success=http_success,
                    status_code=status_code,
                    error=error,
                    missing_fields=missing_fields or [],
                    response_body=response_body,
                )
                # Keep legacy supported/unsupported lists for compatibility
                if http_success:
                    self.add_supported_param(param_path)
                else:
                    # Legacy format also tries to extract detailed error info
                    detail_error = self._extract_error_from_response(response_body)
                    reason = f"HTTP {status_code}"
                    if detail_error:
                        reason = f"HTTP {status_code}: {detail_error}"
                    self.add_unsupported_param(
                        param_name=param_path,
                        param_value=param_value,
                        test_name=test_name,
                        reason=reason,
                    )
        elif tested_param:
            # Normal param test: only process the target param
            param_name, param_value = tested_param
            self._record_param_support(
                param_name=param_name,
                param_value=param_value,
                test_name=test_name,
                http_success=http_success,
                status_code=status_code,
                error=error,
                missing_fields=missing_fields or [],
                response_body=response_body,
            )
            # Keep legacy supported/unsupported lists for compatibility
            if http_success:
                self.add_supported_param(param_name)
            else:
                # Legacy format also tries to extract detailed error info
                detail_error = self._extract_error_from_response(response_body)
                reason = f"HTTP {status_code}"
                if detail_error:
                    reason = f"HTTP {status_code}: {detail_error}"
                self.add_unsupported_param(
                    param_name=param_name,
                    param_value=param_value,
                    test_name=test_name,
                    reason=reason,
                )

    def _get_nested_value(self, params: dict[str, Any], path: str) -> Any:
        """Get a nested value by dotted/bracketed path.

        Args:
            params: params dict
            path: parameter path (e.g. "model" or "response_format.type")

        Returns:
            The value at path, or None if missing.
        """
        parts = path.split(".")
        current = params

        for part in parts:
            # Handle array index, e.g. "messages[0]"
            import re

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

    def add_unsupported_param(
        self, param_name: str, param_value: Any, test_name: str, reason: str
    ) -> None:
        """Add an unsupported parameter record.

        Args:
            param_name: parameter name
            param_value: parameter value
            test_name: test name
            reason: reason
        """
        self.unsupported_params.append(
            UnsupportedParameter(
                parameter=param_name,
                value=param_value,
                test_name=test_name,
                reason=reason,
            )
        )

    def add_supported_param(self, param_name: str) -> None:
        """Add a supported parameter record.

        Args:
            param_name: parameter name
        """
        # Deduplicate
        if not any(p["parameter"] == param_name for p in self.supported_params):
            self.supported_params.append(SupportedParameter(parameter=param_name))

    @staticmethod
    def _extract_variant_value(test_name: str) -> str | None:
        """Extract a parameterized variant value from a test name.

        Examples:
        - "test_param_size[512x512]" -> "512x512"
        - "test_image_media_type[image/webp]" -> "image/webp"
        - "test_baseline" -> None
        """
        import re

        match = re.search(r"\[(.*?)\]$", test_name)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_error_from_response(response_body: JSONValue | str | None) -> str | None:
        """Extract an error message from a response body.

        Args:
            response_body: response body

        Returns:
            Extracted error string, or None.
        """
        if not response_body:
            return None

        # If it's a string, try to parse JSON
        if isinstance(response_body, str):
            try:
                import json

                response_body = json.loads(response_body)
            except Exception:
                # Not JSON; return raw string
                return response_body

        # Extract common error shapes from dict
        if isinstance(response_body, dict):
            # Common shape: {"error": {"message": "..."}}
            if "error" in response_body:
                error_obj = response_body["error"]
                if isinstance(error_obj, dict):
                    # Prefer message
                    if "message" in error_obj:
                        return str(error_obj["message"])
                    # Fallback: type
                    if "type" in error_obj:
                        return str(error_obj["type"])
                elif isinstance(error_obj, str):
                    return error_obj

            # Other common fields
            for key in ["message", "error_message", "detail", "description"]:
                if key in response_body:
                    return str(response_body[key])

        return None

    def _record_param_support(
        self,
        param_name: str,
        param_value: Any,
        test_name: str,
        http_success: bool,
        status_code: int,
        error: str | None,
        missing_fields: list[str],
        response_body: JSONValue | str | None = None,
    ) -> None:
        """Record detailed parameter support (request vs validation).

        Args:
            param_name: parameter name
            param_value: parameter value
            test_name: test name
            http_success: whether the request succeeded (2xx)
            status_code: HTTP status code
            error: validation error message (if any)
            missing_fields: missing field paths
            response_body: response body (used to extract HTTP error details)
        """
        # Build request error
        if http_success:
            request_error = None
        else:
            # Extract details from response body
            detail_error = self._extract_error_from_response(response_body)

            # Base status code reason
            if 400 <= status_code < 500:
                base_error = f"HTTP {status_code}"
            elif 500 <= status_code < 600:
                base_error = f"HTTP {status_code} (Server Error)"
            else:
                base_error = f"HTTP {status_code}"

            # Append details if available
            request_error = f"{base_error}: {detail_error}" if detail_error else base_error

        # Build validation error
        validation_error = None
        if http_success and error:
            if missing_fields:
                validation_error = f"Missing fields: {', '.join(missing_fields)}"
            else:
                # Simplify error message (first line)
                validation_error = error.split("\n")[0]

        # Extract variant value
        variant_value = self._extract_variant_value(test_name)

        info = ParameterSupportInfo(
            parameter=param_name,
            request_ok=http_success,
            request_error=request_error,
            validation_ok=http_success and error is None,
            validation_error=validation_error,
            http_status_code=status_code,
            missing_fields=missing_fields,
            test_name=test_name,
            value=param_value,
            variant_value=variant_value,
        )
        self.param_support_details.append(info)

    def finalize(self, output_dir: str = "./reports") -> str:
        """Write final report files.

        Args:
            output_dir: output directory

        Returns:
            report.json path
        """
        # Directory name
        endpoint_name = self.endpoint.replace("/", "_").strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir_name = f"{self.provider}_{endpoint_name}_{timestamp}"

        # Create report directory
        report_dir = Path(output_dir) / report_dir_name
        report_dir.mkdir(parents=True, exist_ok=True)

        # Build report payload
        report: ReportData = {
            "test_time": self.test_time,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "base_url": self.base_url,
            "test_summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
            },
            "parameters": {
                "tested": sorted(self.tested_params),
                "untested": [],  # TODO: compute from spec definitions
                "supported": self.supported_params,
                "unsupported": self.unsupported_params,
            },
            "response_fields": {
                "expected": sorted(self.expected_fields),
                "unsupported": self.unsupported_fields,
            },
            "errors": self.errors,
            "parameter_support_details": self.param_support_details,
        }

        # Write JSON
        json_path = report_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Generate parameter tables
        self._generate_parameter_tables_if_available(str(report_dir), report)

        return str(json_path)

    def _generate_parameter_tables_if_available(
        self, output_dir: str, report_data: ReportData
    ) -> None:
        """Generate parameter support tables if the formatter is available.

        Args:
            output_dir: output directory
            report_data: report data
        """
        try:
            from llm_spec.reporting.formatter import ParameterTableFormatter

            # Create formatter (report-only)
            formatter = ParameterTableFormatter(report_data)

            # Markdown
            markdown_path = formatter.save_markdown(output_dir)
            print(f"Parameter table (Markdown): {markdown_path}")

            # HTML
            html_path = formatter.save_html(output_dir)
            print(f"Parameter table (HTML): {html_path}")

        except (ImportError, AttributeError, ModuleNotFoundError):
            # Formatter not available; ignore.
            pass
