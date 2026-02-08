"""llm-spec minimal CLI.

This CLI is intentionally small:
- Discover suites from a directory (default: ./suites)
- Run suites against real providers using llm-spec.toml
- Write per-endpoint reports, and optional per-provider aggregated reports
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from llm_spec.adapters.anthropic import AnthropicAdapter
from llm_spec.adapters.gemini import GeminiAdapter
from llm_spec.adapters.openai import OpenAIAdapter
from llm_spec.adapters.xai import XAIAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig, load_config
from llm_spec.logger import RequestLogger
from llm_spec.reporting.aggregator import AggregatedReportCollector
from llm_spec.reporting.collector import ReportCollector
from llm_spec.runners import ConfigDrivenTestRunner, SpecTestSuite, load_test_suite


@dataclass(frozen=True)
class RunOptions:
    config_path: Path
    suites_dir: Path
    output_root: Path | None
    provider_filter: set[str] | None
    k: str | None
    dry_run: bool
    fail_fast: bool
    aggregate: bool


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
    suite_path: Path,
    suite: SpecTestSuite,
    *,
    client,
    output_dir: Path,
    k: str | None,
    dry_run: bool,
    fail_fast: bool,
) -> tuple[bool, Path | None]:
    selected = list(_iter_selected_tests(suite, k))
    if not selected:
        return True, None

    if dry_run:
        for _test, full_name in selected:
            print(full_name)
        return True, None

    collector = ReportCollector(
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
            if fail_fast:
                break
        else:
            print(f"PASS {full_name}")

    report_json_path = Path(collector.finalize(str(output_dir)))
    return ok, report_json_path


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
    output_dir = report_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    suite_files = _discover_suite_files(opts.suites_dir)
    if not suite_files:
        print(f"No suite configs found in: {opts.suites_dir}", file=sys.stderr)
        return 2

    clients: dict[str, tuple[object, HTTPClient]] = {}
    report_files_by_provider: dict[str, list[Path]] = {}
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
            ok, report_path = _run_one_suite(
                suite_path,
                suite,
                client=client,
                output_dir=output_dir,
                k=opts.k,
                dry_run=opts.dry_run,
                fail_fast=opts.fail_fast,
            )
            overall_ok = overall_ok and ok
            if report_path is not None:
                report_files_by_provider.setdefault(suite.provider, []).append(report_path)

        if opts.dry_run:
            return 0

        if opts.aggregate:
            for provider, report_files in report_files_by_provider.items():
                if len(report_files) <= 1:
                    continue
                aggregator = AggregatedReportCollector(provider)
                aggregator.merge_reports(report_files)
                aggregator.finalize(str(output_dir))

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
    run_p.add_argument("--suites", default="suites", help="Suite directory (JSON5)")
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
    run_p.add_argument(
        "--dry-run", action="store_true", help="Only list selected tests, do not run"
    )
    run_p.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    run_p.add_argument("--no-aggregate", action="store_true", help="Disable aggregated reports")
    run_p.set_defaults(_subcmd="run")

    list_p = sub.add_parser("list", help="List all tests discoverable from suites")
    list_p.add_argument("--suites", default="suites", help="Suite directory (JSON5)")
    list_p.add_argument(
        "--provider", action="append", default=None, help="Only list a provider (repeatable)"
    )
    list_p.add_argument(
        "-k",
        dest="k",
        default=None,
        help='Substring filter (like pytest -k), matches "provider/endpoint::test_name"',
    )
    list_p.set_defaults(_subcmd="list")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args._subcmd == "list":
        suites_dir = Path(args.suites)
        provider_filter = set(args.provider) if args.provider else None
        suite_files = _discover_suite_files(suites_dir)
        for suite_path in suite_files:
            try:
                suite = load_test_suite(suite_path)
            except Exception as e:
                print(f"Skip {suite_path}: failed to load suite: {e}", file=sys.stderr)
                continue
            if provider_filter and suite.provider not in provider_filter:
                continue
            for _test, full_name in _iter_selected_tests(suite, args.k):
                print(full_name)
        return 0

    if args._subcmd == "run":
        opts = RunOptions(
            config_path=Path(args.config),
            suites_dir=Path(args.suites),
            output_root=Path(args.output_root) if args.output_root else None,
            provider_filter=set(args.provider) if args.provider else None,
            k=args.k,
            dry_run=bool(args.dry_run),
            fail_fast=bool(args.fail_fast),
            aggregate=not bool(args.no_aggregate),
        )
        return run_command(opts)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
