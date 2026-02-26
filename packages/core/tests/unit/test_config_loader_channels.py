from __future__ import annotations

from pathlib import Path

from llm_spec.config.loader import load_config


def test_load_config_supports_providers_and_channels(tmp_path: Path) -> None:
    config_file = tmp_path / "llm-spec.toml"
    config_file.write_text(
        """
[providers.openai]
api_key = "sk-openai"
base_url = "https://api.openai.com"
timeout = 30

[[channels]]
name = "proxy-a"
api_key = "sk-proxy"
base_url = "https://proxy.example.com"
timeout = 300

  [[channels.providers]]
  name = "openai"
  routes = ["chat_completions"]
  models = ["gpt-4o-mini"]
""".strip(),
        encoding="utf-8",
    )

    cfg = load_config(config_file)
    assert cfg.get_provider_config("openai").base_url == "https://api.openai.com"
    assert cfg.get_channel("proxy-a").base_url == "https://proxy.example.com"
    assert cfg.get_channel("proxy-a").providers[0].routes == ["chat_completions"]
