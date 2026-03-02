from __future__ import annotations

from pathlib import Path

import pytest

from llm_spec.suites.registry import load_registry_suites


def test_registry_expands_openai_chat_model() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "openai"
        and s.route_suite.get("route") == "chat_completions"
        and s.model_name == "gpt-4o-mini"
    )
    assert match.route_suite["provider"] == "openai"
    assert match.route_suite["endpoint"] == "/v1/chat/completions"
    baseline = next(t for t in match.route_suite["tests"] if t.get("baseline") is True)
    assert baseline["params"]["model"] == "gpt-4o-mini"


def test_registry_expands_gemini_endpoint_placeholder() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "gemini"
        and s.route_suite.get("route") == "generate_content"
        and s.model_name == "gemini-3-flash-preview"
    )
    assert "{model}" not in match.route_suite["endpoint"]
    assert "gemini-3-flash-preview" in match.route_suite["endpoint"]
    baseline = next(t for t in match.route_suite["tests"] if t.get("baseline") is True)
    assert "model" not in baseline.get("params", {})


def test_registry_resolves_routes_from_inheritance() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "xai"
        and s.route_suite.get("route") == "chat_completions"
        and s.model_name == "grok-beta"
    )
    assert match.route_suite["api_family"] == "openai"
    assert match.route_suite["endpoint"] == "/v1/chat/completions"


def test_registry_filters_tests_with_include_and_exclude(tmp_path: Path) -> None:
    providers_dir = tmp_path / "providers"
    provider_dir = providers_dir / "demo"
    routes_dir = provider_dir / "routes"
    models_dir = provider_dir / "models"
    routes_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)

    (provider_dir / "provider.toml").write_text('api_family = "openai"\n', encoding="utf-8")
    (routes_dir / "chat.json5").write_text(
        """
        {
          endpoint: "/v1/chat/completions",
          tests: [
            { name: "baseline", baseline: true, params: { messages: [{ role: "user", content: "hi" }] } },
            { name: "temperature", params: { temperature: 0.7 }, focus_param: { name: "temperature", value: 0.7 } },
            { name: "top_p", params: { top_p: 0.9 }, focus_param: { name: "top_p", value: 0.9 } },
          ],
        }
        """,
        encoding="utf-8",
    )
    (models_dir / "demo-model.toml").write_text(
        """
        name = "demo-model"
        routes = ["chat"]
        include_tests = ["baseline", "temperature", "extra_kept"]
        exclude_tests = ["temperature"]

        [[extra_tests]]
        route = "chat"
        name = "extra_kept"
        params = { user = "u1" }
        focus_param = { name = "user", value = "u1" }

        [[extra_tests]]
        route = "chat"
        name = "extra_dropped"
        params = { user = "u2" }
        focus_param = { name = "user", value = "u2" }
        """,
        encoding="utf-8",
    )

    suites = load_registry_suites(providers_dir)
    assert len(suites) == 1
    tests = suites[0].route_suite["tests"]
    test_names = [str(t.get("name", "")) for t in tests]
    assert test_names == ["baseline", "extra_kept"]


def test_registry_rejects_legacy_skip_tests(tmp_path: Path) -> None:
    providers_dir = tmp_path / "providers"
    provider_dir = providers_dir / "demo"
    routes_dir = provider_dir / "routes"
    models_dir = provider_dir / "models"
    routes_dir.mkdir(parents=True)
    models_dir.mkdir(parents=True)

    (provider_dir / "provider.toml").write_text('api_family = "openai"\n', encoding="utf-8")
    (routes_dir / "chat.json5").write_text(
        """
        {
          endpoint: "/v1/chat/completions",
          tests: [
            { name: "baseline", baseline: true, params: { messages: [{ role: "user", content: "hi" }] } },
          ],
        }
        """,
        encoding="utf-8",
    )
    (models_dir / "demo-model.toml").write_text(
        """
        name = "demo-model"
        routes = ["chat"]
        skip_tests = ["temperature"]
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deprecated 'skip_tests'"):
        load_registry_suites(providers_dir)
