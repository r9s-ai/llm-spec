"""Validation report models for field-level validation results."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from rich.text import Text


# =============================================================================
# Global Report Collector (singleton)
# =============================================================================

_report_collector: ReportCollector | None = None


def get_collector() -> ReportCollector:
    """Get the global report collector instance."""
    global _report_collector
    if _report_collector is None:
        _report_collector = ReportCollector()
    return _report_collector


def reset_collector() -> None:
    """Reset the global report collector."""
    global _report_collector
    _report_collector = None


class FieldStatus(str, Enum):
    """Status of a validated field."""

    VALID = "valid"  # Field exists and type matches
    INVALID_TYPE = "invalid_type"  # Field exists but type mismatch
    MISSING = "missing"  # Required field is missing
    UNEXPECTED = "unexpected"  # Field not defined in schema


class FieldResult(BaseModel):
    """Result of validating a single field."""

    field: str = Field(
        ..., description="Field path, e.g., 'choices[0].message.content'"
    )
    status: FieldStatus = Field(..., description="Validation status")
    expected: str | None = Field(default=None, description="Expected type")
    actual: str | None = Field(default=None, description="Actual type or value")
    message: str | None = Field(default=None, description="Additional details")


class ValidationReport(BaseModel):
    """Complete validation report for an API response."""

    provider: str = Field(..., description="Provider name, e.g., 'openai'")
    endpoint: str = Field(..., description="API endpoint, e.g., 'chat/completions'")
    success: bool = Field(..., description="Whether all validations passed")
    total_fields: int = Field(..., description="Total number of fields checked")
    valid_count: int = Field(..., description="Number of valid fields")
    invalid_count: int = Field(..., description="Number of invalid fields")
    fields: list[FieldResult] = Field(
        default_factory=list, description="Detailed field results"
    )
    request_params: dict[str, Any] | None = Field(
        default=None, description="Request parameters used in this test"
    )
    raw_response: dict[str, Any] | None = Field(
        default=None, description="Raw API response for debugging"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Report generation timestamp",
    )

    def print(self, verbose: bool | None = None, show_valid: bool | None = None) -> None:
        """Print report to terminal with colors.

        Args:
            verbose: Override config verbose setting
            show_valid: Override config show_valid setting
        """
        from llm_spec.core.config import get_config

        config = get_config().report

        # Use config values if not overridden
        if verbose is None:
            verbose = config.verbose
        if show_valid is None:
            show_valid = config.show_valid

        console = Console()

        # Header
        status_text = (
            Text("PASSED", style="bold green")
            if self.success
            else Text("FAILED", style="bold red")
        )
        console.print()
        console.print("=" * 60)
        console.print(f"  {self.provider.upper()} /{self.endpoint} Validation Report")
        console.print("=" * 60)
        console.print("  Status: ", end="")
        console.print(status_text)

        percentage = (
            (self.valid_count / self.total_fields * 100) if self.total_fields > 0 else 0
        )
        console.print(
            f"  Fields: {self.valid_count}/{self.total_fields} valid ({percentage:.1f}%)"
        )
        console.print("-" * 60)

        # Field details table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Status", width=3)
        table.add_column("Field", style="cyan")
        table.add_column("Details")

        for field_result in self.fields:
            if field_result.status == FieldStatus.VALID:
                if not show_valid and not verbose:
                    continue
                status_icon = "[green]✓[/green]"
                details = field_result.expected or ""
            elif field_result.status == FieldStatus.INVALID_TYPE:
                status_icon = "[red]✗[/red]"
                details = f"expected: {field_result.expected}, got: {field_result.actual}"
            elif field_result.status == FieldStatus.MISSING:
                status_icon = "[red]![/red]"
                details = f"missing (expected: {field_result.expected})"
            else:  # UNEXPECTED
                status_icon = "[yellow]?[/yellow]"
                details = f"unexpected field: {field_result.actual}"

            table.add_row(status_icon, field_result.field, details)

        console.print(table)
        console.print("-" * 60)
        console.print()

    def to_json(self, indent: int = 2, include_raw: bool | None = None) -> str:
        """Export report as JSON string.

        Args:
            indent: JSON indentation level
            include_raw: Whether to include raw response (defaults to config)
        """
        from llm_spec.core.config import get_config

        if include_raw is None:
            include_raw = get_config().report.include_raw_response

        exclude = None if include_raw else {"raw_response"}
        return self.model_dump_json(indent=indent, exclude=exclude)

    def to_dict(self, include_raw: bool | None = None) -> dict[str, Any]:
        """Export report as dictionary.

        Args:
            include_raw: Whether to include raw response (defaults to config)
        """
        from llm_spec.core.config import get_config

        if include_raw is None:
            include_raw = get_config().report.include_raw_response

        exclude = None if include_raw else {"raw_response"}
        return self.model_dump(exclude=exclude)

    def save(self, path: Path | str | None = None) -> Path:
        """Save report to JSON file.

        Args:
            path: Output path. If None, uses config output_dir with auto-generated name.

        Returns:
            Path where report was saved
        """
        from llm_spec.core.config import get_config

        config = get_config().report

        if path is None:
            if config.output_dir is None:
                raise ValueError(
                    "No output path specified and report.output_dir not configured"
                )
            config.output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"{self.provider}_{self.endpoint.replace('/', '_')}_{timestamp}.json"
            )
            path = config.output_dir / filename
        else:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(self.to_json())
        return path

    def output(self, test_name: str | None = None) -> Path | None:
        """Output report according to configuration.

        Args:
            test_name: Optional test function name for labeling in collected reports.
                       If not provided, tries to get from global context.

        Returns:
            Path if saved to file, None otherwise
        """
        from llm_spec.core.config import get_config

        config = get_config().report
        saved_path = None

        # Try to get test name from global context if not provided
        if test_name is None:
            test_name = get_current_test_name()

        if config.format in ("terminal", "both"):
            self.print()

        if config.format in ("json", "both"):
            # Add to collector instead of saving individual files
            collector = get_collector()
            collector.add(self, test_name)

        return saved_path


# =============================================================================
# Report Collector - Aggregates reports from a test session
# =============================================================================


class ReportCollector:
    """Collects validation reports grouped by provider/endpoint.

    Reports are saved to separate files per endpoint, e.g.:
    - openai_chat_completions.json
    - openai_responses.json
    - openai_embeddings.json
    """

    def __init__(self) -> None:
        # Group reports by (provider, endpoint)
        self._reports: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._start_time: str = datetime.now().isoformat()

    def add(self, report: ValidationReport, test_name: str | None = None) -> None:
        """Add a report to the collection.

        Args:
            report: The validation report to add
            test_name: Optional test function name for labeling
        """
        from llm_spec.core.config import get_config

        config = get_config().report

        # Calculate validation summary
        invalid_type_count = sum(
            1 for f in report.fields if f.status == FieldStatus.INVALID_TYPE
        )
        missing_count = sum(1 for f in report.fields if f.status == FieldStatus.MISSING)
        unexpected_count = sum(
            1 for f in report.fields if f.status == FieldStatus.UNEXPECTED
        )

        entry: dict[str, Any] = {
            "test_name": test_name or "unknown",
            "timestamp": report.timestamp,
            "success": report.success,
            "validation_summary": {
                "valid": report.valid_count,
                "invalid": invalid_type_count,
                "missing": missing_count,
                "unexpected": unexpected_count,
            },
            "request_params": report.request_params,
            "response_metadata": self._extract_response_metadata(report.raw_response),
        }

        # Include fields based on success and verbose setting
        if not report.success or config.verbose_tests:
            entry["fields"] = [f.model_dump() for f in report.fields]
        else:
            # For passed tests, include a simplified notice
            entry["fields"] = [f.model_dump() for f in report.fields]
            entry["fields_detail"] = (
                "Full field details included. Set verbose_tests=false to omit."
            )

        if config.include_raw_response and report.raw_response is not None:
            entry["raw_response"] = report.raw_response

        key = (report.provider, report.endpoint)
        if key not in self._reports:
            self._reports[key] = []
        self._reports[key].append(entry)

    def _get_all_schema_params(self, provider: str, endpoint: str) -> set[str]:
        """Get all parameter names defined in the request schema for an endpoint.

        Args:
            provider: Provider name (e.g., 'openai')
            endpoint: Endpoint path (e.g., 'chat/completions')

        Returns:
            Set of parameter names from the schema
        """
        # Import schema based on provider/endpoint
        if provider == "openai":
            if endpoint == "chat/completions":
                from llm_spec.providers.openai.schemas.chat_completions import (
                    ChatCompletionRequest,
                )
                return set(ChatCompletionRequest.model_fields.keys())
            elif endpoint == "responses":
                from llm_spec.providers.openai.schemas.responses import ResponseRequest
                return set(ResponseRequest.model_fields.keys())
            elif endpoint == "embeddings":
                from llm_spec.providers.openai.schemas.embeddings import EmbeddingRequest
                return set(EmbeddingRequest.model_fields.keys())
        # Return empty set for unknown endpoints
        return set()

    def _collect_tested_params(self, reports: list[dict[str, Any]]) -> set[str]:
        """Collect all parameters that were tested across all reports.

        Args:
            reports: List of test report entries

        Returns:
            Set of parameter names that were used in tests
        """
        tested: set[str] = set()
        for report in reports:
            if report.get("request_params"):
                tested.update(report["request_params"].keys())
        return tested

    def _collect_param_validation_stats(
        self, reports: list[dict[str, Any]]
    ) -> dict[str, dict[str, int]]:
        """Collect validation statistics for each tested parameter.

        Args:
            reports: List of test report entries

        Returns:
            Dictionary mapping parameter names to their validation stats
        """
        param_stats: dict[str, dict[str, int]] = {}

        for report in reports:
            params_used = report.get("request_params", {}).keys()
            for param in params_used:
                if param not in param_stats:
                    param_stats[param] = {"tested": 0, "passed": 0, "failed": 0}

                param_stats[param]["tested"] += 1
                if report["success"]:
                    param_stats[param]["passed"] += 1
                else:
                    param_stats[param]["failed"] += 1

        return param_stats

    def _collect_field_stats(self, reports: list[dict[str, Any]]) -> dict[str, Any]:
        """Collect field validation statistics across all reports.

        Args:
            reports: List of test report entries

        Returns:
            Dictionary with field validation statistics
        """
        field_stats: dict[str, dict[str, int]] = {}
        validated_fields: set[str] = set()

        for report in reports:
            for field_result in report["fields"]:
                field_name = field_result["field"]
                validated_fields.add(field_name)

                if field_name not in field_stats:
                    field_stats[field_name] = {
                        "validated": 0,
                        "valid": 0,
                        "invalid": 0,
                    }

                field_stats[field_name]["validated"] += 1
                if field_result["status"] == "valid":
                    field_stats[field_name]["valid"] += 1
                else:
                    field_stats[field_name]["invalid"] += 1

        return {
            "response_fields_validated": sorted(validated_fields),
            "field_validation_stats": field_stats,
        }

    def _collect_issues(self, reports: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Collect all validation issues across reports.

        Args:
            reports: List of test report entries

        Returns:
            Dictionary categorizing all issues
        """
        issues: dict[str, list[dict[str, Any]]] = {
            "failed_validations": [],
            "missing_fields": [],
            "unexpected_fields": [],
            "type_mismatches": [],
        }

        for report in reports:
            test_name = report["test_name"]
            for field in report["fields"]:
                if field["status"] == "invalid_type":
                    issues["type_mismatches"].append({
                        "test": test_name,
                        "field": field["field"],
                        "expected": field["expected"],
                        "actual": field["actual"],
                    })
                elif field["status"] == "missing":
                    issues["missing_fields"].append({
                        "test": test_name,
                        "field": field["field"],
                        "expected": field["expected"],
                    })
                elif field["status"] == "unexpected":
                    issues["unexpected_fields"].append({
                        "test": test_name,
                        "field": field["field"],
                        "actual": field["actual"],
                    })

        return issues

    def _extract_response_metadata(self, raw_response: dict[str, Any] | None) -> dict[str, Any]:
        """Extract key metadata from raw API response.

        Args:
            raw_response: Raw API response dictionary

        Returns:
            Dictionary with extracted metadata
        """
        if not raw_response:
            return {}

        metadata: dict[str, Any] = {}

        # Common fields across providers
        common_fields = ["id", "model", "created", "object", "system_fingerprint", "service_tier"]
        for field in common_fields:
            if field in raw_response:
                metadata[field] = raw_response[field]

        return metadata

    def _generate_recommendations(
        self,
        provider: str,
        endpoint: str,
        reports: list[dict[str, Any]],
        not_tested_params: set[str],
        issues: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Generate actionable recommendations based on test results.

        Args:
            provider: Provider name
            endpoint: Endpoint path
            reports: List of test report entries
            not_tested_params: Set of parameters not yet tested
            issues: Dictionary of validation issues

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []

        # Recommend testing untested parameters
        if not_tested_params:
            params_list = sorted(not_tested_params)[:5]  # Show first 5
            params_str = ", ".join(params_list)
            if len(not_tested_params) > 5:
                params_str += f", and {len(not_tested_params) - 5} more"
            recommendations.append(
                f"Consider testing the following untested parameters: {params_str}"
            )

        # Recommend fixing validation errors
        if issues["type_mismatches"] or issues["missing_fields"]:
            error_count = len(issues["type_mismatches"]) + len(issues["missing_fields"])
            recommendations.append(
                f"Fix {error_count} validation error(s) before adding new test cases"
            )

        # Recommend more test cases if coverage is low
        total_tests = len(reports)
        if total_tests < 5:
            recommendations.append(
                f"Add more test cases (current: {total_tests}, recommended: 10+)"
            )

        # General recommendations
        recommendations.append(
            "Add tests for error scenarios (rate limits, invalid params, etc.)"
        )

        if total_tests >= 10 and not issues["type_mismatches"]:
            recommendations.append(
                "Test additional models to verify consistency across model versions"
            )

        return recommendations

    def save(self) -> list[Path]:
        """Save all collected reports to separate JSON files per endpoint.

        Returns:
            List of paths where reports were saved
        """
        from llm_spec.core.config import get_config

        config = get_config().report

        if config.output_dir is None:
            raise ValueError("report.output_dir not configured")

        config.output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[Path] = []

        for (provider, endpoint), reports in self._reports.items():
            # Build filename: openai_chat_completions.json
            endpoint_slug = endpoint.replace("/", "_")
            filename = f"{provider}_{endpoint_slug}.json"
            path = config.output_dir / filename

            # Build summary for this endpoint
            total_tests = len(reports)
            passed_tests = sum(1 for r in reports if r["success"])
            failed_tests = total_tests - passed_tests

            # Calculate timing
            end_time = datetime.now().isoformat()
            start_dt = datetime.fromisoformat(self._start_time)
            end_dt = datetime.fromisoformat(end_time)
            duration_seconds = round((end_dt - start_dt).total_seconds(), 2)

            # Calculate field statistics
            total_fields_validated = sum(
                sum(r["validation_summary"].values()) for r in reports
            )
            unique_fields: set[str] = set()
            for r in reports:
                for f in r["fields"]:
                    unique_fields.add(f["field"])

            # Calculate parameter coverage
            all_params = self._get_all_schema_params(provider, endpoint)
            tested_params = self._collect_tested_params(reports)
            not_tested_params = all_params - tested_params
            param_validation_stats = self._collect_param_validation_stats(reports)

            # Collect field coverage stats
            field_coverage = self._collect_field_stats(reports)

            # Collect issues
            issues = self._collect_issues(reports)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                provider, endpoint, reports, not_tested_params, issues
            )

            output: dict[str, Any] = {
                "summary": {
                    "start_time": self._start_time,
                    "end_time": end_time,
                    "duration_seconds": duration_seconds,
                    "provider": provider,
                    "endpoint": endpoint,
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "total_fields_validated": total_fields_validated,
                    "unique_fields_covered": len(unique_fields),
                },
                "parameter_coverage": {
                    "tested": sorted(tested_params),
                    "not_tested": sorted(not_tested_params),
                    "coverage_percent": (
                        round(len(tested_params) / len(all_params) * 100, 1)
                        if all_params
                        else 0
                    ),
                    "validation_stats": param_validation_stats,
                },
                "field_coverage": field_coverage,
                "issues": issues,
                "tests": reports,
                "recommendations": recommendations,
            }

            path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
            saved_paths.append(path)

        return saved_paths

    def clear(self) -> None:
        """Clear all collected reports."""
        self._reports = {}
        self._start_time = datetime.now().isoformat()

    @property
    def count(self) -> int:
        """Number of reports collected."""
        return sum(len(reports) for reports in self._reports.values())


# =============================================================================
# Global test name context (set by pytest hooks)
# =============================================================================

_current_test_name: str | None = None


def set_current_test_name(name: str | None) -> None:
    """Set the current test name (called by pytest hooks)."""
    global _current_test_name
    _current_test_name = name


def get_current_test_name() -> str | None:
    """Get the current test name."""
    return _current_test_name
