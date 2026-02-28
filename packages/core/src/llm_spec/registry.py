"""Registry loader for suites-registry provider/route/model layout."""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import json5


@dataclass(frozen=True)
class ProviderMeta:
    """Provider-level registry metadata."""

    provider: str
    api_family: str
    routes_from: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpandedSuite:
    """A fully expanded suite from route × model."""

    provider: str
    api_family: str
    route: str
    model: str
    source_route_path: Path
    suite_dict: dict[str, Any]
    provider_headers: dict[str, str] = field(default_factory=dict)


def _read_json5(path: Path) -> dict[str, Any]:
    data = json5.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Route file must be an object: {path}")
    return data


def _load_provider_meta(provider_dir: Path) -> ProviderMeta:
    provider = provider_dir.name
    provider_toml = provider_dir / "provider.toml"
    if not provider_toml.exists():
        return ProviderMeta(provider=provider, api_family=provider)

    data = tomllib.loads(provider_toml.read_text(encoding="utf-8"))
    headers = data.get("headers", {})
    if headers is None:
        headers = {}
    if not isinstance(headers, dict):
        raise ValueError(f"[headers] must be a table in {provider_toml}")
    return ProviderMeta(
        provider=provider,
        api_family=str(data.get("api_family") or provider),
        routes_from=str(data["routes_from"]) if data.get("routes_from") else None,
        headers={str(k): str(v) for k, v in headers.items()},
    )


def _load_local_routes(provider_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    routes_dir = provider_dir / "routes"
    route_files: list[Path] = []
    if routes_dir.exists():
        route_files = sorted(p for p in routes_dir.rglob("*.json5") if p.is_file())
    else:
        # Legacy fallback: *.json5 directly under provider dir.
        route_files = sorted(p for p in provider_dir.glob("*.json5") if p.is_file())

    routes: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in route_files:
        route_name = path.stem
        payload = copy.deepcopy(_read_json5(path))
        payload.pop("provider", None)
        if "base_params" in payload:
            raise ValueError(
                f"Route '{path}' uses deprecated 'base_params'. "
                "Move defaults into tests[].baseline.params."
            )
        routes[route_name] = (path, payload)
    return routes


def _load_models(provider_dir: Path) -> dict[str, dict[str, Any]]:
    model_dir = provider_dir / "models"
    if not model_dir.exists():
        return {}
    models: dict[str, dict[str, Any]] = {}
    for model_path in sorted(model_dir.glob("*.toml")):
        data = tomllib.loads(model_path.read_text(encoding="utf-8"))
        model_id = model_path.stem
        models[model_id] = data
    return models


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_routes_for_provider(
    provider: str,
    provider_dirs: dict[str, Path],
    metas: dict[str, ProviderMeta],
    cache: dict[str, dict[str, tuple[Path, dict[str, Any]]]],
    stack: list[str],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    if provider in cache:
        return cache[provider]

    if provider in stack:
        chain = " -> ".join([*stack, provider])
        raise ValueError(f"Circular routes_from detected: {chain}")

    provider_dir = provider_dirs[provider]
    meta = metas[provider]

    merged: dict[str, tuple[Path, dict[str, Any]]] = {}
    if meta.routes_from:
        parent = meta.routes_from
        if parent not in provider_dirs:
            raise ValueError(f"routes_from '{parent}' not found for provider '{provider}'")
        merged.update(
            _resolve_routes_for_provider(
                parent,
                provider_dirs=provider_dirs,
                metas=metas,
                cache=cache,
                stack=[*stack, provider],
            )
        )

    merged.update(_load_local_routes(provider_dir))
    cache[provider] = merged
    return merged


def load_registry_suites(
    registry_dir: Path | str = "suites-registry/providers",
) -> list[ExpandedSuite]:
    """Load and expand route×model suites from registry layout."""
    registry_dir = Path(registry_dir)
    if not registry_dir.exists():
        return []

    provider_dirs = {
        p.name: p
        for p in sorted(registry_dir.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    }
    metas = {name: _load_provider_meta(path) for name, path in provider_dirs.items()}

    route_cache: dict[str, dict[str, tuple[Path, dict[str, Any]]]] = {}
    expanded: list[ExpandedSuite] = []

    for provider, provider_dir in provider_dirs.items():
        meta = metas[provider]
        models = _load_models(provider_dir)

        routes = _resolve_routes_for_provider(
            provider,
            provider_dirs=provider_dirs,
            metas=metas,
            cache=route_cache,
            stack=[],
        )

        for model_id, model_data in models.items():
            routes_for_model = model_data.get("routes", [])
            if not isinstance(routes_for_model, list):
                raise ValueError(f"models/{model_id}.toml routes must be a list")
            skip_tests = set(model_data.get("skip_tests", []) or [])
            if "baseline" in skip_tests:
                raise ValueError(
                    f"models/{model_id}.toml cannot skip baseline test; baseline is required."
                )
            if "base_params_override" in model_data:
                raise ValueError(
                    f"models/{model_id}.toml uses deprecated [base_params_override]. "
                    "Use [baseline_params_override]."
                )
            baseline_params_override = model_data.get("baseline_params_override", {}) or {}
            extra_tests = model_data.get("extra_tests", []) or []

            for route_name in routes_for_model:
                route_name = str(route_name)
                if route_name not in routes:
                    raise ValueError(
                        f"Provider '{provider}' model '{model_id}' references unknown route '{route_name}'"
                    )
                route_path, route_payload = routes[route_name]
                suite = copy.deepcopy(route_payload)
                suite["provider"] = provider

                endpoint = str(suite.get("endpoint", ""))
                if meta.api_family == "gemini":
                    endpoint = endpoint.replace("{model}", model_id)
                suite["endpoint"] = endpoint

                tests = suite.get("tests", [])
                if not isinstance(tests, list):
                    tests = []
                filtered_tests = []
                for test in tests:
                    if not isinstance(test, dict):
                        continue
                    name = str(test.get("name", ""))
                    if name and name in skip_tests:
                        continue
                    filtered_tests.append(test)

                for extra in extra_tests:
                    if not isinstance(extra, dict):
                        continue
                    if str(extra.get("route", "")) != route_name:
                        continue
                    extra_test = {k: copy.deepcopy(v) for k, v in extra.items() if k != "route"}
                    filtered_tests.append(extra_test)

                baseline_tests = [
                    t for t in filtered_tests if isinstance(t, dict) and t.get("baseline") is True
                ]
                if len(baseline_tests) != 1:
                    raise ValueError(
                        f"Provider '{provider}' model '{model_id}' route '{route_name}' must "
                        f"have exactly one baseline test after expansion, got {len(baseline_tests)}"
                    )

                baseline = baseline_tests[0]
                baseline_params = baseline.get("params", {})
                if not isinstance(baseline_params, dict):
                    baseline_params = {}
                baseline_params = copy.deepcopy(baseline_params)
                if meta.api_family == "gemini":
                    baseline_params.pop("model", None)
                else:
                    baseline_params["model"] = model_id
                baseline_params = _deep_merge(baseline_params, baseline_params_override)
                baseline["params"] = baseline_params

                suite["tests"] = filtered_tests
                expanded.append(
                    ExpandedSuite(
                        provider=provider,
                        api_family=meta.api_family,
                        route=route_name,
                        model=model_id,
                        source_route_path=route_path,
                        suite_dict=suite,
                        provider_headers=meta.headers,
                    )
                )

    return expanded
