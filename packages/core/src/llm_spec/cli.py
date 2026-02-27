"""llm-spec CLI."""

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
from llm_spec.config.loader import AppConfig, ProviderConfig, load_config
from llm_spec.logger import RequestLogger
from llm_spec.registry import load_registry_suites
from llm_spec.reporting.collector import EndpointResultBuilder
from llm_spec.reporting.report_types import ReportData
from llm_spec.reporting.run_result_formatter import RunResultFormatter
from llm_spec.runners import ConfigDrivenTestRunner
from llm_spec.suites import SpecTestSuite, load_test_suite_from_dict


@dataclass(frozen=True)
class RunOptions:
    config_path: Path
    suites_dir: Path
    output_root: Path | None
    provider_filter: set[str] | None
    channel: str | None
    model_filter: set[str] | None
    tags: set[str] | None
    exclude_tags: set[str] | None
    k: str | None


@dataclass(frozen=True)
class SuiteTarget:
    suite: SpecTestSuite
    provider: str
    route: str
    model: str
    api_family: str
    provider_headers: dict[str, str]


_ADAPTERS: dict[str, type] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "xai": XAIAdapter,
}


def _discover_suites(suites_dir: Path) -> list[SuiteTarget]:
    suites = load_registry_suites(suites_dir)
    resolved: list[SuiteTarget] = []
    for item in suites:
        suite = load_test_suite_from_dict(item.suite_dict, item.source_route_path)
        resolved.append(
            SuiteTarget(
                suite=suite,
                provider=item.provider,
                route=item.route,
                model=item.model,
                api_family=item.api_family,
                provider_headers=item.provider_headers,
            )
        )
    return resolved


def _iter_selected_tests(
    target: SuiteTarget,
    *,
    k: str | None,
    include_tags: set[str] | None,
    exclude_tags: set[str] | None,
):
    endpoint_path = target.suite.endpoint.lstrip("/")
    for test in target.suite.tests:
        full_name = f"{target.provider}/{target.model}/{endpoint_path}::{test.name}"
        if k and k not in full_name and k not in test.name:
            continue
        test_tags = set(test.tags or [])
        if include_tags and test_tags.isdisjoint(include_tags):
            continue
        if exclude_tags and not test_tags.isdisjoint(exclude_tags):
            continue
        yield test, full_name


def _make_client(
    *,
    provider: str,
    api_family: str,
    provider_config: ProviderConfig,
    app_config: AppConfig,
):
    logger = RequestLogger(app_config.log)
    http_client = HTTPClient(default_timeout=provider_config.timeout)
    adapter_cls = _ADAPTERS.get(api_family)
    if adapter_cls is None:
        http_client.close()
        raise ValueError(f"Unknown api_family '{api_family}' for provider '{provider}'")
    return adapter_cls(provider_config, http_client, logger), http_client


def _run_one_suite(
    target: SuiteTarget,
    *,
    client,
    k: str | None,
    include_tags: set[str] | None,
    exclude_tags: set[str] | None,
) -> tuple[bool, ReportData | None]:
    selected = list(
        _iter_selected_tests(
            target,
            k=k,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )
    )
    if not selected:
        return True, None

    collector = EndpointResultBuilder(
        provider=target.suite.provider,
        endpoint=target.suite.endpoint,
        base_url=client.get_base_url(),
    )
    runner = ConfigDrivenTestRunner(
        target.suite, client, collector, getattr(client, "logger", None)
    )

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

    discovered = _discover_suites(opts.suites_dir)
    if not discovered:
        print(f"No suite configs found in: {opts.suites_dir}", file=sys.stderr)
        return 2

    channel_cfg = None
    if opts.channel:
        try:
            channel_cfg = app_config.get_channel(opts.channel)
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 2

    clients: dict[str, tuple[object, HTTPClient]] = {}
    reports_by_provider: dict[str, list[ReportData]] = {}
    overall_ok = True

    channel_provider_limits: dict[str, tuple[set[str], set[str]]] = {}
    if channel_cfg:
        for cp in channel_cfg.providers:
            channel_provider_limits[cp.name] = (set(cp.routes), set(cp.models))

    try:
        for target in discovered:
            provider = target.provider
            if opts.provider_filter and provider not in opts.provider_filter:
                continue
            if opts.model_filter and target.model not in opts.model_filter:
                continue

            if channel_cfg:
                limits = channel_provider_limits.get(provider)
                if limits is None:
                    continue
                route_limit, model_limit = limits
                if route_limit and target.route not in route_limit:
                    continue
                if model_limit and target.model not in model_limit:
                    continue
                provider_config = ProviderConfig(
                    api_key=channel_cfg.api_key,
                    base_url=channel_cfg.base_url,
                    timeout=channel_cfg.timeout,
                    api_family=target.api_family,
                    headers=target.provider_headers,
                    channel=channel_cfg.name,
                )
                client_key = f"{channel_cfg.name}:{provider}:{target.api_family}"
            else:
                try:
                    base_config = app_config.get_provider_config(provider)
                except KeyError:
                    print(
                        f"Skip {provider}/{target.route}/{target.model}: missing provider config [{provider}].",
                        file=sys.stderr,
                    )
                    continue
                provider_config = ProviderConfig(
                    api_key=base_config.api_key,
                    base_url=base_config.base_url,
                    timeout=base_config.timeout,
                    api_family=base_config.api_family or target.api_family,
                    headers=target.provider_headers | (base_config.headers or {}),
                    channel=base_config.channel,
                )
                client_key = f"{provider}:{provider_config.api_family or target.api_family}"

            if client_key not in clients:
                clients[client_key] = _make_client(
                    provider=provider,
                    api_family=provider_config.api_family or target.api_family,
                    provider_config=provider_config,
                    app_config=app_config,
                )

            client, _http_client = clients[client_key]
            ok, report_data = _run_one_suite(
                target,
                client=client,
                k=opts.k,
                include_tags=opts.tags,
                exclude_tags=opts.exclude_tags,
            )
            overall_ok = overall_ok and ok
            if report_data is not None:
                reports_by_provider.setdefault(target.provider, []).append(report_data)

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
        for _client_key, (_client, http_client) in clients.items():
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
    run_p.add_argument("--suites", default="suites-registry/providers", help="Registry directory")
    run_p.add_argument(
        "--output-root", default=None, help="Report root dir (default: config[report].output_dir)"
    )
    run_p.add_argument(
        "--provider", action="append", default=None, help="Only run a provider (repeatable)"
    )
    run_p.add_argument("--channel", default=None, help="Run a named channel from [[channels]]")
    run_p.add_argument("--model", action="append", default=None, help="Only run model(s)")
    run_p.add_argument(
        "--tags", default=None, help="Only run tests matching tags (comma-separated)"
    )
    run_p.add_argument(
        "--exclude-tags",
        default=None,
        help="Skip tests matching tags (comma-separated)",
    )
    run_p.add_argument(
        "-k",
        dest="k",
        default=None,
        help='Substring filter (like pytest -k), matches "provider/model/endpoint::test_name"',
    )
    run_p.set_defaults(_subcmd="run")

    return parser


def _parse_csv_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    return {p for p in parts if p}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args._subcmd == "run":
        opts = RunOptions(
            config_path=Path(args.config),
            suites_dir=Path(args.suites),
            output_root=Path(args.output_root) if args.output_root else None,
            provider_filter=set(args.provider) if args.provider else None,
            channel=args.channel,
            model_filter=set(args.model) if args.model else None,
            tags=_parse_csv_set(args.tags),
            exclude_tags=_parse_csv_set(args.exclude_tags),
            k=args.k,
        )
        return run_command(opts)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
