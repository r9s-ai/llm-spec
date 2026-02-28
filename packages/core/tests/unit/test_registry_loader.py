from __future__ import annotations

from pathlib import Path

from llm_spec.registry import load_registry_suites


def test_registry_expands_openai_chat_model() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "openai" and s.route == "chat_completions" and s.model == "gpt-4o-mini"
    )
    assert match.suite_dict["provider"] == "openai"
    assert match.suite_dict["endpoint"] == "/v1/chat/completions"
    baseline = next(t for t in match.suite_dict["tests"] if t.get("baseline") is True)
    assert baseline["params"]["model"] == "gpt-4o-mini"


def test_registry_expands_gemini_endpoint_placeholder() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "gemini"
        and s.route == "generate_content"
        and s.model == "gemini-3-flash-preview"
    )
    assert "{model}" not in match.suite_dict["endpoint"]
    assert "gemini-3-flash-preview" in match.suite_dict["endpoint"]
    baseline = next(t for t in match.suite_dict["tests"] if t.get("baseline") is True)
    assert "model" not in baseline.get("params", {})


def test_registry_resolves_routes_from_inheritance() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    suites = load_registry_suites(repo_root / "suites-registry" / "providers")

    match = next(
        s
        for s in suites
        if s.provider == "xai" and s.route == "chat_completions" and s.model == "grok-beta"
    )
    assert match.api_family == "openai"
    assert match.suite_dict["endpoint"] == "/v1/chat/completions"
