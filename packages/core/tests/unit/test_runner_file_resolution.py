from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.runners.runner import ConfigDrivenTestRunner, SpecTestCase, SpecTestSuite


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


def _make_runner(tmp_path: Path) -> tuple[ConfigDrivenTestRunner, Path]:
    registry_root = tmp_path / "suites-registry"
    route_dir = registry_root / "providers" / "openai" / "routes"
    route_dir.mkdir(parents=True, exist_ok=True)
    config_path = route_dir / "chat_completions.json5"
    config_path.write_text("{}", encoding="utf-8")
    suite = SpecTestSuite(
        provider="openai",
        endpoint="/v1/chat/completions",
        config_path=config_path,
    )
    collector = EndpointResultBuilder(
        provider="openai",
        endpoint="/v1/chat/completions",
        base_url="https://api.openai.com",
    )
    runner = ConfigDrivenTestRunner(suite, MagicMock(), collector)
    return runner, registry_root


def test_asset_placeholder_base64_and_data_uri(tmp_path: Path) -> None:
    runner, registry_root = _make_runner(tmp_path)
    image = registry_root / "assets" / "images" / "tiny.bin"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"\x00\x01\x02")

    test = SpecTestCase(
        name="asset_placeholders",
        params={
            "raw": "$asset_base64(assets/images/tiny.bin)",
            "uri": "$asset_data_uri(assets/images/tiny.bin,application/octet-stream)",
        },
        test_param={"name": "raw", "value": "x"},
    )
    params = runner.build_params(test)
    expected_b64 = base64.b64encode(b"\x00\x01\x02").decode("ascii")
    assert params["raw"] == expected_b64
    assert params["uri"] == f"data:application/octet-stream;base64,{expected_b64}"


def test_asset_placeholder_missing_file_raises(tmp_path: Path) -> None:
    runner, _ = _make_runner(tmp_path)
    test = SpecTestCase(
        name="missing_asset",
        params={"raw": "$asset_base64(assets/images/not_exists.bin)"},
        test_param={"name": "raw", "value": "x"},
    )
    with pytest.raises(FileNotFoundError):
        runner.build_params(test)
