from llm_spec.adapters.api_family import APIFamilyAdapter, create_api_family_adapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import ProviderConfig


def test_openai_headers_use_bearer_auth() -> None:
    config = ProviderConfig(
        api_key="sk-test",
        base_url="https://api.openai.com",
        headers={"x-extra": "cfg"},
    )
    adapter = APIFamilyAdapter(config=config, http_client=HTTPClient(), api_family="openai")

    headers = adapter.prepare_headers({"x-extra": "runtime"})

    assert headers["Authorization"] == "Bearer sk-test"
    assert headers["Content-Type"] == "application/json"
    assert headers["x-extra"] == "runtime"


def test_anthropic_headers_use_x_api_key_and_version() -> None:
    config = ProviderConfig(
        api_key="sk-ant-test",
        base_url="https://api.anthropic.com",
    )
    adapter = APIFamilyAdapter(config=config, http_client=HTTPClient(), api_family="anthropic")

    headers = adapter.prepare_headers()

    assert headers["x-api-key"] == "sk-ant-test"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["Content-Type"] == "application/json"


def test_create_api_family_adapter_prefers_config_api_family() -> None:
    config = ProviderConfig(
        api_key="sk-test",
        base_url="https://proxy.example.com",
        api_family="gemini",
    )

    adapter = create_api_family_adapter(
        provider="custom-provider", config=config, http_client=HTTPClient()
    )
    headers = adapter.prepare_headers()

    assert headers["x-goog-api-key"] == "sk-test"


def test_unsupported_api_family_raises_value_error() -> None:
    config = ProviderConfig(
        api_key="k",
        base_url="https://example.com",
    )
    adapter = APIFamilyAdapter(config=config, http_client=HTTPClient(), api_family="unknown")

    try:
        adapter.prepare_headers()
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Unsupported api_family" in str(exc)
