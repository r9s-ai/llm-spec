"""Registry loader — expands (provider × model × route) into SuiteSpec list.

Also provides:
- ``Registry``: immutable snapshot of the registry, caller controls lifecycle/caching.
- ``build_executable_cases()``: convert a SuiteSpec into executable ExecutableCase list.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

import json5

from .loader import parse_route_dict
from .types import (
    ExecutableCase,
    HttpRequest,
    ModelSpec,
    ProviderSpec,
    SchemaRef,
    SuiteSpec,
    TestDef,
    ValidationSpec,
)

# ── Deterministic suite ID ────────────────────────────────


def _suite_id(provider: str, model: str, route: str) -> str:
    """Deterministic short hash from (provider, model, route)."""
    key = f"{provider}:{model}:{route}"
    # return hashlib.sha256(key.encode()).hexdigest()[:12]
    return key


# ── File-system readers ───────────────────────────────────


def _read_json5(path: Path) -> dict[str, Any]:
    data = json5.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Route file must be an object: {path}")
    return data


def _load_provider_spec(provider_dir: Path) -> ProviderSpec:
    provider = provider_dir.name
    provider_toml = provider_dir / "provider.toml"
    if not provider_toml.exists():
        return ProviderSpec(provider_id=provider, api_family=provider)

    data = tomllib.loads(provider_toml.read_text(encoding="utf-8"))
    headers = data.get("headers", {})
    if headers is None:
        headers = {}
    if not isinstance(headers, dict):
        raise ValueError(f"[headers] must be a table in {provider_toml}")
    return ProviderSpec(
        provider_id=provider,
        api_family=str(data.get("api_family") or provider),
        routes_from=str(data["routes_from"]) if data.get("routes_from") else None,
        headers={str(k): str(v) for k, v in headers.items()},
    )


def _load_local_routes(provider_dir: Path) -> dict[str, dict[str, Any]]:
    routes_dir = provider_dir / "routes"
    route_files: list[Path] = []
    if routes_dir.exists():
        route_files = sorted(p for p in routes_dir.rglob("*.json5") if p.is_file())
    else:
        route_files = sorted(p for p in provider_dir.glob("*.json5") if p.is_file())

    routes: dict[str, dict[str, Any]] = {}
    for path in route_files:
        route_name = path.stem
        payload = copy.deepcopy(_read_json5(path))
        payload.pop("provider", None)
        if "base_params" in payload:
            raise ValueError(
                f"Route '{path}' uses deprecated 'base_params'. "
                "Move defaults into tests[].baseline.params."
            )
        routes[route_name] = payload
    return routes


def _load_model_specs(provider_dir: Path) -> dict[str, ModelSpec]:
    model_dir = provider_dir / "models"
    if not model_dir.exists():
        return {}
    models: dict[str, ModelSpec] = {}
    for model_path in sorted(model_dir.glob("*.toml")):
        data = tomllib.loads(model_path.read_text(encoding="utf-8"))
        model_id = model_path.stem

        routes_raw = data.get("routes", [])
        if not isinstance(routes_raw, list):
            raise ValueError(f"models/{model_id}.toml routes must be a list")

        include_raw = data.get("include_tests")
        if include_raw is not None and not isinstance(include_raw, list):
            raise ValueError(f"models/{model_id}.toml include_tests must be a list")

        include_tests = [str(n) for n in include_raw] if isinstance(include_raw, list) else None
        if include_tests is not None and "baseline" not in include_tests:
            raise ValueError(f"models/{model_id}.toml include_tests must include 'baseline'.")

        exclude_raw = data.get("exclude_tests", []) or []
        if not isinstance(exclude_raw, list):
            raise ValueError(f"models/{model_id}.toml exclude_tests must be a list")

        exclude_tests = [str(n) for n in exclude_raw] if exclude_raw else None
        if exclude_tests and "baseline" in exclude_tests:
            raise ValueError(
                f"models/{model_id}.toml cannot exclude baseline test; baseline is required."
            )

        models[model_id] = ModelSpec(
            model_id=model_id,
            routes=[str(r) for r in routes_raw],
            include_tests=include_tests,
            exclude_tests=exclude_tests,
            baseline_params_override=data.get("baseline_params_override", {}) or {},
        )
    return models


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def resolve_provider_routes_from(
    provider: str,
    provider_dirs: dict[str, Path],
    specs: dict[str, ProviderSpec],
    cache: dict[str, dict[str, dict[str, Any]]],
    stack: list[str],
) -> dict[str, dict[str, Any]]:
    if provider in cache:
        return cache[provider]

    if provider in stack:
        chain = " -> ".join([*stack, provider])
        raise ValueError(f"Circular routes_from detected: {chain}")

    provider_dir = provider_dirs[provider]
    spec = specs[provider]

    merged: dict[str, dict[str, Any]] = {}
    if spec.routes_from:
        parent = spec.routes_from
        if parent not in provider_dirs:
            raise ValueError(f"routes_from '{parent}' not found for provider '{provider}'")
        merged.update(
            resolve_provider_routes_from(
                parent,
                provider_dirs=provider_dirs,
                specs=specs,
                cache=cache,
                stack=[*stack, provider],
            )
        )

    merged.update(_load_local_routes(provider_dir))
    cache[provider] = merged
    return merged


# ── Main expansion ────────────────────────────────────────


def _discover_provider_dirs(registry_dir: Path) -> dict[str, Path]:
    return {
        p.name: p
        for p in sorted(registry_dir.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    }


def _load_provider_specs(provider_dirs: dict[str, Path]) -> dict[str, ProviderSpec]:
    return {
        provider_name: _load_provider_spec(provider_dir)
        for provider_name, provider_dir in provider_dirs.items()
    }


def _filter_tests(
    route_spec_tests: list[TestDef],
    model_spec: ModelSpec,
) -> list[TestDef]:
    include_set = set(model_spec.include_tests) if model_spec.include_tests else None
    exclude_set = set(model_spec.exclude_tests) if model_spec.exclude_tests else set()

    filtered_tests: list[TestDef] = []
    for test_def in route_spec_tests:
        test_name = str(test_def.name or "")
        if include_set is not None and test_name not in include_set:
            continue
        if test_name and test_name in exclude_set:
            continue
        filtered_tests.append(test_def)

    return filtered_tests


def _baseline_params_override(
    baseline: TestDef,
    *,
    model_id: str,
    api_family: str,
    baseline_params_override: dict[str, Any],
) -> dict[str, Any]:
    baseline_params = copy.deepcopy(baseline.params or {})
    if not isinstance(baseline_params, dict):
        baseline_params = {}
    if api_family == "gemini":
        baseline_params.pop("model", None)
    else:
        baseline_params["model"] = model_id
    baseline_params = _deep_merge(baseline_params, baseline_params_override)
    baseline.params = baseline_params
    return baseline_params


def load_SuiteSpecs(
    registry_dir: Path | str = "suites-registry/providers",
) -> list[SuiteSpec]:
    """Load and expand registry into a list of SuiteSpec objects."""
    registry_dir = Path(registry_dir)
    if not registry_dir.exists():
        return []

    provider_dirs = _discover_provider_dirs(registry_dir)

    provider_specs = _load_provider_specs(provider_dirs)

    routes_cache: dict[str, dict[str, dict[str, Any]]] = {}
    expanded_suites: list[SuiteSpec] = []

    for provider_name, provider_dir in provider_dirs.items():
        provider_spec = provider_specs[provider_name]
        api_family = provider_spec.api_family or provider_name
        model_specs = _load_model_specs(provider_dir)

        resolved_routes = resolve_provider_routes_from(
            provider_name,
            provider_dirs=provider_dirs,
            specs=provider_specs,
            cache=routes_cache,
            stack=[],
        )

        for model_id, model_spec in model_specs.items():
            for route_name in model_spec.routes:
                route_name = str(route_name)
                if route_name not in resolved_routes:
                    raise ValueError(
                        f"Provider '{provider_name}' model '{model_id}' references unknown route '{route_name}'"
                    )
                route_payload = resolved_routes[route_name]
                route_dict = copy.deepcopy(route_payload)
                route_dict["provider"] = provider_name

                # Gemini model placeholder in endpoint
                endpoint = str(route_dict.get("endpoint", ""))
                if api_family == "gemini":
                    endpoint = endpoint.replace("{model}", model_id)
                route_dict["endpoint"] = endpoint

                # Expand variants first
                route_spec = parse_route_dict(route_dict, route_id=route_name, source_path=None)

                # Filter by include/exclude (after expansion)
                filtered_tests = _filter_tests(route_spec.tests, model_spec)

                # Validate exactly one baseline
                baseline_tests = [t for t in filtered_tests if t.baseline is True]
                if len(baseline_tests) != 1:
                    raise ValueError(
                        f"Provider '{provider_name}' model '{model_id}' route '{route_name}' must "
                        f"have exactly one baseline test after expansion, got {len(baseline_tests)}"
                    )

                # Inject model into baseline params
                baseline_params = _baseline_params_override(
                    baseline_tests[0],
                    model_id=model_id,
                    api_family=api_family,
                    baseline_params_override=model_spec.baseline_params_override,
                )

                expanded_suites.append(
                    SuiteSpec(
                        suite_id=_suite_id(provider_name, model_id, route_name),
                        suite_name=f"{provider_name}/{model_id}/{route_name}",
                        provider_id=provider_name,
                        model_id=model_id,
                        route_id=route_name,
                        api_family=api_family,
                        endpoint=route_spec.endpoint,
                        method=route_spec.method,
                        provider_headers=copy.deepcopy(provider_spec.headers),
                        schemas=route_spec.schemas,
                        required_fields=route_spec.required_fields,
                        stream_rules=route_spec.stream_rules,
                        baseline_params=baseline_params,
                        tests=filtered_tests,
                        source_path=None,
                    )
                )

    return expanded_suites


# ── Execution plan builder ────────────────────────────────


def build_executable_cases(
    suiteSpec: SuiteSpec,
    selected_tests: set[str] | None = None,
) -> list[ExecutableCase]:
    """Convert a SuiteSpec into a list of executable ExecutableCase objects.

    Args:
        suite: The expanded suite specification.
        selected_tests: If given, only include tests whose names are in this set.
                        If None, include all tests.

    Returns:
        List of self-contained ExecutableCase objects ready for execution.
    """
    cases: list[ExecutableCase] = []

    for test_def in suiteSpec.tests:
        if selected_tests is not None and test_def.name not in selected_tests:
            continue

        # Merge params: baseline + test overrides
        merged_params = copy.deepcopy(suiteSpec.baseline_params)
        merged_params.update(copy.deepcopy(test_def.params))

        # Resolve endpoint
        endpoint = test_def.endpoint_override or suiteSpec.endpoint
        method = test_def.method or suiteSpec.method

        # Build HttpRequest
        request = HttpRequest(
            method=method,
            endpoint=endpoint,
            params=merged_params,
            headers=copy.deepcopy(suiteSpec.provider_headers),
            files=copy.deepcopy(test_def.files) if test_def.files else None,
            stream=test_def.check_stream,
        )

        # Build ValidationSpec: test-level overrides > suite-level defaults
        test_schemas = test_def.schemas or SchemaRef()
        response_schema = test_schemas.response or suiteSpec.schemas.response
        stream_chunk_schema = test_schemas.stream_chunk or suiteSpec.schemas.stream_chunk

        # Required fields: suite-level + test-level
        all_required_fields = list(suiteSpec.required_fields)
        if test_def.required_fields:
            all_required_fields.extend(test_def.required_fields)

        checks = ValidationSpec(
            response_schema=response_schema,
            stream_chunk_schema=stream_chunk_schema,
            required_fields=all_required_fields,
            stream_rules=test_def.stream_rules or suiteSpec.stream_rules,
        )

        case_id = f"{suiteSpec.suite_id}:{test_def.name}"

        cases.append(
            ExecutableCase(
                case_id=case_id,
                test_name=test_def.name,
                description=test_def.description,
                is_baseline=test_def.baseline,
                tags=list(test_def.tags),
                focus=test_def.focus_param,
                request=request,
                checks=checks,
                provider=suiteSpec.provider_id,
                model=suiteSpec.model_id,
                route=suiteSpec.route_id,
                api_family=suiteSpec.api_family,
            )
        )

    return cases


# ── Registry (immutable snapshot) ─────────────────────────


class Registry:
    """Immutable snapshot of the suite registry.

    Callers decide when to create / discard instances — core does not manage caching.

    - CLI/scripts: create once, use for the process lifetime.
    - Web backend: wrap in a caching layer (e.g. TTL + file-signature).
    - Tests: create fresh per test.
    """

    __slots__ = ("_suites",)

    def __init__(self, suites: dict[str, SuiteSpec]) -> None:
        self._suites = suites

    @classmethod
    def from_directory(cls, registry_dir: Path | str) -> Registry:
        """Parse registry files once and return an immutable snapshot."""
        specs = load_SuiteSpecs(registry_dir)
        return cls({s.suite_id: s for s in specs})

    # ── Query API ─────────────────────────────────────────

    def list_suites(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        route: str | None = None,
        endpoint: str | None = None,
    ) -> list[SuiteSpec]:
        suites = list(self._suites.values())
        if provider:
            suites = [s for s in suites if s.provider_id == provider]
        if model:
            suites = [s for s in suites if s.model_id == model]
        if route:
            suites = [s for s in suites if s.route_id == route]
        if endpoint:
            suites = [s for s in suites if s.endpoint == endpoint]
        return sorted(suites, key=lambda s: (s.provider_id, s.model_id, s.route_id))

    def get_suite(self, suite_id: str) -> SuiteSpec | None:
        return self._suites.get(suite_id)

    def get_execution_plan(
        self,
        suite_id: str,
        selected_tests: set[str] | None = None,
    ) -> list[ExecutableCase]:
        suite = self._suites.get(suite_id)
        if suite is None:
            raise KeyError(f"Suite not found: {suite_id}")
        return build_executable_cases(suite, selected_tests=selected_tests)

    @property
    def suite_ids(self) -> list[str]:
        return list(self._suites.keys())

    def __len__(self) -> int:
        return len(self._suites)

    def __contains__(self, suite_id: str) -> bool:
        return suite_id in self._suites
