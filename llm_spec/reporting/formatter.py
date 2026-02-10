"""Report formatter: generate concise tables from JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

    def _format_display_value(self, value: Any, truncate: bool = True) -> str:
        r"""Format a parameter value for display in reports.

        Rules:
        1. If None, return "-"
        2. If it's a file path (contains / or \ and NOT 'data:'), return basename.类型
        3. If truncate is True, truncate string to 100 chars.
        4. If complex (list/dict), json.dumps and optionally truncate to 100 chars.
        """
        if value is None:
            return "-"

        if isinstance(value, str):
            # Check for file path (heuristic: contains / or \ and not a data URI)
            if ("/" in value or "\\" in value) and not value.startswith("data:"):
                try:
                    p = Path(value)
                    # We want "filename.ext"
                    if p.name:
                        return p.name
                except Exception:
                    pass

            # Escape control characters like \n, \r, \t, etc.
            # We use json.dumps for robust escaping, then strip surrounding quotes.
            if any(ord(c) < 32 for c in value):
                display_str = json.dumps(value, ensure_ascii=False).strip('"')
            else:
                display_str = value
        elif isinstance(value, (list, dict)):
            try:
                display_str = json.dumps(value, ensure_ascii=False)
            except Exception:
                display_str = str(value)
        else:
            display_str = str(value)

        # Truncate if requested
        if truncate and len(display_str) > 100:
            return display_str[:97] + "..."

        return display_str

    def generate_markdown(self) -> str:
        """Generate a concise Markdown report."""
        lines = []

        # Extract provider details
        provider = self.report.get("provider", "Unknown")
        endpoint = self.report.get("endpoint", "Unknown")
        base_url = self.report.get("base_url", "Unknown")
        test_time = self.report.get("test_time", "N/A")

        # Title and Metadata
        lines.append("# LLM API Compliance Report")
        lines.append("")

        lines.append("| Metadata | Value |")
        lines.append("| :--- | :--- |")
        lines.append(f"| **Provider** | `{provider}` |")
        lines.append(f"| **Endpoint** | `{endpoint}` |")
        lines.append(f"| **Base URL** | `{base_url}` |")
        lines.append(f"| **Date** | {test_time} |")
        lines.append("")

        # Summary Stats
        lines.append("### Statistics")
        lines.append("")
        lines.append(f"- **Total Tests**: {self.total_tests}")
        lines.append(f"- **Passed**: {self.passed_tests} ✅")
        lines.append(f"- **Failed**: {self.failed_tests} ❌")
        lines.append("")

        # Table using parameter_support_details
        if self.param_support_details:
            # Always show 4 columns for new format: Parameter | Value | Request | Validation
            lines.append("| Parameter | Value | Request | Validation |")
            lines.append("| :--- | :--- | :--- | :--- |")

            for info in self.param_support_details:
                param = info.get("parameter", "")
                # Prefer 'value' field (raw value), fallback to 'variant_value'
                raw_value = info.get("value")
                if raw_value is None:
                    raw_value = info.get("variant_value")

                value_display = self._format_display_value(raw_value)
                request_ok = info.get("request_ok", False)
                request_error = info.get("request_error")
                validation_ok = info.get("validation_ok", False)
                validation_error = info.get("validation_error")

                # Request status
                if request_ok:
                    request_status = "✅ Success"
                else:
                    request_status = (
                        f"❌ Failed<br><small>{request_error}</small>"
                        if request_error
                        else "❌ Failed"
                    )

                # Validation status
                if not request_ok:
                    validation_status = "Skipped"
                elif validation_ok:
                    validation_status = "✅ Valid"
                else:
                    validation_status = (
                        f"❌ Invalid<br><small>{validation_error}</small>"
                        if validation_error
                        else "❌ Invalid"
                    )

                lines.append(
                    f"| **{param}** | `{value_display}` | {request_status} | {validation_status} |"
                )

            lines.append("")
        else:
            # Legacy format
            self.display_params = [
                p
                for p in self.tested_params
                if p in self.supported_params or p in self.unsupported_params
            ]

            # Since stats are already printed above, we can skip re-printing them or keep them for specific legacy flow contexts
            # But the user asked for alignment, so let's stick to the new table format logic mainly.
            # For legacy, we just print the list.

            if self.display_params:
                lines.append("### Parameters")
                lines.append("")
                lines.append("| Parameter | Status |")
                lines.append("| :--- | :--- |")

                for param in self.display_params:
                    if param in self.unsupported_params:
                        status = "❌ Unsupported"
                        reason = self.unsupported_params[param].get("reason", "")
                        if reason:
                            status += f"<br><small>{reason}</small>"
                    else:
                        status = "✅ Supported"
                    lines.append(f"| **{param}** | {status} |")

            lines.append("")

        return "\n".join(lines)

    def generate_html(self) -> str:
        """Generate a concise HTML report."""
        import base64
        import os

        api_name = self._get_api_name()

        # Load logo
        logo_path = os.path.join(os.path.dirname(__file__), "../../assets/logo.jpg")
        logo_b64 = ""
        try:
            with open(logo_path, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass

        # Use parameter_support_details if available
        use_new_format = bool(self.param_support_details)

        # Extract provider details
        provider = self.report.get("provider", "Unknown")
        endpoint = self.report.get("endpoint", "Unknown")
        base_url = self.report.get("base_url", "Unknown")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_name} Parameter Support Report</title>
    <style>
        :root {{
            --color-purple-600: oklch(55.8% .288 302.321);
            --color-text: #1a1a1a;
            --color-bg: #ffffff;
            --color-border: #e5e5e5;
            --color-success: #16a34a;
            --color-error: #dc2626;
            --color-neutral: #525252;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.5;
            font-size: 14px;
        }}

        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        /* Compact Header Area containing Logo, Title, Config, Stats */
        .dashboard-header {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 20px;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--color-border);
        }}

        .header-left {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo {{ height: 48px; width: auto; }}

        h1 {{
            font-size: 20px;
            font-weight: 700;
            color: var(--color-text);
            margin: 0;
        }}

        .meta-info {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px 24px;
            font-size: 13px;
        }}

        .meta-item {{ display: flex; gap: 6px; align-items: baseline; }}
        .meta-label {{ color: var(--color-neutral); font-size: 11px; text-transform: uppercase; font-weight: 600; }}
        .meta-value {{ font-family: 'Courier New', monospace; font-weight: 600; color: var(--color-text); }}

        .stats-grid {{
            display: flex;
            gap: 24px; /* Increased gap since boxes are gone */
        }}

        .stat-card {{
            /* Removed background and border */
            background: transparent;
            padding: 0;
            border: none;
            text-align: center;
            min-width: 80px;
            display: flex;
            flex-direction: column-reverse; /* Put label bottom, value top? or kept normal. Usually Label below value. */
            justify-content: center;
        }}

        /* Value: Purple, Bigger */
        .stat-value {{
            font-family: 'Courier New', monospace;
            font-size: 32px;
            font-weight: 800;
            color: var(--color-purple-600);
            line-height: 1.1;
        }}

        /* Label: Bigger, neutral/dark text */
        .stat-label {{
            font-size: 13px;
            color: var(--color-neutral);
            font-weight: 600;
            margin-top: 4px;
            text-transform: uppercase;
        }}

        h2 {{
            font-size: 16px;
            margin: 0 0 15px;
            color: var(--color-text);
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            border: 1px solid var(--color-border);
            border-radius: 8px;
            overflow: hidden;
            font-size: 13px;
            table-layout: fixed; /* Fixed layout for truncation */
        }}

        th {{
            background: #fafafa;
            color: var(--color-text);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 1px solid var(--color-border);
        }}

        td {{
            padding: 8px 12px;
            border-bottom: 1px solid var(--color-border);
            vertical-align: middle;
            overflow: hidden;
        }}

        /* Column widths */
        th:nth-child(1), td:nth-child(1) {{ width: 25%; }}
        th:nth-child(2), td:nth-child(2) {{ width: 40%; }}
        th:nth-child(3), td:nth-child(3) {{ width: 17%; }}
        th:nth-child(4), td:nth-child(4) {{ width: 18%; }}

        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: #fafafa; }}

        .param-path {{
            font-family: 'Courier New', monospace;
            color: var(--color-text);
            font-weight: 700;
            font-size: 13px;
            display: block;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}

        .status-ok {{ background: #dcfce7; color: var(--color-success); }}
        .status-error {{ background: #fee2e2; color: var(--color-error); }}
        .status-na {{ background: #f5f5f5; color: var(--color-neutral); }}

        .error-detail {{
            display: block;
            margin-top: 2px;
            font-size: 11px;
            color: var(--color-error);
            max-width: 400px;
        }}

        .footer {{
            text-align: center;
            color: var(--color-neutral);
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid var(--color-border);
            font-size: 11px;
        }}
    </style>
</head>
    <body>
        <div class="container">
            <div class="dashboard-header">
                <div class="header-left">
                    <div class="brand">
                        {f'<img src="data:image/jpeg;base64,{logo_b64}" alt="Logo" class="logo">' if logo_b64 else ""}
                        <h1>LLM API Compliance Report</h1>
                    </div>

                    <div class="meta-info">
                        <div class="meta-item">
                            <span class="meta-label">Provider</span>
                            <span class="meta-value">{provider}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Endpoint</span>
                            <span class="meta-value">{endpoint}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Base URL</span>
                            <span class="meta-value">{base_url}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Date</span>
                            <span class="meta-value">{self.report.get("test_time", "N/A")}</span>
                        </div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{self.total_tests}</div>
                        <div class="stat-label">Total Tests</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{self.passed_tests}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{self.failed_tests}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                </div>
            </div>

            <table>
"""

        if use_new_format:
            # Always show 4 columns for new format: Parameter | Value | Request Status | Validation Status
            html += """            <tr>
                <th>Parameter</th>
                <th>Value</th>
                <th>Request Status</th>
                <th>Validation Status</th>
            </tr>
"""
            for info in self.param_support_details:
                param = info.get("parameter", "")
                raw_value = info.get("value")
                if raw_value is None:
                    raw_value = info.get("variant_value")

                value_display = self._format_display_value(raw_value, truncate=False)
                # Escaping quotes for title attribute
                hover_text = str(value_display).replace('"', "&quot;")

                request_ok = info.get("request_ok", False)
                request_error = info.get("request_error")
                validation_ok = info.get("validation_ok", False)
                validation_error = info.get("validation_error")

                # Request status
                if request_ok:
                    request_status = '<span class="status-badge status-ok">✓ Success</span>'
                else:
                    error_msg = (
                        f'<span class="error-detail">{request_error}</span>'
                        if request_error
                        else ""
                    )
                    request_status = (
                        f'<span class="status-badge status-error">✕ Failed</span>{error_msg}'
                    )

                # Validation status
                if not request_ok:
                    validation_status = '<span class="status-badge status-na">Skipped</span>'
                elif validation_ok:
                    validation_status = '<span class="status-badge status-ok">✓ Valid</span>'
                else:
                    error_msg = (
                        f'<span class="error-detail">{validation_error}</span>'
                        if validation_error
                        else ""
                    )
                    validation_status = (
                        f'<span class="status-badge status-error">✕ Invalid</span>{error_msg}'
                    )

                html += f"""            <tr>
                <td><span class="param-path" title="{param}">{param}</span></td>
                <td><span class="param-path" title="{hover_text}">{value_display}</span></td>
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
                    status = '<span class="status-badge status-error">✕ Unsupported</span>'
                    reason = self.unsupported_params[param].get("reason", "")
                    if reason:
                        status += f'<span class="error-detail">{reason}</span>'
                else:
                    status = '<span class="status-badge status-ok">✓ Supported</span>'

                html += f"""            <tr>
                <td><span class="param-path">{param}</span></td>
                <td>{status}</td>
            </tr>
"""

        html += """        </table>

            <div class="footer">
                <p>Generated by LLM-Spec • R9S AI Infrastructure</p>
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
