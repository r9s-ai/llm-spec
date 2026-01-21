"""Integration tests for Gemini API validation."""

from __future__ import annotations

import pytest

from llm_spec.providers.gemini import GeminiClient


@pytest.mark.integration
def test_gemini_generate_content(gemini_client: GeminiClient) -> None:
    """Test Gemini generateContent response validation."""
    report = gemini_client.validate_generate_content()

    # Print report for visibility
    report.print()

    # Basic assertions
    assert report.provider == "gemini"
    assert report.endpoint == "generateContent"
    assert report.total_fields > 0

    # Log results
    print(f"\nValidation {'PASSED' if report.success else 'FAILED'}")
    print(f"Valid: {report.valid_count}/{report.total_fields}")
