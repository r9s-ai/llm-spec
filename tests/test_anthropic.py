"""Integration tests for Anthropic API validation."""

from __future__ import annotations

import pytest

from llm_spec.providers.anthropic import AnthropicClient


@pytest.mark.integration
def test_anthropic_messages(anthropic_client: AnthropicClient) -> None:
    """Test Anthropic messages response validation."""
    report = anthropic_client.validate_messages()

    # Print report for visibility
    report.print()

    # Basic assertions
    assert report.provider == "anthropic"
    assert report.endpoint == "messages"
    assert report.total_fields > 0

    # Log results
    print(f"\nValidation {'PASSED' if report.success else 'FAILED'}")
    print(f"Valid: {report.valid_count}/{report.total_fields}")
