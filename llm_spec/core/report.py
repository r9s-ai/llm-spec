"""Validation report models for field-level validation results."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from rich.text import Text


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

    def output(self) -> Path | None:
        """Output report according to configuration.

        Returns:
            Path if saved to file, None otherwise
        """
        from llm_spec.core.config import get_config

        config = get_config().report
        saved_path = None

        if config.format in ("terminal", "both"):
            self.print()

        if config.format in ("json", "both"):
            if config.output_dir is not None:
                saved_path = self.save()
                print(f"Report saved to: {saved_path}")
            else:
                # Print JSON to stdout
                print(self.to_json())

        return saved_path
