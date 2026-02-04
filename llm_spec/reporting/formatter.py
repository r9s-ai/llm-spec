"""报告格式化器 - 从 JSON 报告生成简洁表格"""

from __future__ import annotations

from pathlib import Path

from llm_spec.reporting.types import ReportData, SupportedParameter, UnsupportedParameter


class ParameterTableFormatter:
    """参数支持情况格式化器"""

    def __init__(self, report_data: ReportData):
        """
        Args:
            report_data: JSON 报告数据
        """
        self.report = report_data

        # 从报告中提取信息
        raw_tested = sorted(report_data.get("parameters", {}).get("tested", []))

        # 提取明确支持的参数
        self.supported_params: dict[str, SupportedParameter] = {}
        for p in report_data.get("parameters", {}).get("supported", []) or []:
            key = p.get("parameter", "")
            if key:
                self.supported_params[key] = p

        # 注意：同一个 parameter 可能在多个测试中多次被标记为 unsupported（不同 value/原因）。
        # 这里保留“最严重/最有信息量”的那条（优先带 HTTP 错误的 reason 或更长 reason）。
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

        # 只展示“叶子参数路径”，避免同时展示容器参数（如 contents）与其子路径（如 contents[0].parts）。
        # 规则：如果存在 tested 参数以 `p + "."` 或 `p + "["` 开头，则认为 p 是容器路径，应隐藏。
        # 只展示被明确标记为支持或不支持的参数
        # 过滤掉未被明确标记的嵌套参数
        all_tested = self._leaf_only(raw_tested)
        self.tested_params = self._filter_tested_params(all_tested)

        # 测试统计
        test_summary = report_data.get("test_summary", {})
        self.total_tests = test_summary.get("total_tests", 0)
        self.passed_tests = test_summary.get("passed", 0)
        self.failed_tests = test_summary.get("failed", 0)

    @staticmethod
    def _leaf_only(params: list[str]) -> list[str]:
        """仅保留叶子参数路径（隐藏容器/前缀路径）。

        示例：
        - 输入: ["contents", "contents[0].parts", "contents[0].parts[0].text"]
        - 输出: ["contents[0].parts[0].text"]
        """
        if not params:
            return []

        s = set(params)
        leaves: list[str] = []

        for p in params:
            # 如果任何其它参数以 p 为前缀（. 或 [），则 p 不是叶子
            if any((q != p) and (q.startswith(p + ".") or q.startswith(p + "[")) for q in s):
                continue
            leaves.append(p)

        return leaves

    @staticmethod
    def _filter_tested_params(params: list[str]) -> list[str]:
        """过滤测试参数，只保留被明确标记为支持或不支持的参数

        规则：
        1. 保留所有顶层参数（不包含 . 或 [ 的参数）
        2. 保留被明确标记的嵌套参数（在 supported_params 或 unsupported_params 中）
        """
        # 这里简化处理：只保留顶层参数和被明确标记的参数
        # 实际过滤在 generate_markdown 中根据 supported_params 和 unsupported_params 进行
        return params

    def _get_api_name(self) -> str:
        """获取 API 名称"""
        try:
            from llm_spec.reporting.api_registry import find_api_config

            endpoint = self.report.get("endpoint", "")
            config = find_api_config(endpoint)
            if config:
                return str(config.get("api_name", "Unknown API"))
        except Exception:
            pass

        # 智能推断
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
        """生成简洁的 Markdown 表格"""
        lines = []
        api_name = self._get_api_name()

        # 标题和统计信息
        lines.append(f"# {api_name} 参数支持报告")
        lines.append("")
        lines.append(f"**报告时间**: {self.report.get('test_time', 'N/A')}")
        lines.append(f"**总测试数**: {self.total_tests}")
        lines.append(f"**测试通过**: {self.passed_tests} ✅")
        lines.append(f"**测试失败**: {self.failed_tests} ❌")
        lines.append("")

        # 参数统计：只统计明确标记为支持或不支持的参数
        # 明确支持的参数（在 supported_params 中且不在 unsupported_params 中）
        supported_count = len(
            [p for p in self.supported_params if p not in self.unsupported_params]
        )
        # 明确不支持的参数
        unsupported_count = len(self.unsupported_params)
        # 只显示被明确标记为支持或不支持的参数
        self.display_params = [
            p
            for p in self.tested_params
            if p in self.supported_params or p in self.unsupported_params
        ]
        total_count = len(self.display_params)

        lines.append("## 参数支持情况")
        lines.append("")
        lines.append(f"- **已测试参数**: {total_count}")
        lines.append(f"  - ✅ 支持: {supported_count}")
        lines.append(f"  - ❌ 不支持: {unsupported_count}")
        lines.append("")

        # 参数表格
        if self.display_params:
            lines.append("## 参数详情")
            lines.append("")
            lines.append("| 参数 | 状态 |")
            lines.append("|------|------|")

            for param in self.display_params:
                if param in self.unsupported_params:
                    status = "❌ 不支持"
                    reason = self.unsupported_params[param].get("reason", "")
                    if reason:
                        status += f" ({reason})"
                else:
                    status = "✅ 支持"
                lines.append(f"| `{param}` | {status} |")

        lines.append("")
        return "\n".join(lines)

    def generate_html(self) -> str:
        """生成简洁的 HTML 报告"""
        api_name = self._get_api_name()
        # 参数统计：只统计明确标记为支持或不支持的参数
        supported_count = len(
            [p for p in self.supported_params if p not in self.unsupported_params]
        )
        unsupported_count = len(self.unsupported_params)
        total_count = len(self.display_params)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_name} 参数支持报告</title>
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
        .supported {{ color: #4caf50; font-weight: bold; }}
        .unsupported {{ color: #f44336; font-weight: bold; }}

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
        <h1>📋 {api_name} 参数支持报告</h1>

        <div class="summary">
            <h2>测试概览</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{self.total_tests}</div>
                    <div class="stat-label">总测试数</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{self.passed_tests}</div>
                    <div class="stat-label">通过 ✅</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{self.failed_tests}</div>
                    <div class="stat-label">失败 ❌</div>
                </div>
            </div>
            <p><strong>报告时间</strong>: {self.report.get("test_time", "N/A")}</p>
        </div>

        <div class="summary">
            <h2>参数支持情况</h2>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{total_count}</div>
                    <div class="stat-label">已测试参数</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{supported_count}</div>
                    <div class="stat-label">支持 ✅</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{unsupported_count}</div>
                    <div class="stat-label">不支持 ❌</div>
                </div>
            </div>
        </div>

        <h2>参数详情</h2>
        <table>
            <tr>
                <th>参数</th>
                <th>状态</th>
            </tr>
"""

        for param in self.display_params:
            if param in self.unsupported_params:
                status = '<span class="unsupported">❌ 不支持</span>'
                reason = self.unsupported_params[param].get("reason", "")
                if reason:
                    status += f" ({reason})"
            else:
                status = '<span class="supported">✅ 支持</span>'
                status = "<span>❓ 未知（未明确标记支持状态）</span>"

            html += f"""            <tr>
                <td><span class="param-path">{param}</span></td>
                <td>{status}</td>
            </tr>
"""

        html += """        </table>

        <div class="footer">
            <p>此报告由 llm-spec 自动生成</p>
        </div>
    </div>
</body>
</html>"""

        return html

    def save_markdown(self, output_dir: str = "reports") -> str:
        """保存 Markdown 报告"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{output_dir}/report.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())

        return filename

    def save_html(self, output_dir: str = "reports") -> str:
        """保存 HTML 报告"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{output_dir}/report.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.generate_html())

        return filename
