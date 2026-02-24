"""Provider configuration service for business logic."""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from llm_spec.web.config import settings
from llm_spec.web.core.exceptions import NotFoundError
from llm_spec.web.models.provider import ProviderConfigModel
from llm_spec.web.repositories.provider_repo import ProviderRepository


class ProviderService:
    """Service for provider configuration business logic.

    This class orchestrates provider configuration operations and manages transactions.
    It also syncs provider configurations to the TOML file for CLI compatibility.
    """

    def get_provider(self, db: Session, provider: str) -> ProviderConfigModel:
        """Get a provider configuration.

        Args:
            db: Database session.
            provider: Provider name.

        Returns:
            ProviderConfigModel instance.

        Raises:
            NotFoundError: If provider configuration not found.
        """
        repo = ProviderRepository(db)
        config = repo.get_by_provider(provider)
        if config is None:
            raise NotFoundError("ProviderConfig", provider)
        return config

    def list_providers(self, db: Session) -> Sequence[ProviderConfigModel]:
        """List all provider configurations.

        Args:
            db: Database session.

        Returns:
            List of ProviderConfigModel instances.
        """
        repo = ProviderRepository(db)
        return repo.list_all()

    def upsert_provider(
        self,
        db: Session,
        provider: str,
        api_type: str,
        base_url: str,
        timeout: float,
        api_key: str | None,
        extra_config: dict,
    ) -> ProviderConfigModel:
        """Create or update a provider configuration.

        Args:
            db: Database session.
            provider: Provider name.
            api_type: API type (openai, anthropic, gemini, xai).
            base_url: API base URL.
            timeout: Request timeout in seconds.
            api_key: API key for authentication (None to keep existing).
            extra_config: Additional configuration.

        Returns:
            Created or updated ProviderConfigModel instance.
        """
        repo = ProviderRepository(db)
        config = repo.get_by_provider(provider)

        if config is None:
            # For new provider, api_key is required
            if api_key is None:
                raise ValueError("api_key is required for new provider")
            config = ProviderConfigModel(
                provider=provider,
                api_type=api_type,
                base_url=base_url,
                timeout=timeout,
                api_key=api_key,
                extra_config=extra_config,
            )
        else:
            # For update, only update fields that are provided
            config.api_type = api_type
            config.base_url = base_url
            config.timeout = timeout
            if api_key is not None:
                config.api_key = api_key
            config.extra_config = extra_config

        repo.upsert(config)
        db.commit()
        db.refresh(config)

        # Sync to TOML file
        self._sync_providers_to_toml(db)

        return config

    def delete_provider(self, db: Session, provider: str) -> None:
        """Delete a provider configuration.

        Args:
            db: Database session.
            provider: Provider name.

        Raises:
            NotFoundError: If provider configuration not found.
        """
        repo = ProviderRepository(db)
        config = repo.get_by_provider(provider)
        if config is None:
            raise NotFoundError("ProviderConfig", provider)

        repo.delete(config)
        db.commit()

        # Sync to TOML file
        self._sync_providers_to_toml(db)

    def _sync_providers_to_toml(self, db: Session) -> None:
        """Sync all provider configurations to the TOML file.

        This ensures CLI tools can read the latest provider configurations.

        Args:
            db: Database session.
        """
        toml_path = Path(settings.app_toml_path)

        # Read existing TOML content to preserve non-provider sections
        existing_data: dict[str, Any] = {}
        if toml_path.exists():
            try:
                with open(toml_path, "rb") as f:
                    existing_data = tomllib.load(f)
            except Exception:
                # If we can't read the file, start fresh
                existing_data = {}

        # Get all providers from database
        repo = ProviderRepository(db)
        providers = repo.list_all()

        # Known non-provider sections
        known_sections = {"log", "report"}

        # Remove old provider sections
        for key in list(existing_data.keys()):
            if key not in known_sections:
                del existing_data[key]

        # Add current provider sections
        for provider in providers:
            existing_data[provider.provider] = {
                "api_key": provider.api_key,
                "base_url": provider.base_url,
                "timeout": provider.timeout,
            }

        # Write back to TOML file
        # Note: tomllib only reads, we need to write manually
        self._write_toml(toml_path, existing_data)

    def _write_toml(self, path: Path, data: dict[str, Any]) -> None:
        """Write data to a TOML file.

        Since Python's standard library only has tomllib (read-only),
        we implement a simple TOML writer.

        Args:
            path: Path to the TOML file.
            data: Data to write.
        """
        lines: list[str] = []

        # Known non-provider sections (write these first)
        known_sections = {"log", "report"}

        # Write header comment
        lines.append("# llm-spec.toml - Auto-generated by web UI")
        lines.append("# This file is synced with the database. Manual edits may be overwritten.")
        lines.append("")

        # Write log section
        if "log" in data:
            lines.append("[log]")
            for key, value in data["log"].items():
                lines.append(f"{key} = {self._format_toml_value(value)}")
            lines.append("")

        # Write report section
        if "report" in data:
            lines.append("[report]")
            for key, value in data["report"].items():
                lines.append(f"{key} = {self._format_toml_value(value)}")
            lines.append("")

        # Write provider sections
        for key, value in data.items():
            if key not in known_sections and isinstance(value, dict):
                lines.append(f"[{key}]")
                # Write in a consistent order
                if "base_url" in value:
                    lines.append(f"base_url = {self._format_toml_value(value['base_url'])}")
                if "api_key" in value:
                    lines.append(f"api_key = {self._format_toml_value(value['api_key'])}")
                if "timeout" in value:
                    lines.append(f"timeout = {self._format_toml_value(value['timeout'])}")
                # Write any other fields
                for k, v in value.items():
                    if k not in ("base_url", "api_key", "timeout"):
                        lines.append(f"{k} = {self._format_toml_value(v)}")
                lines.append("")

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _format_toml_value(self, value: Any) -> str:
        """Format a Python value as a TOML value string.

        Args:
            value: Python value to format.

        Returns:
            TOML-formatted string.
        """
        if isinstance(value, str):
            # Escape special characters in strings
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            items = ", ".join(self._format_toml_value(item) for item in value)
            return f"[{items}]"
        elif isinstance(value, dict):
            # Inline table
            items = ", ".join(f"{k} = {self._format_toml_value(v)}" for k, v in value.items())
            return "{ " + items + " }"
        else:
            # Fallback to string representation
            return self._format_toml_value(str(value))
