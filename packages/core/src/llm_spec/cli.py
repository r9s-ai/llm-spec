"""llm-spec minimal CLI.

This CLI is intentionally small:
- Discover suites from a directory (default: ./suites)
- Run suites against real providers using llm-spec.toml
- Write a cross-provider `run_result.json` and render run-level reports
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig, load_config
from llm_spec.logger import RequestLogger
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.report_types import ReportData
from llm_spec.reporting.run_result_formatter import RunResultFormatter
from llm_spec.runners import ConfigDrivenTestRunner, SpecTestSuite, load_test_suite


@dataclass(frozen=True)
class RunOptions:
    config_path: Path
    suites_dir: Path
    output_root: Path | None
    provider_filter: set[str] | None
    k: str | None


def _discover_suite_files(suites_dir: Path) -> list[Path]:
    if not suites_dir.exists():
        return []
    return sorted(p for p in suites_dir.rglob("*.json5") if p.is_file())


def _iter_selected_tests(suite: SpecTestSuite, k: str | None):
    endpoint_path = suite.endpoint.lstrip("/")
    for test in suite.tests:
        full_name = f"{suite.provider}/{endpoint_path}::{test.name}"
        if k and k not in full_name and k not in test.name:
            continue
        yield test, full_name


def _make_client(provider: str, app_config: AppConfig):
    provider_config = app_config.get_provider_config(provider)
    logger = RequestLogger(app_config.log)
    http_client = HTTPClient(default_timeout=provider_config.timeout)

    if provider == "openai":
        return OpenAIAdapter(provider_config, http_client, logger), http_client
    if provider == "anthropic":
        return AnthropicAdapter(provider_config, http_client, logger), http_client
    if provider == "gemini":
        return GeminiAdapter(provider_config, http_client, logger), http_client
    if provider == "xai":
        return XAIAdapter(provider_config, http_client, logger), http_client

    http_client.close()
    raise ValueError(f"Unknown provider: {provider}")


def _run_one_suite(
    suite: SpecTestSuite,
    *,
    client,
    k: str | None,
) -> tuple[bool, ReportData | None]:
    selected = list(_iter_selected_tests(suite, k))
    if not selected:
        return True, None

    collector = EndpointResultBuilder(
        provider=suite.provider,
        endpoint=suite.endpoint,
        base_url=client.get_base_url(),
    )
    runner = ConfigDrivenTestRunner(suite, client, collector, getattr(client, "logger", None))

    ok = True
    for test, full_name in selected:
        success = runner.run_test(test)
        if not success:
            ok = False
            print(f"FAIL {full_name}")
        else:
            print(f"PASS {full_name}")

    return ok, collector.build_report_data()


def _build_run_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    reports_by_provider: dict[str, list[ReportData]],
) -> dict:
    providers: list[dict] = []
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0

    for provider in sorted(reports_by_provider.keys()):
        endpoint_nodes: list[dict] = []
        provider_total = 0
        provider_passed = 0
        provider_failed = 0
        provider_skipped = 0
        provider_base_url = ""

        for report_data in reports_by_provider[provider]:
            summary = report_data.get("test_summary", {})
            endpoint_total = int(summary.get("total_tests", 0))
            endpoint_passed = int(summary.get("passed", 0))
            endpoint_failed = int(summary.get("failed", 0))
            endpoint_skipped = int(summary.get("skipped", 0))

            provider_total += endpoint_total
            provider_passed += endpoint_passed
            provider_failed += endpoint_failed
            provider_skipped += endpoint_skipped

            provider_base_url = provider_base_url or str(report_data.get("base_url", ""))
            endpoint_nodes.append(
                {
                    "endpoint": str(report_data.get("endpoint", "unknown")),
                    "tests": report_data.get("tests", []),
                    "summary": {
                        "total": endpoint_total,
                        "passed": endpoint_passed,
                        "failed": endpoint_failed,
                        "skipped": endpoint_skipped,
                    },
                }
            )

        total_tests += provider_total
        passed_tests += provider_passed
        failed_tests += provider_failed
        skipped_tests += provider_skipped

        providers.append(
            {
                "provider": provider,
                "base_url": provider_base_url,
                "endpoints": endpoint_nodes,
                "summary": {
                    "total": provider_total,
                    "passed": provider_passed,
                    "failed": provider_failed,
                    "skipped": provider_skipped,
                },
            }
        )

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "providers": providers,
        "summary": {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "skipped": skipped_tests,
        },
    }


def run_command(opts: RunOptions) -> int:
    try:
        app_config = load_config(opts.config_path)
    except FileNotFoundError:
        print(f"Config not found: {opts.config_path}", file=sys.stderr)
        return 2

    report_root = (
        opts.output_root
        if opts.output_root is not None
        else Path(app_config.report.output_dir)
        if getattr(app_config, "report", None)
        else Path("./reports")
    )
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_started_at = datetime.now(UTC).isoformat()
    output_dir = report_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    suite_files = _discover_suite_files(opts.suites_dir)
    if not suite_files:
        print(f"No suite configs found in: {opts.suites_dir}", file=sys.stderr)
        return 2

    clients: dict[str, tuple[object, HTTPClient]] = {}
    reports_by_provider: dict[str, list[ReportData]] = {}
    overall_ok = True

    try:
        for suite_path in suite_files:
            try:
                suite = load_test_suite(suite_path)
            except Exception as e:
                print(f"Skip {suite_path}: failed to load suite: {e}", file=sys.stderr)
                overall_ok = False
                continue
            if opts.provider_filter and suite.provider not in opts.provider_filter:
                continue

            if suite.provider not in clients:
                try:
                    clients[suite.provider] = _make_client(suite.provider, app_config)
                except KeyError:
                    print(
                        f"Skip {suite_path}: missing provider config [{suite.provider}].",
                        file=sys.stderr,
                    )
                    continue

            client, _http_client = clients[suite.provider]
            ok, report_data = _run_one_suite(
                suite,
                client=client,
                k=opts.k,
            )
            overall_ok = overall_ok and ok
            if report_data is not None:
                reports_by_provider.setdefault(suite.provider, []).append(report_data)

        run_finished_at = datetime.now(UTC).isoformat()
        run_result = _build_run_result(
            run_id=run_id,
            started_at=run_started_at,
            finished_at=run_finished_at,
            reports_by_provider=reports_by_provider,
        )
        run_result_path = output_dir / "run_result.json"
        with open(run_result_path, "w", encoding="utf-8") as f:
            json.dump(run_result, f, indent=2, ensure_ascii=False)

        formatter = RunResultFormatter(run_result)
        formatter.save_markdown(str(output_dir))
        formatter.save_html(str(output_dir))

    finally:
        for _provider, (_client, http_client) in clients.items():
            http_client.close()

    print(f"Reports: {output_dir}")
    return 0 if overall_ok else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-spec", description="LLM API compatibility test runner"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run suites against providers")
    run_p.add_argument("--config", default="llm-spec.toml", help="Path to llm-spec.toml")
    run_p.add_argument(
        "--suites", default="suites-registry/providers", help="Suite directory (JSON5)"
    )
    run_p.add_argument(
        "--output-root", default=None, help="Report root dir (default: config[report].output_dir)"
    )
    run_p.add_argument(
        "--provider", action="append", default=None, help="Only run a provider (repeatable)"
    )
    run_p.add_argument(
        "-k",
        dest="k",
        default=None,
        help='Substring filter (like pytest -k), matches "provider/endpoint::test_name"',
    )
    run_p.set_defaults(_subcmd="run")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args._subcmd == "run":
        opts = RunOptions(
            config_path=Path(args.config),
            suites_dir=Path(args.suites),
            output_root=Path(args.output_root) if args.output_root else None,
            provider_filter=set(args.provider) if args.provider else None,
            k=args.k,
        )
        return run_command(opts)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
