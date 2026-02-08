"""Report aggregator for merging multiple endpoint reports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.reporting.report_types import ReportData, TestSummary, UnsupportedParameter


class AggregatedReportCollector:
    """Aggregate multiple endpoint reports for a provider.

    Use cases:
    - Collect all endpoint reports for one provider
    - Merge parameters, statistics, and errors
    - Keep endpoint-to-parameter mapping
    - Produce a summary report
    """

    def __init__(self, provider: str):
        """Initialize the aggregated report collector.

        Args:
            provider: provider name (e.g. 'openai', 'anthropic', 'gemini')
        """
        self.provider = provider
        self.endpoints: dict[str, ReportData] = {}  # endpoint -> report_data
        self.aggregation_time = datetime.now().isoformat()

    def add_endpoint_report(self, endpoint: str, report_data: ReportData) -> None:
        """Add a single endpoint report.

        Args:
            endpoint: API endpoint (e.g. '/v1/chat/completions')
            report_data: report JSON data for one endpoint
        """
        self.endpoints[endpoint] = report_data

    def merge_reports(self, report_files: list[Path]) -> None:
        """Merge multiple reports from a list of JSON files.

        Args:
            report_files: list of report.json paths
        """
        for report_file in report_files:
            try:
                with open(report_file, encoding="utf-8") as f:
                    report_data: ReportData = json.load(f)
                    endpoint = str(report_data.get("endpoint", "unknown"))
                    self.add_endpoint_report(endpoint, report_data)
            except (OSError, json.JSONDecodeError) as e:
                print(f"Warning: Failed to load report {report_file}: {e}")

    def get_aggregated_parameters(self) -> dict[str, dict[str, Any]]:
        """Aggregate parameter support across endpoints while preserving endpoint mapping.

        Logic:
        1) Build a set of unsupported parameters from the `unsupported` array.
        2) Only parameters not in that set are marked as supported.
        3) Parameters in that set are marked as unsupported.

        Returns:
            Aggregated parameter data, shape:
            {
                'parameter_name': {
                    'endpoints': {
                        '/v1/chat/completions': {'status': 'supported', ...},
                        '/v1/embeddings': {'status': 'unsupported', 'reason': '...'},
                    },
                    'support_count': 1,
                    'total_endpoints': 2
                },
                ...
            }
        """
        aggregated: dict[str, dict[str, Any]] = {}
        all_endpoints = set(self.endpoints.keys())

        for endpoint, report in self.endpoints.items():
            # Build a lookup: test_name -> structured error (from endpoint report)
            # Prefer the first occurrence per test_name (good enough for reporting).
            errors_by_test: dict[str, dict[str, Any]] = {}
            for err in report.get("errors", []) or []:
                tn = err.get("test_name")
                if isinstance(tn, str) and tn and tn not in errors_by_test:
                    errors_by_test[tn] = err

            # Step 1: build lookup for unsupported parameters
            unsupported_params_list: list[UnsupportedParameter] = report.get("parameters", {}).get(
                "unsupported", []
            )
            unsupported_param_names: dict[str, UnsupportedParameter] = {
                str(param.get("parameter")): param
                for param in unsupported_params_list
                if param.get("parameter")
            }

            # Step 2: get all params (tested + unsupported)
            tested_params = set(report.get("parameters", {}).get("tested", []))
            all_params = tested_params | set(unsupported_param_names.keys())

            # Step 3: process each parameter
            for param in all_params:
                if param not in aggregated:
                    aggregated[param] = {
                        "endpoints": {},
                        "support_count": 0,
                        "total_endpoints": len(all_endpoints),
                    }

                # Key logic: check whether this parameter is in `unsupported`
                if param in unsupported_param_names:
                    # This parameter is unsupported
                    unsupported_info = unsupported_param_names[param]
                    test_name = unsupported_info.get("test_name", "")
                    err = errors_by_test.get(test_name) if isinstance(test_name, str) else None

                    # Prefer structured response_body for detail (user-requested)
                    reason_detail: str | None = None
                    if err is not None:
                        status_code = err.get("status_code")
                        resp_body = err.get("response_body")
                        if status_code is not None:
                            reason_detail = f"HTTP {status_code}: {resp_body}"

                    aggregated[param]["endpoints"][endpoint] = {
                        "status": "unsupported",
                        # Keep legacy reason for backwards compatibility, but add a detailed one.
                        "reason": unsupported_info.get("reason", "Unknown"),
                        "reason_detail": reason_detail or unsupported_info.get("reason", "Unknown"),
                        "test_name": test_name,
                    }
                else:
                    # Supported (in tested but not in unsupported)
                    aggregated[param]["endpoints"][endpoint] = {
                        "status": "supported",
                        "test_count": report.get("test_summary", {}).get("total_tests", 0),
                    }
                    aggregated[param]["support_count"] += 1

        return aggregated

    def get_aggregated_summary(self) -> dict[str, Any]:
        """Return aggregated summary statistics.

        Returns:
            Summary including:
            - endpoints count
            - total tests
            - passed/failed
            - parameter stats
        """
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_list: list[Any] = []

        for report in self.endpoints.values():
            summary: TestSummary = report.get("test_summary", {})
            total_tests += summary.get("total_tests", 0)
            passed_tests += summary.get("passed", 0)
            failed_tests += summary.get("failed", 0)
            error_list.extend(report.get("errors", []))  # Any until error schema is defined

        # Deduplicate errors by (test_name + status_code + error + response_body)
        unique_errors = {}
        for error in error_list:
            key = (
                f"{error.get('test_name', '')}_"
                f"{error.get('status_code', '')}_"
                f"{error.get('error', '')}_"
                f"{json.dumps(error.get('response_body', None), sort_keys=True, ensure_ascii=False, default=str)}"
            )
            if key not in unique_errors:
                unique_errors[key] = error

        aggregated_params = self.get_aggregated_parameters()

        return {
            "provider": self.provider,
            "aggregation_time": self.aggregation_time,
            "endpoints_count": len(self.endpoints),
            "endpoints": list(self.endpoints.keys()),
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "pass_rate": f"{(passed_tests / total_tests * 100):.1f}%"
                if total_tests > 0
                else "N/A",
            },
            "parameters": {
                "total_unique": len(aggregated_params),
                "fully_supported": sum(
                    1
                    for p in aggregated_params.values()
                    if p["support_count"] == p["total_endpoints"]
                ),
                "partially_supported": sum(
                    1
                    for p in aggregated_params.values()
                    if 0 < p["support_count"] < p["total_endpoints"]
                ),
                "unsupported": sum(
                    1 for p in aggregated_params.values() if p["support_count"] == 0
                ),
            },
            "errors_count": len(unique_errors),
            "errors": list(unique_errors.values()),
        }

    def finalize(self, output_dir: str = "./reports") -> dict[str, str]:
        """Write aggregated report files.

        Args:
            output_dir: output directory

        Returns:
            A dict of generated file paths: {"json": path, "markdown": path, "html": path}
        """
        if not self.endpoints:
            raise ValueError("No endpoint reports to aggregate. Call add_endpoint_report() first.")

        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir_name = f"{self.provider}_aggregated_{timestamp}"
        report_dir = Path(output_dir) / report_dir_name
        report_dir.mkdir(parents=True, exist_ok=True)

        # Build aggregated report
        aggregated_params = self.get_aggregated_parameters()
        summary = self.get_aggregated_summary()

        report = {
            "report_type": "aggregated",
            "provider": self.provider,
            "aggregation_time": self.aggregation_time,
            "summary": summary,
            "endpoints": {
                endpoint: {
                    "endpoint": endpoint,
                    "base_url": data.get("base_url", ""),
                    "test_summary": data.get("test_summary", {}),
                }
                for endpoint, data in self.endpoints.items()
            },
            "parameters": {
                "aggregated": self._serialize_aggregated_params(aggregated_params),
            },
            # Attach structured error list
            "errors": summary.get("errors", []),
        }

        # Write JSON
        json_path = report_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Generate Markdown/HTML
        markdown_path = self._generate_markdown(report_dir, report)
        html_path = self._generate_html(report_dir, report)

        return {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "html": str(html_path),
        }

    @staticmethod
    def _serialize_aggregated_params(
        aggregated_params: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Serialize aggregated parameter data for JSON output."""
        result = {}
        for param_name, param_data in aggregated_params.items():
            result[param_name] = {
                "endpoints": param_data["endpoints"],
                "support_count": param_data["support_count"],
                "total_endpoints": param_data["total_endpoints"],
                "support_rate": f"{(param_data['support_count'] / param_data['total_endpoints'] * 100):.1f}%"
                if param_data["total_endpoints"] > 0
                else "N/A",
            }
        return result

    def _generate_markdown(self, report_dir: Path, report: dict[str, Any]) -> Path:
        """Generate a Markdown aggregated report grouped by endpoint."""
        markdown_path = report_dir / "report.md"

        summary = report["summary"]
        endpoints = report["endpoints"]

        lines = []
        lines.append(f"# {summary['provider'].upper()} API Parameter Support (Aggregated)\n")
        lines.append(f"**Aggregation time**: {summary['aggregation_time']}\n")

        # Summary
        lines.append("## 📊 Summary\n")
        lines.append(f"- **Endpoints**: {summary['endpoints_count']}")
        lines.append(f"- **Total tests**: {summary['test_summary']['total_tests']}")
        lines.append(f"- **Passed**: {summary['test_summary']['passed']} ✅")
        lines.append(f"- **Failed**: {summary['test_summary']['failed']} ❌")
        lines.append(f"- **Pass rate**: {summary['test_summary']['pass_rate']}\n")

        # Parameters grouped by endpoint
        lines.append("## 📋 Parameter support by endpoint\n")

        for endpoint in sorted(endpoints.keys()):
            endpoint_data = endpoints[endpoint]
            ep_summary = endpoint_data["test_summary"]

            # Endpoint header + stats
            lines.append(f"### {endpoint}\n")
            lines.append(
                f"**Tests**: {ep_summary.get('total_tests', 0)}, "
                f"passed: {ep_summary.get('passed', 0)} ✅, "
                f"failed: {ep_summary.get('failed', 0)} ❌\n"
            )

            # Pull this endpoint's parameter info from the aggregated parameter map
            aggregated_params = report["parameters"]["aggregated"]

            lines.append("| Parameter | Status |")
            lines.append("|------|------|")

            for param_name in sorted(aggregated_params.keys()):
                param_data = aggregated_params[param_name]
                endpoint_info = param_data["endpoints"].get(endpoint)

                if endpoint_info:
                    if endpoint_info["status"] == "supported":
                        status = "✅ Supported"
                    else:
                        reason = endpoint_info.get("reason_detail") or endpoint_info.get(
                            "reason", "Unsupported"
                        )
                        status = "❌ Unsupported"
                        if reason:
                            status += f" ({reason})"
                    lines.append(f"| `{param_name}` | {status} |")

            lines.append("")

        # Errors
        if summary["errors_count"] > 0:
            lines.append("## ⚠️ Error summary\n")
            lines.append(f"Total errors: {summary['errors_count']}\n")
            # Show structured errors (deduped, max 50)
            for err in report.get("errors", [])[:50]:
                lines.append(
                    f"- **{err.get('test_name', '')}** (HTTP {err.get('status_code', '')}, {err.get('type', '')})"
                )
                lines.append(f"  - error: {err.get('error')}")
                lines.append(f"  - response_body: {err.get('response_body')}")
                lines.append("")

        markdown_content = "\n".join(lines)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return markdown_path

    def _generate_html(self, report_dir: Path, report: dict[str, Any]) -> Path:
        """Generate an HTML aggregated report grouped by endpoint."""
        html_path = report_dir / "report.html"

        summary = report["summary"]
        endpoints = report["endpoints"]
        aggregated_params = report["parameters"]["aggregated"]

        # HTML template grouped by endpoint
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{summary["provider"].upper()} API Parameter Support (Aggregated)</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ font-size: 14px; opacity: 0.9; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .stat-card h3 {{ color: #666; font-size: 13px; margin-bottom: 8px; font-weight: 500; }}
        .stat-card .value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .section h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}
        .endpoint-group {{ margin-bottom: 30px; padding: 15px; background: #fafafa; border-left: 4px solid #667eea; border-radius: 4px; }}
        .endpoint-group h3 {{ font-size: 16px; color: #667eea; margin-bottom: 12px; font-family: monospace; }}
        .endpoint-stats {{ display: flex; gap: 20px; margin-bottom: 12px; font-size: 13px; color: #666; }}
        .endpoint-stats span {{ display: inline-block; }}
        .endpoint-stats .pass {{ color: #27ae60; }}
        .endpoint-stats .fail {{ color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f8f8f8; padding: 10px; text-align: left; font-weight: 600; color: #333; border-bottom: 2px solid #ddd; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #fafafa; }}
        .support {{ color: #27ae60; font-weight: 500; }}
        .unsupport {{ color: #e74c3c; }}
        .summary-table td:first-child {{ font-weight: 500; color: #333; }}
        pre {{ white-space: pre-wrap; word-break: break-word; background: #0b1020; color: #e6edf3; padding: 12px; border-radius: 6px; font-size: 12px; }}
        .error-card {{ background: #fff6f6; border: 1px solid #ffd6d6; padding: 12px; border-radius: 8px; margin-top: 10px; }}
        .error-title {{ font-weight: 600; color: #b91c1c; margin-bottom: 6px; }}
        .reason-detail {{ color: #444; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{summary["provider"].upper()} API Parameter Support (Aggregated)</h1>
            <p>Aggregation time: {summary["aggregation_time"]}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total tests</h3>
                <div class="value">{summary["test_summary"]["total_tests"]}</div>
            </div>
            <div class="stat-card">
                <h3>Passed ✅</h3>
                <div class="value" style="color: #27ae60;">{summary["test_summary"]["passed"]}</div>
            </div>
            <div class="stat-card">
                <h3>Failed ❌</h3>
                <div class="value" style="color: #e74c3c;">{summary["test_summary"]["failed"]}</div>
            </div>
            <div class="stat-card">
                <h3>Pass rate</h3>
                <div class="value">{summary["test_summary"]["pass_rate"]}</div>
            </div>
        </div>

        <div class="section">
            <h2>📋 Parameter support by endpoint</h2>
        """

        # Group by endpoint
        for endpoint in sorted(endpoints.keys()):
            endpoint_data = endpoints[endpoint]
            ep_summary = endpoint_data["test_summary"]

            total_tests = ep_summary.get("total_tests", 0)
            passed = ep_summary.get("passed", 0)
            failed = ep_summary.get("failed", 0)

            html_content += f"""
            <div class="endpoint-group">
                <h3>{endpoint}</h3>
                <div class="endpoint-stats">
                    <span>🔬 {total_tests} tests</span>
                    <span class="pass">✅ {passed} passed</span>
                    <span class="fail">❌ {failed} failed</span>
                </div>
                <table>
                    <tr>
                        <th style="width: 40%;">Parameter</th>
                        <th style="width: 60%;">Status</th>
                    </tr>
            """

            # Table rows for this endpoint
            for param_name in sorted(aggregated_params.keys()):
                param_data = aggregated_params[param_name]
                endpoint_info = param_data["endpoints"].get(endpoint)
                if not endpoint_info:
                    continue

                if endpoint_info["status"] == "supported":
                    status_html = '<span class="support">✅ Supported</span>'
                else:
                    reason_detail = endpoint_info.get("reason_detail") or endpoint_info.get(
                        "reason", "Unsupported"
                    )
                    status_html = (
                        '<span class="unsupport">❌ Unsupported</span>'
                        f'<div class="reason-detail">{reason_detail}</div>'
                    )

                html_content += f"""
                    <tr>
                        <td><code>{param_name}</code></td>
                        <td>{status_html}</td>
                    </tr>
                """

            html_content += """
                </table>
            </div>
            """

        # Close "Parameter support by endpoint" section
        html_content += """
        </div>
        """

        # Structured error details
        if report.get("errors"):
            html_content += """
        <div class="section">
            <h2>⚠️ Error details</h2>
            <p style="color:#666; font-size: 13px; margin-bottom: 10px;">
                Deduplicated error list (showing up to 50)
            </p>
            """

            for err in report.get("errors", [])[:50]:
                pretty = json.dumps(err, ensure_ascii=False, indent=2, default=str)
                html_content += f"""
            <div class="error-card">
                <div class="error-title">{err.get("test_name", "")} (HTTP {err.get("status_code", "")}, {err.get("type", "")})</div>
                <pre>{pretty}</pre>
            </div>
                """
            html_content += """
        </div>
            """

        html_content += """
    </div>
</body>
</html>
        """

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_path
