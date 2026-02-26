"""Format run-level reports from run_result.json payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunResultFormatter:
    """Generate Markdown/HTML views from a run_result payload."""

    def __init__(self, run_result: dict[str, Any]):
        self.run_result = run_result

    def generate_markdown(self) -> str:
        summary = self.run_result.get("summary", {})
        lines: list[str] = [
            "# LLM Spec Run Report",
            "",
            f"- Run ID: `{self.run_result.get('run_id', 'unknown')}`",
            f"- Started: `{self.run_result.get('started_at', 'N/A')}`",
            f"- Finished: `{self.run_result.get('finished_at', 'N/A')}`",
            "",
            "## Summary",
            "",
            f"- Total: {summary.get('total', 0)}",
            f"- Passed: {summary.get('passed', 0)}",
            f"- Failed: {summary.get('failed', 0)}",
            f"- Skipped: {summary.get('skipped', 0)}",
            "",
        ]

        for provider_node in self.run_result.get("providers", []):
            provider = provider_node.get("provider", "unknown")
            p_summary = provider_node.get("summary", {})
            lines.extend(
                [
                    f"## Provider: `{provider}`",
                    "",
                    f"- Total: {p_summary.get('total', 0)}",
                    f"- Passed: {p_summary.get('passed', 0)}",
                    f"- Failed: {p_summary.get('failed', 0)}",
                    f"- Skipped: {p_summary.get('skipped', 0)}",
                    "",
                ]
            )

            for endpoint_node in provider_node.get("endpoints", []):
                endpoint = endpoint_node.get("endpoint", "unknown")
                e_summary = endpoint_node.get("summary", {})
                lines.extend(
                    [
                        f"### Endpoint: `{endpoint}`",
                        "",
                        f"- Total: {e_summary.get('total', 0)}",
                        f"- Passed: {e_summary.get('passed', 0)}",
                        f"- Failed: {e_summary.get('failed', 0)}",
                        f"- Skipped: {e_summary.get('skipped', 0)}",
                        "",
                        "| Test | Parameter | Value | Status | Reason |",
                        "|---|---|---|---|---|",
                    ]
                )

                for test in endpoint_node.get("tests", []):
                    test_name = test.get("test_name", "")
                    parameter = (test.get("parameter") or {}).get("name", "")
                    value = (test.get("parameter") or {}).get("value")
                    status = (test.get("result") or {}).get("status", "")
                    reason = (test.get("result") or {}).get("reason")
                    value_text = json.dumps(value, ensure_ascii=False) if value is not None else "-"
                    reason_text = str(reason) if reason else "-"
                    lines.append(
                        f"| `{test_name}` | `{parameter}` | `{value_text}` | `{status}` | {reason_text} |"
                    )
                lines.append("")

        return "\n".join(lines)

    def generate_html(self) -> str:
        summary = self.run_result.get("summary", {})
        html = [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            "<title>LLM Spec Run Report</title>",
            "<style>body{font-family:Arial,sans-serif;padding:20px}table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ddd;padding:8px}th{background:#f5f5f5}code{font-family:monospace}</style>",
            "</head><body>",
            "<h1>LLM Spec Run Report</h1>",
            f"<p>Run ID: <code>{self.run_result.get('run_id', 'unknown')}</code></p>",
            f"<p>Total: {summary.get('total', 0)} | Passed: {summary.get('passed', 0)} | "
            f"Failed: {summary.get('failed', 0)} | Skipped: {summary.get('skipped', 0)}</p>",
        ]

        for provider_node in self.run_result.get("providers", []):
            provider = provider_node.get("provider", "unknown")
            p_summary = provider_node.get("summary", {})
            html.extend(
                [
                    f"<h2>Provider: <code>{provider}</code></h2>",
                    f"<p>Total: {p_summary.get('total', 0)} | Passed: {p_summary.get('passed', 0)} | "
                    f"Failed: {p_summary.get('failed', 0)} | Skipped: {p_summary.get('skipped', 0)}</p>",
                ]
            )

            for endpoint_node in provider_node.get("endpoints", []):
                endpoint = endpoint_node.get("endpoint", "unknown")
                e_summary = endpoint_node.get("summary", {})
                html.extend(
                    [
                        f"<h3>Endpoint: <code>{endpoint}</code></h3>",
                        f"<p>Total: {e_summary.get('total', 0)} | Passed: {e_summary.get('passed', 0)} | "
                        f"Failed: {e_summary.get('failed', 0)} | Skipped: {e_summary.get('skipped', 0)}</p>",
                        "<table><tr><th>Test</th><th>Parameter</th><th>Value</th><th>Status</th><th>Reason</th></tr>",
                    ]
                )

                for test in endpoint_node.get("tests", []):
                    test_name = str(test.get("test_name", ""))
                    parameter = str((test.get("parameter") or {}).get("name", ""))
                    value = (test.get("parameter") or {}).get("value")
                    status = str((test.get("result") or {}).get("status", ""))
                    reason = str((test.get("result") or {}).get("reason", "") or "-")
                    value_text = json.dumps(value, ensure_ascii=False) if value is not None else "-"
                    html.append(
                        f"<tr><td><code>{test_name}</code></td><td><code>{parameter}</code></td>"
                        f"<td><code>{value_text}</code></td><td>{status}</td><td>{reason}</td></tr>"
                    )
                html.append("</table>")

        html.append("</body></html>")
        return "\n".join(html)

    def save_markdown(self, output_dir: str) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir) / "report.md"
        output_path.write_text(self.generate_markdown(), encoding="utf-8")
        return str(output_path)

    def save_html(self, output_dir: str) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = Path(output_dir) / "report.html"
        output_path.write_text(self.generate_html(), encoding="utf-8")
        return str(output_path)
