"""Google Gemini API client implementation."""

from __future__ import annotations

from typing import Any

from llm_spec.core import config as global_config
from llm_spec.core.client import BaseClient
from llm_spec.core.config import ProviderConfig
from llm_spec.core.report import ValidationReport
from llm_spec.core.validator import SchemaValidator
from llm_spec.providers.gemini.schemas import GenerateContentResponse


class GeminiClient(BaseClient):
    """Client for Google Gemini API."""

    provider_name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _get_global_config(self) -> ProviderConfig:
        return global_config.gemini

    def _build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _get_endpoint(self, model: str) -> str:
        """Build the endpoint URL with API key."""
        return f"/models/{model}:generateContent?key={self.api_key}"

    def validate_generate_content(
        self,
        *,
        model: str = "gemini-1.5-flash",
        contents: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate generateContent endpoint response against schema.

        Args:
            model: Model to use for the test request
            contents: Optional custom contents
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        if contents is None:
            contents = [{"parts": [{"text": "Say 'test' and nothing else."}]}]

        request_body = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 10},
            **kwargs,
        }

        endpoint = self._get_endpoint(model)
        response = self.request("POST", endpoint, json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="generateContent")
        return validator.validate(response, GenerateContentResponse)

    def validate_chat_completion(self, **kwargs: Any) -> ValidationReport:
        """Alias for validate_generate_content to match base class interface."""
        return self.validate_generate_content(**kwargs)
