"""xAI (Grok) API client implementation."""

from __future__ import annotations

from typing import Any

from llm_spec.core import config as global_config
from llm_spec.core.client import BaseClient
from llm_spec.core.config import ProviderConfig
from llm_spec.core.report import ValidationReport
from llm_spec.core.validator import SchemaValidator
from llm_spec.providers.xai.schemas import ChatCompletionResponse


class XAIClient(BaseClient):
    """Client for xAI (Grok) API.

    xAI API is compatible with OpenAI's API format.
    """

    provider_name = "xai"
    default_base_url = "https://api.x.ai/v1"

    def _get_global_config(self) -> ProviderConfig:
        return global_config.xai

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def validate_chat_completion(
        self,
        *,
        model: str = "grok-beta",
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ValidationReport:
        """Validate chat completion endpoint response against schema.

        Args:
            model: Model to use for the test request
            messages: Optional custom messages
            **kwargs: Additional parameters

        Returns:
            ValidationReport with field-level results
        """
        if messages is None:
            messages = [{"role": "user", "content": "Say 'test' and nothing else."}]

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": 10,
            **kwargs,
        }

        response = self.request("POST", "/chat/completions", json=request_body)

        validator = SchemaValidator(provider=self.provider_name, endpoint="chat/completions")
        return validator.validate(response, ChatCompletionResponse)
