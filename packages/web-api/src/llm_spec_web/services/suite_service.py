"""Suite service backed by suites-registry files (no DB)."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

from llm_spec.suites import Registry, SuiteSpec
from llm_spec_web.core.exceptions import NotFoundError


class SuiteService:
    """Read-only suite service from registry files.

    Wraps ``Registry`` (core) with TTL + file-signature caching.
    """

    def __init__(
        self,
        registry_dir: Path | str = "suites-registry/providers",
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        self.registry_dir = Path(registry_dir)
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0.0)
        self._cache_lock = Lock()
        self._registry: Registry | None = None
        self._cache_registry_signature: tuple[int, int, int] | None = None
        self._cache_built_at: float = 0.0

    def _registry_signature(self) -> tuple[int, int, int]:
        """Build a cheap signature to detect registry file changes."""
        if not self.registry_dir.exists():
            return (0, 0, 0)
        file_count = 0
        total_size = 0
        max_mtime_ns = 0
        for path in self.registry_dir.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            file_count += 1
            total_size += int(stat.st_size)
            max_mtime_ns = max(max_mtime_ns, int(stat.st_mtime_ns))
        return (file_count, total_size, max_mtime_ns)

    def _build_suites_cache(self) -> Registry:
        now_monotonic = time.monotonic()
        with self._cache_lock:
            if (
                self._registry is not None
                and (now_monotonic - self._cache_built_at) <= self._cache_ttl_seconds
            ):
                return self._registry

        signature = self._registry_signature()
        with self._cache_lock:
            if self._registry is not None and self._cache_registry_signature == signature:
                self._cache_built_at = now_monotonic
                return self._registry

        registry = Registry.from_directory(self.registry_dir)

        with self._cache_lock:
            self._registry = registry
            self._cache_registry_signature = signature
            self._cache_built_at = now_monotonic

        return registry

    def clear_cache(self) -> None:
        """Clear in-memory registry cache."""
        with self._cache_lock:
            self._registry = None
            self._cache_registry_signature = None
            self._cache_built_at = 0.0

    def refresh_cache(self) -> tuple[int, int]:
        """Force rebuild cache and return suite count."""
        self.clear_cache()
        registry = self._build_suites_cache()
        count = len(registry)
        return count, count

    def list_suites(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        route: str | None = None,
        endpoint: str | None = None,
    ) -> list[SuiteSpec]:
        registry = self._build_suites_cache()
        return registry.list_suites(
            provider=provider,
            model=model_name,
            route=route,
            endpoint=endpoint,
        )

    def get_suite(self, suite_id: str) -> SuiteSpec:
        registry = self._build_suites_cache()
        suite = registry.get_suite(suite_id)
        if suite is None:
            raise NotFoundError("SuiteSpec", suite_id)
        return suite

    def get_registry(self) -> Registry:
        """Return the cached Registry snapshot."""
        return self._build_suites_cache()
