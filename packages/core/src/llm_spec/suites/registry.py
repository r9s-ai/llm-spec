"""Registry loader — expands (provider × model × route) into SuiteSpec list.

Also provides ``build_execution_plan()`` to convert a SuiteSpec into executable TestCase list.
"""

from __future__ import annotations

import copy
import hashlib
import tomllib
from pathlib import Path
from typing import Any

import json5

from .loader import (
    _raw_focus_to_focus_param,
    _raw_schemas_to_schema_ref,
    load_route_from_dict,
)
from .types import (
    ExtraTestDef,
    HttpRequest,
    ModelSpec,
    ProviderSpec,
    SchemaRef,
    SuiteSpec,
    TestCase,
    ValidationSpec,
)

# ── Deterministic suite ID ────────────────────────────────


def _suite_id(provider: str, model: str, route: str) -> str:
    """Deterministic short hash from (provider, model, route)."""
    key = f"suite:{provider}:{model}:{route}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


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


def _load_local_routes(provider_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    routes_dir = provider_dir / "routes"
    route_files: list[Path] = []
    if routes_dir.exists():
        route_files = sorted(p for p in routes_dir.rglob("*.json5") if p.is_file())
    else:
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


def _load_model_specs(provider_dir: Path) -> dict[str, ModelSpec]:
    model_dir = provider_dir / "models"
    if not model_dir.exists():
        return {}
    models: dict[str, ModelSpec] = {}
    for model_path in sorted(model_dir.glob("*.toml")):
        data = tomllib.loads(model_path.read_text(encoding="utf-8"))
        model_id = model_path.stem

        if "skip_tests" in data:
            raise ValueError(
                f"models/{model_id}.toml uses deprecated 'skip_tests'. "
                "Use 'include_tests' and/or 'exclude_tests'."
            )
        if "base_params_override" in data:
            raise ValueError(
                f"models/{model_id}.toml uses deprecated [base_params_override]. "
                "Use [baseline_params_override]."
            )

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

        extra_tests: list[ExtraTestDef] = []
        for extra in data.get("extra_tests", []) or []:
            if not isinstance(extra, dict):
                continue
            raw_focus = extra.get("focus_param")
            extra_tests.append(
                ExtraTestDef(
                    route=str(extra.get("route", "")),
                    name=str(extra.get("name", "")),
                    description=str(extra.get("description", "")),
                    params=extra.get("params", {}),
                    focus_param=_raw_focus_to_focus_param(raw_focus) if raw_focus else None,
                    baseline=bool(extra.get("baseline", False)),
                    check_stream=bool(extra.get("check_stream", False)),
                    stream_rules=extra.get("stream_rules") or extra.get("stream_expectations"),
                    endpoint_override=extra.get("endpoint_override"),
                    files=extra.get("files"),
                    schemas=_raw_schemas_to_schema_ref(extra.get("schemas")),
                    required_fields=extra.get("required_fields"),
                    method=extra.get("method"),
                    tags=list(extra.get("tags", []) or []),
                )
            )

        models[model_id] = ModelSpec(
            model_id=model_id,
            routes=[str(r) for r in routes_raw],
            include_tests=include_tests,
            exclude_tests=exclude_tests,
            baseline_params_override=data.get("baseline_params_override", {}) or {},
            extra_tests=extra_tests,
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


def _resolve_routes_for_provider(
    provider: str,
    provider_dirs: dict[str, Path],
    specs: dict[str, ProviderSpec],
    cache: dict[str, dict[str, tuple[Path, dict[str, Any]]]],
    stack: list[str],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    if provider in cache:
        return cache[provider]

    if provider in stack:
        chain = " -> ".join([*stack, provider])
        raise ValueError(f"Circular routes_from detected: {chain}")

    provider_dir = provider_dirs[provider]
    spec = specs[provider]

    merged: dict[str, tuple[Path, dict[str, Any]]] = {}
    if spec.routes_from:
        parent = spec.routes_from
        if parent not in provider_dirs:
            raise ValueError(f"routes_from '{parent}' not found for provider '{provider}'")
        merged.update(
            _resolve_routes_for_provider(
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


def load_registry_suites(
    registry_dir: Path | str = "suites-registry/providers",
) -> list[SuiteSpec]:
    """Load and expand registry into a list of SuiteSpec objects."""
    registry_dir = Path(registry_dir)
    if not registry_dir.exists():
        return []

    provider_dirs = {
        p.name: p
        for p in sorted(registry_dir.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    }
    specs = {name: _load_provider_spec(path) for name, path in provider_dirs.items()}

    route_cache: dict[str, dict[str, tuple[Path, dict[str, Any]]]] = {}
    expanded: list[SuiteSpec] = []

    for provider, provider_dir in provider_dirs.items():
        provider_spec = specs[provider]
        api_family = provider_spec.api_family or provider
        model_specs = _load_model_specs(provider_dir)

        routes = _resolve_routes_for_provider(
            provider,
            provider_dirs=provider_dirs,
            specs=specs,
            cache=route_cache,
            stack=[],
        )

        for model_id, model_spec in model_specs.items():
            for route_name in model_spec.routes:
                route_name = str(route_name)
                if route_name not in routes:
                    raise ValueError(
                        f"Provider '{provider}' model '{model_id}' references unknown route '{route_name}'"
                    )
                route_path, route_payload = routes[route_name]
                suite_dict = copy.deepcopy(route_payload)
                suite_dict["provider"] = provider

                # Gemini model placeholder in endpoint
                endpoint = str(suite_dict.get("endpoint", ""))
                if api_family == "gemini":
                    endpoint = endpoint.replace("{model}", model_id)
                suite_dict["endpoint"] = endpoint

                # Collect all tests (route tests + model extra tests)
                raw_tests: list[dict[str, Any]] = []
                for test in suite_dict.get("tests", []):
                    if isinstance(test, dict):
                        raw_tests.append(test)

                for extra in model_spec.extra_tests:
                    if extra.route != route_name:
                        continue
                    raw_tests.append(
                        {
                            "name": extra.name,
                            "description": extra.description,
                            "params": copy.deepcopy(extra.params),
                            "focus_param": (
                                {"name": extra.focus_param.name, "value": extra.focus_param.value}
                                if extra.focus_param
                                else None
                            ),
                            "baseline": extra.baseline,
                            "check_stream": extra.check_stream,
                            "stream_rules": extra.stream_rules,
                            "endpoint_override": extra.endpoint_override,
                            "files": extra.files,
                            "schemas": (
                                {
                                    k: v
                                    for k, v in [
                                        ("response", extra.schemas.response),
                                        ("stream_chunk", extra.schemas.stream_chunk),
                                    ]
                                    if v is not None
                                }
                                if extra.schemas
                                else None
                            ),
                            "required_fields": extra.required_fields,
                            "method": extra.method,
                            "tags": extra.tags,
                        }
                    )

                # Filter by include/exclude
                include_set = set(model_spec.include_tests) if model_spec.include_tests else None
                exclude_set = set(model_spec.exclude_tests) if model_spec.exclude_tests else set()

                filtered_tests: list[dict[str, Any]] = []
                for test in raw_tests:
                    name = str(test.get("name", ""))
                    if include_set is not None and name not in include_set:
                        continue
                    if name and name in exclude_set:
                        continue
                    filtered_tests.append(test)

                # Validate exactly one baseline
                baseline_tests = [t for t in filtered_tests if t.get("baseline") is True]
                if len(baseline_tests) != 1:
                    raise ValueError(
                        f"Provider '{provider}' model '{model_id}' route '{route_name}' must "
                        f"have exactly one baseline test after expansion, got {len(baseline_tests)}"
                    )

                # Inject model into baseline params
                baseline = baseline_tests[0]
                baseline_params = copy.deepcopy(baseline.get("params", {}))
                if not isinstance(baseline_params, dict):
                    baseline_params = {}
                if api_family == "gemini":
                    baseline_params.pop("model", None)
                else:
                    baseline_params["model"] = model_id
                baseline_params = _deep_merge(baseline_params, model_spec.baseline_params_override)
                baseline["params"] = baseline_params

                # Put filtered tests back and run through loader for variant expansion
                suite_dict["tests"] = filtered_tests
                route_spec = load_route_from_dict(
                    suite_dict, route_id=route_name, source_path=route_path
                )

                # Build suite-level SchemaRef
                suite_schemas = route_spec.schemas

                expanded.append(
                    SuiteSpec(
                        suite_id=_suite_id(provider, model_id, route_name),
                        suite_name=f"{provider}/{model_id}/{route_name}",
                        provider_id=provider,
                        model_id=model_id,
                        route_id=route_name,
                        api_family=api_family,
                        endpoint=route_spec.endpoint,
                        method=route_spec.method,
                        provider_headers=copy.deepcopy(provider_spec.headers),
                        schemas=suite_schemas,
                        required_fields=route_spec.required_fields,
                        stream_rules=route_spec.stream_rules,
                        baseline_params=baseline_params,
                        tests=route_spec.tests,
                        source_path=route_path,
                    )
                )

    return expanded


# ── Execution plan builder ────────────────────────────────


def build_execution_plan(
    suite: SuiteSpec,
    selected_tests: set[str] | None = None,
) -> list[TestCase]:
    """Convert a SuiteSpec into a list of executable TestCase objects.

    Args:
        suite: The expanded suite specification.
        selected_tests: If given, only include tests whose names are in this set.
                        If None, include all tests.

    Returns:
        List of self-contained TestCase objects ready for execution.
    """
    cases: list[TestCase] = []

    for test_def in suite.tests:
        if selected_tests is not None and test_def.name not in selected_tests:
            continue

        # Merge params: baseline + test overrides
        merged_params = copy.deepcopy(suite.baseline_params)
        merged_params.update(copy.deepcopy(test_def.params))

        # Resolve endpoint
        endpoint = test_def.endpoint_override or suite.endpoint
        method = test_def.method or suite.method

        # Build HttpRequest
        request = HttpRequest(
            method=method,
            endpoint=endpoint,
            params=merged_params,
            headers=copy.deepcopy(suite.provider_headers),
            files=copy.deepcopy(test_def.files) if test_def.files else None,
            stream=test_def.check_stream,
        )

        # Build ValidationSpec: test-level overrides > suite-level defaults
        test_schemas = test_def.schemas or SchemaRef()
        response_schema = test_schemas.response or suite.schemas.response
        stream_chunk_schema = test_schemas.stream_chunk or suite.schemas.stream_chunk

        # Required fields: suite-level + test-level
        all_required_fields = list(suite.required_fields)
        if test_def.required_fields:
            all_required_fields.extend(test_def.required_fields)

        checks = ValidationSpec(
            response_schema=response_schema,
            stream_chunk_schema=stream_chunk_schema,
            required_fields=all_required_fields,
            stream_rules=test_def.stream_rules or suite.stream_rules,
        )

        case_id = f"{suite.provider_id}:{suite.model_id}:{suite.route_id}:{test_def.name}"

        cases.append(
            TestCase(
                case_id=case_id,
                test_name=test_def.name,
                description=test_def.description,
                is_baseline=test_def.baseline,
                tags=list(test_def.tags),
                focus=test_def.focus_param,
                request=request,
                checks=checks,
                provider=suite.provider_id,
                model=suite.model_id,
                route=suite.route_id,
                api_family=suite.api_family,
            )
        )

    return cases
