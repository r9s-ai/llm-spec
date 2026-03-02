"""Model-suite service backed by suites-registry files (no DB)."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Lock

from llm_spec.suites.registry import ModelSuite, hydrate_executable_suite, load_registry_suites
from llm_spec_web.core.exceptions import NotFoundError


class SuiteService:
    """Read-only model-suite service from registry files."""

    def __init__(
        self,
        registry_dir: Path | str = "suites-registry/providers",
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        self.registry_dir = Path(registry_dir)
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0.0)
        self._cache_lock = Lock()
        self._model_suites_cache: dict[str, ModelSuite] | None = None
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

    def _build_model_suites_cache(self) -> dict[str, ModelSuite]:
        now_monotonic = time.monotonic()
        with self._cache_lock:
            if (
                self._model_suites_cache is not None
                and (now_monotonic - self._cache_built_at) <= self._cache_ttl_seconds
            ):
                return self._model_suites_cache

        signature = self._registry_signature()
        with self._cache_lock:
            if self._model_suites_cache is not None and self._cache_registry_signature == signature:
                self._cache_built_at = now_monotonic
                return self._model_suites_cache

        suites = {suite.id: suite for suite in load_registry_suites(self.registry_dir)}

        with self._cache_lock:
            self._model_suites_cache = suites
            self._cache_registry_signature = signature
            self._cache_built_at = now_monotonic

        return suites

    def clear_cache(self) -> None:
        """Clear in-memory registry cache."""
        with self._cache_lock:
            self._model_suites_cache = None
            self._cache_registry_signature = None
            self._cache_built_at = 0.0

    def refresh_cache(self) -> tuple[int, int]:
        """Force rebuild cache and return counts for model suites."""
        self.clear_cache()
        suites = self._build_model_suites_cache()
        return len(suites), len(suites)

    def list_suites(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        route: str | None = None,
        endpoint: str | None = None,
    ) -> list[ModelSuite]:
        suites = list(self._build_model_suites_cache().values())
        if provider:
            suites = [s for s in suites if s.provider == provider]
        if model_name:
            suites = [s for s in suites if s.model_name == model_name]
        if route:
            suites = [s for s in suites if str(s.route_suite.get("route", "")) == route]
        if endpoint:
            suites = [s for s in suites if str(s.route_suite.get("endpoint", "")) == endpoint]
        return sorted(
            suites,
            key=lambda s: (s.provider, s.model_name, str(s.route_suite.get("route", ""))),
        )

    def get_suite(self, suite_id: str) -> ModelSuite:
        suite = self._build_model_suites_cache().get(suite_id)
        if suite is None:
            raise NotFoundError("ModelSuite", suite_id)
        return suite

    def resolve_model_suite(self, model_suite_id: str) -> ModelSuite:
        """Resolve one model suite and validate route_suite can hydrate to executable suite."""
        suite = self.get_suite(model_suite_id)
        hydrate_executable_suite(suite.route_suite)
        return suite
