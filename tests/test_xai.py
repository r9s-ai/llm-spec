"""Integration tests for xAI API validation."""

from __future__ import annotations

import pytest

from llm_spec.providers.xai import XAIClient


@pytest.mark.integration
def test_xai_chat_completion(xai_client: XAIClient) -> None:
    """Test xAI chat completion response validation."""
    report = xai_client.validate_chat_completion()

    # Print report for visibility
    report.print()

    # Basic assertions
    assert report.provider == "xai"
    assert report.endpoint == "chat/completions"
    assert report.total_fields > 0

    # Log results
    print(f"\nValidation {'PASSED' if report.success else 'FAILED'}")
    print(f"Valid: {report.valid_count}/{report.total_fields}")
