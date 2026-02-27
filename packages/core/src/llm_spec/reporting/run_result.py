"""Build run-level result payloads from endpoint report data."""

from __future__ import annotations

from llm_spec.reporting.report_types import ReportData


def build_run_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    reports_by_provider: dict[str, list[ReportData]],
) -> dict:
    """Build a stable run-level result payload."""
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
