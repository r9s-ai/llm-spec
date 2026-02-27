"""Suite service backed by suites-registry files (no DB)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import json5

from llm_spec.registry import load_registry_suites
from llm_spec.suites import load_test_suite_from_dict
from llm_spec_web.core.exceptions import NotFoundError


@dataclass(frozen=True)
class RegistrySuite:
    id: str
    provider: str
    route: str
    model: str
    endpoint: str
    name: str
    status: str
    latest_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RegistrySuiteVersion:
    id: str
    suite_id: str
    version: int
    created_by: str
    created_at: datetime
    raw_json5: str
    parsed_json: dict[str, Any]


class SuiteService:
    """Read-only suite service from registry files."""

    def __init__(
        self,
        registry_dir: Path | str = "suites-registry/providers",
        cache_ttl_seconds: float = 2.0,
    ) -> None:
        self.registry_dir = Path(registry_dir)
        self._namespace = uuid.UUID("31fb0a3f-845d-4ec8-bf08-1f6a3fd0fc09")
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0.0)
        self._cache_lock = Lock()
        self._cache_suites: dict[str, RegistrySuite] | None = None
        self._cache_versions: dict[str, RegistrySuiteVersion] | None = None
        self._cache_registry_signature: tuple[int, int, int] | None = None
        self._cache_built_at: float = 0.0

    def _suite_id(self, provider: str, route: str, model: str) -> str:
        return str(uuid.uuid5(self._namespace, f"suite:{provider}:{route}:{model}"))

    def _version_id(self, suite_id: str, version: int) -> str:
        return str(uuid.uuid5(self._namespace, f"version:{suite_id}:{version}"))

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

    def _build_indices(self) -> tuple[dict[str, RegistrySuite], dict[str, RegistrySuiteVersion]]:
        now_monotonic = time.monotonic()
        with self._cache_lock:
            if (
                self._cache_suites is not None
                and self._cache_versions is not None
                and (now_monotonic - self._cache_built_at) <= self._cache_ttl_seconds
            ):
                return self._cache_suites, self._cache_versions

        signature = self._registry_signature()
        with self._cache_lock:
            if (
                self._cache_suites is not None
                and self._cache_versions is not None
                and self._cache_registry_signature == signature
            ):
                self._cache_built_at = now_monotonic
                return self._cache_suites, self._cache_versions

        now = datetime.now(UTC)
        suites: dict[str, RegistrySuite] = {}
        versions: dict[str, RegistrySuiteVersion] = {}

        for expanded in load_registry_suites(self.registry_dir):
            provider = expanded.provider
            route = expanded.route
            model = expanded.model
            suite_id = self._suite_id(provider, route, model)
            parsed_json = dict(expanded.suite_dict)
            raw_json5_source = dict(expanded.suite_dict)

            # Normalize suite payload to executable test rows so UI selection and
            # runner execution share the same test-name space (including variants).
            loaded_suite = load_test_suite_from_dict(parsed_json)
            parsed_json["tests"] = [
                {
                    "name": test.name,
                    "description": test.description,
                    "params": test.params,
                    "focus_param": test.focus_param,
                    "baseline": test.baseline,
                    "stream": test.stream,
                    "stream_expectations": test.stream_expectations,
                    "endpoint_override": test.endpoint_override,
                    "files": test.files,
                    "schemas": test.schemas,
                    "required_fields": test.required_fields,
                    "method": test.method,
                    "tags": test.tags,
                }
                for test in loaded_suite.tests
            ]
            raw_json5 = json5.dumps(raw_json5_source, quote_keys=False, trailing_commas=False)
            name = str(parsed_json.get("suite_name") or f"{provider} {route} ({model})")

            suite = RegistrySuite(
                id=suite_id,
                provider=provider,
                route=route,
                model=model,
                endpoint=str(parsed_json.get("endpoint", "")),
                name=name,
                status="active",
                latest_version=1,
                created_at=now,
                updated_at=now,
            )
            suites[suite_id] = suite

            version = RegistrySuiteVersion(
                id=self._version_id(suite_id, 1),
                suite_id=suite_id,
                version=1,
                created_by="registry",
                created_at=now,
                raw_json5=raw_json5,
                parsed_json=parsed_json,
            )
            versions[version.id] = version

        with self._cache_lock:
            self._cache_suites = suites
            self._cache_versions = versions
            self._cache_registry_signature = signature
            self._cache_built_at = now_monotonic

        return suites, versions

    def clear_cache(self) -> None:
        """Clear in-memory registry cache."""
        with self._cache_lock:
            self._cache_suites = None
            self._cache_versions = None
            self._cache_registry_signature = None
            self._cache_built_at = 0.0

    def refresh_cache(self) -> tuple[int, int]:
        """Force rebuild cache and return counts for suites and versions."""
        self.clear_cache()
        suites, versions = self._build_indices()
        return len(suites), len(versions)

    def list_suites(
        self,
        provider: str | None = None,
        route: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
    ) -> list[RegistrySuite]:
        suites, _ = self._build_indices()
        rows = list(suites.values())
        if provider:
            rows = [s for s in rows if s.provider == provider]
        if route:
            rows = [s for s in rows if s.route == route]
        if model:
            rows = [s for s in rows if s.model == model]
        if endpoint:
            rows = [s for s in rows if s.endpoint == endpoint]
        return sorted(rows, key=lambda s: (s.provider, s.route, s.model))

    def get_suite(self, suite_id: str) -> RegistrySuite:
        suites, _ = self._build_indices()
        suite = suites.get(suite_id)
        if suite is None:
            raise NotFoundError("Suite", suite_id)
        return suite

    def list_versions(self, suite_id: str) -> list[RegistrySuiteVersion]:
        suites, versions = self._build_indices()
        if suite_id not in suites:
            raise NotFoundError("Suite", suite_id)
        return [v for v in versions.values() if v.suite_id == suite_id]

    def get_version(self, version_id: str) -> RegistrySuiteVersion:
        _, versions = self._build_indices()
        version = versions.get(version_id)
        if version is None:
            raise NotFoundError("SuiteVersion", version_id)
        return version

    def resolve_suite_by_version_id(self, version_id: str) -> RegistrySuiteVersion:
        """Resolve a synthetic suite version id to parsed registry suite."""
        _, versions = self._build_indices()
        version = versions.get(version_id)
        if version is None:
            raise NotFoundError("SuiteVersion", version_id)
        # Validate route payload shape with core loader for safety.
        load_test_suite_from_dict(version.parsed_json)
        return version
