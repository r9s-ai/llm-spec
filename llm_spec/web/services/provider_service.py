"""Provider configuration service for business logic."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from llm_spec.web.core.exceptions import NotFoundError
from llm_spec.web.models.provider import ProviderConfigModel
from llm_spec.web.repositories.provider_repo import ProviderRepository


class ProviderService:
    """Service for provider configuration business logic.

    This class orchestrates provider configuration operations and manages transactions.
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
        base_url: str,
        timeout: float,
        api_key: str,
        extra_config: dict,
    ) -> ProviderConfigModel:
        """Create or update a provider configuration.

        Args:
            db: Database session.
            provider: Provider name.
            base_url: API base URL.
            timeout: Request timeout in seconds.
            api_key: API key for authentication.
            extra_config: Additional configuration.

        Returns:
            Created or updated ProviderConfigModel instance.
        """
        repo = ProviderRepository(db)
        config = repo.get_by_provider(provider)

        if config is None:
            config = ProviderConfigModel(
                provider=provider,
                base_url=base_url,
                timeout=timeout,
                api_key=api_key,
                extra_config=extra_config,
            )
        else:
            config.base_url = base_url
            config.timeout = timeout
            config.api_key = api_key
            config.extra_config = extra_config

        repo.upsert(config)
        db.commit()
        db.refresh(config)
        return config
