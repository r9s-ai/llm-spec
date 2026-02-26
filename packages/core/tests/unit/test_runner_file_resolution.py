from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.runners.runner import ConfigDrivenTestRunner, SpecTestSuite


def test_file_resolution_prefers_registry_root_assets(tmp_path: Path) -> None:
    registry_root = tmp_path / "suites-registry"
    route_dir = registry_root / "providers" / "openai" / "routes"
    route_dir.mkdir(parents=True, exist_ok=True)
    config_path = route_dir / "images_edits.json5"
    config_path.write_text("{}", encoding="utf-8")

    asset_path = registry_root / "assets" / "images" / "test.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"png")

    suite = SpecTestSuite(
        provider="openai",
        endpoint="/v1/images/edits",
        config_path=config_path,
    )
    collector = EndpointResultBuilder(
        provider="openai",
        endpoint="/v1/images/edits",
        base_url="https://api.openai.com",
    )
    client = MagicMock()
    runner = ConfigDrivenTestRunner(suite, client, collector)

    resolved = runner._resolve_test_file_path("assets/images/test.png")
    assert resolved == asset_path
