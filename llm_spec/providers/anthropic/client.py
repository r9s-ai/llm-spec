"""Anthropic API client implementation."""

from __future__ import annotations

from typing import Any

from llm_spec.core import config as global_config
from llm_spec.core.client import BaseClient
from llm_spec.core.config import ProviderConfig
from llm_spec.core.report import ValidationReport
from llm_spec.core.validator import SchemaValidator
from llm_spec.providers.anthropic.schemas import MessageResponse


class AnthropicClient(BaseClient):
    """Client for Anthropic API."""

    provider_name = "anthropic"
    default_base_url = "https://api.anthropic.com/v1"
    api_version = "2023-06-01"

    def _get_global_config(self) -> ProviderConfig:
        return global_config.anthropic

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.api_version,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def validate_messages(
        self,
        *,
        model: str = "claude-3-haiku-20240307",
        messages: list[dict[str, Any]] | None = None,
        max_tokens: int = 10,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate messages endpoint response against schema.

        Args:
            model: Model to use for the test request
            messages: Optional custom messages
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        if messages is None:
            messages = [{"role": "user", "content": "Say 'test' and nothing else."}]

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            **kwargs,
        }

        response = self.request("POST", "/messages", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="messages")
        return validator.validate(response, MessageResponse)

    def validate_chat_completion(self, **kwargs: Any) -> ValidationReport:
        """Alias for validate_messages to match base class interface."""
        return self.validate_messages(**kwargs)
