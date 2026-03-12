from __future__ import annotations

from pathlib import Path

from llm_spec.suites.registry import load_SuiteSpecs


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "suites-registry").exists():
            return parent
    raise RuntimeError("repo root not found for suites-registry")


def test_registry_expands_openai_chat_model() -> None:
    repo_root = _repo_root()
    suites = load_SuiteSpecs(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider_id == "openai"
        and s.route_id == "chat_completions"
        and s.model_id == "gpt-4o-mini"
    )
    assert match.endpoint == "/v1/chat/completions"
    baseline = next(t for t in match.tests if t.baseline is True)
    assert baseline.params["model"] == "gpt-4o-mini"


def test_registry_expands_gemini_endpoint_placeholder() -> None:
    repo_root = _repo_root()
    suites = load_SuiteSpecs(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider_id == "gemini"
        and s.route_id == "generate_content"
        and s.model_id == "gemini-3-flash-preview"
    )
    assert "{model}" not in match.endpoint
    assert "gemini-3-flash-preview" in match.endpoint
    baseline = next(t for t in match.tests if t.baseline is True)
    assert "model" not in baseline.params


def test_registry_resolves_routes_from_inheritance() -> None:
    repo_root = _repo_root()
    suites = load_SuiteSpecs(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider_id == "xai" and s.route_id == "chat_completions" and s.model_id == "grok-beta"
    )
    assert match.api_family == "openai"
    assert match.endpoint == "/v1/chat/completions"


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
        include_tests = ["baseline", "temperature", "top_p"]
        exclude_tests = ["temperature"]
        """,
        encoding="utf-8",
    )

    suites = load_SuiteSpecs(providers_dir)
    assert len(suites) == 1
    test_names = [t.name for t in suites[0].tests]
    assert test_names == ["baseline", "top_p"]
