"""Report formatter: generate concise tables from JSON reports."""

from __future__ import annotations

from pathlib import Path

from llm_spec.reporting.report_types import (
    ParameterSupportInfo,
    ReportData,
    SupportedParameter,
    UnsupportedParameter,
)


class ParameterTableFormatter:
    """Format parameter support results for Markdown/HTML reports."""

    def __init__(self, report_data: ReportData):
        """
        Args:
            report_data: JSON report data
        """
        self.report = report_data

        # Prefer the new parameter_support_details format if available
        self.param_support_details: list[ParameterSupportInfo] = report_data.get(
            "parameter_support_details", []
        )

        # Fallback to legacy format
        if not self.param_support_details:
            # Extract from report (legacy compatibility)
            raw_tested = sorted(report_data.get("parameters", {}).get("tested", []))

            # Supported params
            self.supported_params: dict[str, SupportedParameter] = {}
            for p in report_data.get("parameters", {}).get("supported", []) or []:
                key = p.get("parameter", "")
                if key:
                    self.supported_params[key] = p

            # Unsupported params
            self.unsupported_params: dict[str, UnsupportedParameter] = {}
            for p in report_data.get("parameters", {}).get("unsupported", []) or []:
                key = p.get("parameter", "")
                if not key:
                    continue
                if key not in self.unsupported_params:
                    self.unsupported_params[key] = p
                    continue

                old = self.unsupported_params[key]
                old_reason = str(old.get("reason", ""))
                new_reason = str(p.get("reason", ""))

                # Prefer HTTP error reasons (usually start with "HTTP ")
                def _score(reason: str) -> tuple[int, int]:
                    return (1 if reason.strip().startswith("HTTP") else 0, len(reason))

                if _score(new_reason) > _score(old_reason):
                    self.unsupported_params[key] = p

            # Only show leaf parameter paths
            all_tested = self._leaf_only(raw_tested)
            self.tested_params = self._filter_tested_params(all_tested)
        else:
            # New format: use parameter_support_details directly
            self.supported_params = {}
            self.unsupported_params = {}
            self.tested_params = []

        # Summary
        test_summary = report_data.get("test_summary", {})
        self.total_tests = test_summary.get("total_tests", 0)
        self.passed_tests = test_summary.get("passed", 0)
        self.failed_tests = test_summary.get("failed", 0)

    @staticmethod
    def _leaf_only(params: list[str]) -> list[str]:
        """Keep leaf parameter paths only (hide container/prefix paths).

        Example:
        - Input:  ["contents", "contents[0].parts", "contents[0].parts[0].text"]
        - Output: ["contents[0].parts[0].text"]
        """
        if not params:
            return []

        s = set(params)
        leaves: list[str] = []

        for p in params:
            # If any other param has p as a prefix ('.' or '['), p is not a leaf.
            if any((q != p) and (q.startswith(p + ".") or q.startswith(p + "[")) for q in s):
                continue
            leaves.append(p)

        return leaves

    @staticmethod
    def _filter_tested_params(params: list[str]) -> list[str]:
        """Filter tested params.

        Current behavior keeps:
        1) all top-level params (no '.' or '[')
        2) nested params explicitly marked supported/unsupported
        """
        return params

    def _get_api_name(self) -> str:
        """Infer a human-readable API name."""
        try:
            from llm_spec.reporting.api_registry import find_api_config

            endpoint = self.report.get("endpoint", "")
            config = find_api_config(endpoint)
            if config:
                return str(config.get("api_name", "Unknown API"))
        except Exception:
            pass

        # Heuristics fallback
        provider = self.report.get("provider", "unknown").capitalize()
        endpoint = self.report.get("endpoint", "unknown")

        if "chat" in endpoint and "completions" in endpoint:
            return f"{provider} Chat Completions"
        elif "embeddings" in endpoint:
            return f"{provider} Embeddings"
        elif "messages" in endpoint:
            return f"{provider} Messages"
        elif "batch" in endpoint.lower():
            return f"{provider} Batch Generate Content"
        else:
            return f"{provider} API"

    def generate_markdown(self) -> str:
        """Generate a concise Markdown report."""
        lines = []
        api_name = self._get_api_name()

        # Title and summary
        lines.append(f"# {api_name} Parameter Support Report")
        lines.append("")
        lines.append(f"**Report time**: {self.report.get('test_time', 'N/A')}")
        lines.append(f"**Total tests**: {self.total_tests}")
        lines.append(f"**Passed**: {self.passed_tests} ✅")
        lines.append(f"**Failed**: {self.failed_tests} ❌")
        lines.append("")

        # Table using parameter_support_details
        if self.param_support_details:
            lines.append("## Parameter Support")
            lines.append("")

            # Check whether there are variant values
            has_variants = any(info.get("variant_value") for info in self.param_support_details)

            if has_variants:
                # Variants present: 4-column table
                lines.append("| Parameter | Variant | Request | Validation |")
                lines.append("|------|--------|----------|--------------|")

                for info in self.param_support_details:
                    param = info.get("parameter", "")
                    variant = info.get("variant_value") or "-"
                    request_ok = info.get("request_ok", False)
                    request_error = info.get("request_error")
                    validation_ok = info.get("validation_ok", False)
                    validation_error = info.get("validation_error")

                    # Request status
                    if request_ok:
                        request_status = "✅"
                    else:
                        request_status = f"❌ {request_error}" if request_error else "❌"

                    # Validation status
                    if not request_ok:
                        validation_status = "N/A"
                    elif validation_ok:
                        validation_status = "✅"
                    else:
                        validation_status = f"❌ {validation_error}" if validation_error else "❌"

                    lines.append(
                        f"| `{param}` | `{variant}` | {request_status} | {validation_status} |"
                    )
            else:
                # No variants: 3-column table
                lines.append("| Parameter | Request | Validation |")
                lines.append("|------|----------|--------------|")

                for info in self.param_support_details:
                    param = info.get("parameter", "")
                    request_ok = info.get("request_ok", False)
                    request_error = info.get("request_error")
                    validation_ok = info.get("validation_ok", False)
                    validation_error = info.get("validation_error")

                    # Request status
                    if request_ok:
                        request_status = "✅"
                    else:
                        request_status = f"❌ {request_error}" if request_error else "❌"

                    # Validation status
                    if not request_ok:
                        validation_status = "N/A"
                    elif validation_ok:
                        validation_status = "✅"
                    else:
                        validation_status = f"❌ {validation_error}" if validation_error else "❌"

                    lines.append(f"| `{param}` | {request_status} | {validation_status} |")

            lines.append("")
        else:
            # Legacy format
            supported_count = len(
                [p for p in self.supported_params if p not in self.unsupported_params]
            )
            unsupported_count = len(self.unsupported_params)
            self.display_params = [
                p
                for p in self.tested_params
                if p in self.supported_params or p in self.unsupported_params
            ]
            total_count = len(self.display_params)

            lines.append("## Parameter Support")
            lines.append("")
            lines.append(f"- **Tested parameters**: {total_count}")
            lines.append(f"  - ✅ Supported: {supported_count}")
            lines.append(f"  - ❌ Unsupported: {unsupported_count}")
            lines.append("")

            # Table (legacy)
            if self.display_params:
                lines.append("## Parameters")
                lines.append("")
                lines.append("| Parameter | Status |")
                lines.append("|------|------|")

                for param in self.display_params:
                    if param in self.unsupported_params:
                        status = "❌ Unsupported"
                        reason = self.unsupported_params[param].get("reason", "")
                        if reason:
                            status += f" ({reason})"
                    else:
                        status = "✅ Supported"
                    lines.append(f"| `{param}` | {status} |")

            lines.append("")

        return "\n".join(lines)

    def generate_html(self) -> str:
        """Generate a concise HTML report."""
        api_name = self._get_api_name()

        # Use parameter_support_details if available
        use_new_format = bool(self.param_support_details)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_name} Parameter Support Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1976d2; margin: 30px 0 20px; text-align: center; }}
        h2 {{ color: #1976d2; margin: 20px 0 10px; border-bottom: 2px solid #1976d2; padding-bottom: 5px; }}

        .summary {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}

        .stat {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}

        .stat-value {{ font-size: 24px; font-weight: bold; margin-bottom: 5px; }}
        .stat-label {{ font-size: 12px; opacity: 0.9; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            margin: 20px 0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        th {{
            background: #1976d2;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}

        tr:hover {{ background: #f9f9f9; }}

        .param-path {{ font-family: 'Courier New', monospace; color: #d32f2f; }}
        .status-ok {{ color: #4caf50; font-weight: bold; }}
        .status-error {{ color: #f44336; font-weight: bold; }}
        .status-na {{ color: #9e9e9e; font-style: italic; }}
        .error-detail {{ color: #d32f2f; font-size: 0.9em; }}

        .footer {{
            text-align: center;
            color: #999;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
        }}
    </style>
</head>
    <body>
        <div class="container">
            <h1>📋 {api_name} Parameter Support Report</h1>

            <div class="summary">
                <h2>Test overview</h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{self.total_tests}</div>
                        <div class="stat-label">Total</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{self.passed_tests}</div>
                        <div class="stat-label">Passed ✅</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{self.failed_tests}</div>
                        <div class="stat-label">Failed ❌</div>
                    </div>
                </div>
                <p><strong>Report time</strong>: {self.report.get("test_time", "N/A")}</p>
            </div>

            <h2>Parameter support</h2>
            <table>
"""

        if use_new_format:
            # Check whether there are variant values
            has_variants = any(info.get("variant_value") for info in self.param_support_details)

            if has_variants:
                # Variants present: 4-column table
                html += """            <tr>
                <th>Parameter</th>
                <th>Variant</th>
                <th>Request</th>
                <th>Validation</th>
            </tr>
"""
                for info in self.param_support_details:
                    param = info.get("parameter", "")
                    variant = info.get("variant_value") or "-"
                    request_ok = info.get("request_ok", False)
                    request_error = info.get("request_error")
                    validation_ok = info.get("validation_ok", False)
                    validation_error = info.get("validation_error")

                    # Request status
                    if request_ok:
                        request_status = '<span class="status-ok">✅</span>'
                    else:
                        error_msg = f" {request_error}" if request_error else ""
                        request_status = f'<span class="status-error">❌{error_msg}</span>'

                    # Validation status
                    if not request_ok:
                        validation_status = '<span class="status-na">N/A</span>'
                    elif validation_ok:
                        validation_status = '<span class="status-ok">✅</span>'
                    else:
                        error_msg = f" {validation_error}" if validation_error else ""
                        validation_status = f'<span class="status-error">❌{error_msg}</span>'

                    html += f"""            <tr>
                <td><span class="param-path">{param}</span></td>
                <td><span class="param-path">{variant}</span></td>
                <td>{request_status}</td>
                <td>{validation_status}</td>
            </tr>
"""
            else:
                # No variants: 3-column table
                html += """            <tr>
                    <th>Parameter</th>
                    <th>Request</th>
                    <th>Validation</th>
                </tr>
"""
                for info in self.param_support_details:
                    param = info.get("parameter", "")
                    request_ok = info.get("request_ok", False)
                    request_error = info.get("request_error")
                    validation_ok = info.get("validation_ok", False)
                    validation_error = info.get("validation_error")

                    # Request status
                    if request_ok:
                        request_status = '<span class="status-ok">✅</span>'
                    else:
                        error_msg = f" {request_error}" if request_error else ""
                        request_status = f'<span class="status-error">❌{error_msg}</span>'

                    # Validation status
                    if not request_ok:
                        validation_status = '<span class="status-na">N/A</span>'
                    elif validation_ok:
                        validation_status = '<span class="status-ok">✅</span>'
                    else:
                        error_msg = f" {validation_error}" if validation_error else ""
                        validation_status = f'<span class="status-error">❌{error_msg}</span>'

                    html += f"""            <tr>
                    <td><span class="param-path">{param}</span></td>
                    <td>{request_status}</td>
                    <td>{validation_status}</td>
                </tr>
"""
        else:
            # Legacy: 2-column table
            html += """            <tr>
                <th>Parameter</th>
                <th>Status</th>
            </tr>
"""
            for param in self.display_params if hasattr(self, "display_params") else []:
                if param in self.unsupported_params:
                    status = '<span class="status-error">❌ Unsupported</span>'
                    reason = self.unsupported_params[param].get("reason", "")
                    if reason:
                        status += f' <span class="error-detail">({reason})</span>'
                else:
                    status = '<span class="status-ok">✅ Supported</span>'

                html += f"""            <tr>
                <td><span class="param-path">{param}</span></td>
                <td>{status}</td>
            </tr>
"""

        html += """        </table>

            <div class="footer">
                <p>This report is generated by llm-spec</p>
            </div>
    </div>
</body>
</html>"""

        return html

    def save_markdown(self, output_dir: str = "reports") -> str:
        """Write Markdown report to output_dir."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{output_dir}/report.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())

        return filename

    def save_html(self, output_dir: str = "reports") -> str:
        """Write HTML report to output_dir."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{output_dir}/report.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.generate_html())

        return filename
