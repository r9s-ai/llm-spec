"""Provider auto-discovery registry."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_spec.core.client import BaseClient


_registry: dict[str, type[BaseClient]] = {}


def register_provider(name: str, client_class: type[BaseClient]) -> None:
    """Register a provider client class."""
    _registry[name] = client_class


def get_provider(name: str) -> type[BaseClient] | None:
    """Get a registered provider client class by name."""
    return _registry.get(name)


def list_providers() -> list[str]:
    """List all registered provider names."""
    return list(_registry.keys())


def discover_providers() -> None:
    """Auto-discover and register all providers in the providers package."""
    import llm_spec.providers as providers_pkg

    for _importer, modname, _ispkg in pkgutil.iter_modules(providers_pkg.__path__):
        try:
            module = importlib.import_module(f"llm_spec.providers.{modname}")
            # Look for a Client class that ends with "Client"
            for attr_name in dir(module):
                if attr_name.endswith("Client") and attr_name != "BaseClient":
                    client_class = getattr(module, attr_name)
                    if hasattr(client_class, "provider_name") and client_class.provider_name:
                        register_provider(client_class.provider_name, client_class)
        except ImportError:
            continue


def get_client(provider: str, **kwargs) -> BaseClient:
    """Get an instantiated client for a provider."""
    client_class = get_provider(provider)
    if client_class is None:
        raise ValueError(f"Unknown provider: {provider}. Available: {list_providers()}")
    return client_class(**kwargs)
