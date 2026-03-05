"""Suite service backed by suites-registry files (no DB)."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

from llm_spec.suites import SuiteSpec, load_registry_suites
from llm_spec_web.core.exceptions import NotFoundError


class SuiteService:
    """Read-only suite service from registry files."""

    def __init__(
        self,
        registry_dir: Path | str = "suites-registry/providers",
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        self.registry_dir = Path(registry_dir)
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0.0)
        self._cache_lock = Lock()
        self._suites_cache: dict[str, SuiteSpec] | None = None
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

    def _build_suites_cache(self) -> dict[str, SuiteSpec]:
        now_monotonic = time.monotonic()
        with self._cache_lock:
            if (
                self._suites_cache is not None
                and (now_monotonic - self._cache_built_at) <= self._cache_ttl_seconds
            ):
                return self._suites_cache

        signature = self._registry_signature()
        with self._cache_lock:
            if self._suites_cache is not None and self._cache_registry_signature == signature:
                self._cache_built_at = now_monotonic
                return self._suites_cache

        suites = {s.suite_id: s for s in load_registry_suites(self.registry_dir)}

        with self._cache_lock:
            self._suites_cache = suites
            self._cache_registry_signature = signature
            self._cache_built_at = now_monotonic

        return suites

    def clear_cache(self) -> None:
        """Clear in-memory registry cache."""
        with self._cache_lock:
            self._suites_cache = None
            self._cache_registry_signature = None
            self._cache_built_at = 0.0

    def refresh_cache(self) -> tuple[int, int]:
        """Force rebuild cache and return suite count."""
        self.clear_cache()
        suites = self._build_suites_cache()
        return len(suites), len(suites)

    def list_suites(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        route: str | None = None,
        endpoint: str | None = None,
    ) -> list[SuiteSpec]:
        suites = list(self._build_suites_cache().values())
        if provider:
            suites = [s for s in suites if s.provider_id == provider]
        if model_name:
            suites = [s for s in suites if s.model_id == model_name]
        if route:
            suites = [s for s in suites if s.route_id == route]
        if endpoint:
            suites = [s for s in suites if s.endpoint == endpoint]
        return sorted(
            suites,
            key=lambda s: (s.provider_id, s.model_id, s.route_id),
        )

    def get_suite(self, suite_id: str) -> SuiteSpec:
        suite = self._build_suites_cache().get(suite_id)
        if suite is None:
            raise NotFoundError("SuiteSpec", suite_id)
        return suite
