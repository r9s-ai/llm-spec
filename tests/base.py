"""Base test utilities for API validation tests."""

from __future__ import annotations

from llm_spec.core.report import FieldStatus, ValidationReport


def assert_report_valid(report: ValidationReport) -> None:
    """Assert that a validation report passed all checks.

    Args:
        report: The validation report to check

    Raises:
        AssertionError: If validation failed
    """
    assert report.total_fields > 0, "Report should have checked at least one field"

    if not report.success:
        # Collect failed fields for error message
        failed_fields = [
            f for f in report.fields if f.status != FieldStatus.VALID
        ]
        failed_info = "\n".join(
            f"  - {f.field}: {f.status.value} (expected: {f.expected}, got: {f.actual})"
            for f in failed_fields
        )
        raise AssertionError(
            f"Validation failed for {report.provider}/{report.endpoint}:\n{failed_info}"
        )


def assert_report_has_fields(report: ValidationReport, fields: list[str]) -> None:
    """Assert that a validation report checked specific fields.

    Args:
        report: The validation report to check
        fields: List of field paths that should have been validated

    Raises:
        AssertionError: If any expected field is missing
    """
    validated_fields = {f.field for f in report.fields}
    missing = set(fields) - validated_fields
    if missing:
        raise AssertionError(f"Missing expected fields: {missing}")


def assert_field_valid(report: ValidationReport, field_path: str) -> None:
    """Assert that a specific field passed validation.

    Args:
        report: The validation report
        field_path: The field path to check (e.g., "choices[0].message.content")

    Raises:
        AssertionError: If field is missing or invalid
    """
    for field in report.fields:
        if field.field == field_path:
            if field.status != FieldStatus.VALID:
                raise AssertionError(
                    f"Field '{field_path}' is {field.status.value}, "
                    f"expected: {field.expected}, got: {field.actual}"
                )
            return
    raise AssertionError(f"Field '{field_path}' not found in report")


def get_field_status(report: ValidationReport, field_path: str) -> FieldStatus | None:
    """Get the validation status of a specific field.

    Args:
        report: The validation report
        field_path: The field path to check

    Returns:
        FieldStatus or None if field not found
    """
    for field in report.fields:
        if field.field == field_path:
            return field.status
    return None


def count_fields_by_status(report: ValidationReport, status: FieldStatus) -> int:
    """Count fields with a specific status.

    Args:
        report: The validation report
        status: The status to count

    Returns:
        Number of fields with the given status
    """
    return sum(1 for f in report.fields if f.status == status)


def get_unexpected_fields(report: ValidationReport) -> list[str]:
    """Get list of unexpected fields in the response.

    Args:
        report: The validation report

    Returns:
        List of field paths that were unexpected
    """
    return [f.field for f in report.fields if f.status == FieldStatus.UNEXPECTED]


def print_report_summary(report: ValidationReport) -> None:
    """Print a summary of the validation report.

    Args:
        report: The validation report
    """
    status = "PASSED" if report.success else "FAILED"
    print(f"\n{report.provider}/{report.endpoint}: {status}")
    print(f"  Valid: {report.valid_count}/{report.total_fields}")

    if not report.success:
        print("  Failed fields:")
        for f in report.fields:
            if f.status != FieldStatus.VALID:
                print(f"    - {f.field}: {f.status.value}")
