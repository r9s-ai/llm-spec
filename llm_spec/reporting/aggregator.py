"""报告聚合器 - 合并多个 endpoint 的测试结果"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_spec.reporting.types import ReportData, TestSummary, UnsupportedParameter


class AggregatedReportCollector:
    """聚合多个 endpoint 的测试报告收集器

    用途：
    - 收集某个厂商的所有 endpoint 的测试报告
    - 合并参数、统计信息、错误日志
    - 保持参数的 endpoint 映射关系
    - 生成汇总报告
    """

    def __init__(self, provider: str):
        """初始化聚合报告收集器

        Args:
            provider: Provider 名称 (如 'openai', 'anthropic', 'gemini')
        """
        self.provider = provider
        self.endpoints: dict[str, ReportData] = {}  # endpoint -> report_data
        self.aggregation_time = datetime.now().isoformat()

    def add_endpoint_report(self, endpoint: str, report_data: ReportData) -> None:
        """添加单个 endpoint 的报告数据

        Args:
            endpoint: API endpoint (如 '/v1/chat/completions')
            report_data: 单个 endpoint 的报告 JSON 数据
        """
        self.endpoints[endpoint] = report_data

    def merge_reports(self, report_files: list[Path]) -> None:
        """从文件列表合并多个报告

        Args:
            report_files: 报告 JSON 文件的路径列表
        """
        for report_file in report_files:
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data: ReportData = json.load(f)
                    endpoint = str(report_data.get("endpoint", "unknown"))
                    self.add_endpoint_report(endpoint, report_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load report {report_file}: {e}")

    def get_aggregated_parameters(self) -> dict[str, dict[str, Any]]:
        """获取聚合后的参数信息，保持 endpoint 映射关系

        ✅ 修复后的逻辑：
        1. 先构建"不支持参数"的集合（从 unsupported 数组）
        2. 只有不在"不支持"集合中的参数才标记为 "supported"
        3. 在"不支持"集合中的参数标记为 "unsupported"

        Returns:
            参数聚合数据，格式：
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
            # 第一步：构建不支持参数的集合（便于快速查询）
            unsupported_params_list: list[UnsupportedParameter] = (
                report.get("parameters", {}).get("unsupported", [])
            )
            unsupported_param_names: dict[str, UnsupportedParameter] = {
                str(param.get("parameter")): param
                for param in unsupported_params_list
                if param.get("parameter")
            }

            # 第二步：获取所有参数（tested + unsupported）
            tested_params = set(report.get("parameters", {}).get("tested", []))
            all_params = tested_params | set(unsupported_param_names.keys())

            # 第三步：处理每个参数
            for param in all_params:
                if param not in aggregated:
                    aggregated[param] = {
                        'endpoints': {},
                        'support_count': 0,
                        'total_endpoints': len(all_endpoints),
                    }

                # ✅ 关键逻辑：检查参数是否在 unsupported 中
                if param in unsupported_param_names:
                    # 这个参数不支持
                    unsupported_info = unsupported_param_names[param]
                    aggregated[param]['endpoints'][endpoint] = {
                        'status': 'unsupported',
                        'reason': unsupported_info.get('reason', 'Unknown'),
                        'test_name': unsupported_info.get('test_name', ''),
                    }
                else:
                    # 这个参数支持（在 tested 中但不在 unsupported 中）
                    aggregated[param]['endpoints'][endpoint] = {
                        'status': 'supported',
                        'test_count': report.get("test_summary", {}).get("total_tests", 0),
                    }
                    aggregated[param]['support_count'] += 1

        return aggregated

    def get_aggregated_summary(self) -> dict[str, Any]:
        """获取聚合的统计摘要

        Returns:
            统计摘要，包括：
            - 总 endpoint 数
            - 总测试数
            - 通过/失败数
            - 参数统计
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

        # 去重错误日志（按 test_name 和 message）
        unique_errors = {}
        for error in error_list:
            key = f"{error.get('test_name', '')}_{error.get('message', '')}"
            if key not in unique_errors:
                unique_errors[key] = error

        aggregated_params = self.get_aggregated_parameters()

        return {
            'provider': self.provider,
            'aggregation_time': self.aggregation_time,
            'endpoints_count': len(self.endpoints),
            'endpoints': list(self.endpoints.keys()),
            'test_summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'pass_rate': f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "N/A",
            },
            'parameters': {
                'total_unique': len(aggregated_params),
                'fully_supported': sum(
                    1 for p in aggregated_params.values()
                    if p['support_count'] == p['total_endpoints']
                ),
                'partially_supported': sum(
                    1 for p in aggregated_params.values()
                    if 0 < p['support_count'] < p['total_endpoints']
                ),
                'unsupported': sum(
                    1 for p in aggregated_params.values()
                    if p['support_count'] == 0
                ),
            },
            'errors_count': len(unique_errors),
        }

    def finalize(self, output_dir: str = "./reports") -> dict[str, str]:
        """生成聚合报告

        Args:
            output_dir: 输出目录

        Returns:
            生成的文件路径字典 {'json': path, 'markdown': path, 'html': path}
        """
        if not self.endpoints:
            raise ValueError("No endpoint reports to aggregate. Call add_endpoint_report() first.")

        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir_name = f"{self.provider}_aggregated_{timestamp}"
        report_dir = Path(output_dir) / report_dir_name
        report_dir.mkdir(parents=True, exist_ok=True)

        # 生成聚合报告
        aggregated_params = self.get_aggregated_parameters()
        summary = self.get_aggregated_summary()

        report = {
            'report_type': 'aggregated',
            'provider': self.provider,
            'aggregation_time': self.aggregation_time,
            'summary': summary,
            'endpoints': {
                endpoint: {
                    'endpoint': endpoint,
                    'base_url': data.get('base_url', ''),
                    'test_summary': data.get('test_summary', {}),
                }
                for endpoint, data in self.endpoints.items()
            },
            'parameters': {
                'aggregated': self._serialize_aggregated_params(aggregated_params),
            },
        }

        # 写入 JSON 文件
        json_path = report_dir / "report.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 生成参数表格
        markdown_path = self._generate_markdown(report_dir, report)
        html_path = self._generate_html(report_dir, report)

        return {
            'json': str(json_path),
            'markdown': str(markdown_path),
            'html': str(html_path),
        }

    @staticmethod
    def _serialize_aggregated_params(
        aggregated_params: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """序列化聚合参数数据用于 JSON 输出"""
        result = {}
        for param_name, param_data in aggregated_params.items():
            result[param_name] = {
                'endpoints': param_data['endpoints'],
                'support_count': param_data['support_count'],
                'total_endpoints': param_data['total_endpoints'],
                'support_rate': f"{(param_data['support_count'] / param_data['total_endpoints'] * 100):.1f}%"
                    if param_data['total_endpoints'] > 0 else "N/A",
            }
        return result

    def _generate_markdown(self, report_dir: Path, report: dict[str, Any]) -> Path:
        """生成 Markdown 格式的聚合报告 - 按 endpoint 分组显示参数"""
        markdown_path = report_dir / "report.md"

        summary = report['summary']
        endpoints = report['endpoints']

        lines = []
        lines.append(f"# {summary['provider'].upper()} API 参数支持聚合报告\n")
        lines.append(f"**聚合时间**: {summary['aggregation_time']}\n")

        # 统计摘要
        lines.append("## 📊 统计摘要\n")
        lines.append(f"- **测试 Endpoint 数**: {summary['endpoints_count']}")
        lines.append(f"- **总测试数**: {summary['test_summary']['total_tests']}")
        lines.append(f"- **测试通过**: {summary['test_summary']['passed']} ✅")
        lines.append(f"- **测试失败**: {summary['test_summary']['failed']} ❌")
        lines.append(f"- **通过率**: {summary['test_summary']['pass_rate']}\n")

        # 按 endpoint 分组显示参数表格
        lines.append("## 📋 各 Endpoint 参数支持情况\n")

        for endpoint in sorted(endpoints.keys()):
            endpoint_data = endpoints[endpoint]
            ep_summary = endpoint_data['test_summary']

            # endpoint 标题和统计
            lines.append(f"### {endpoint}\n")
            lines.append(
                f"**测试统计**: {ep_summary.get('total_tests', 0)} 测试, "
                f"通过: {ep_summary.get('passed', 0)} ✅, "
                f"失败: {ep_summary.get('failed', 0)} ❌\n"
            )

            # 获取这个 endpoint 的原始报告数据（从endpoints中的raw数据）
            # 从聚合参数中提取该endpoint的参数信息
            aggregated_params = report['parameters']['aggregated']

            lines.append("| 参数 | 状态 |")
            lines.append("|------|------|")

            for param_name in sorted(aggregated_params.keys()):
                param_data = aggregated_params[param_name]
                endpoint_info = param_data['endpoints'].get(endpoint)

                if endpoint_info:
                    if endpoint_info['status'] == 'supported':
                        status = "✅ 支持"
                    else:
                        reason = endpoint_info.get('reason', '不支持')
                        status = f"❌ 不支持"
                        if reason:
                            status += f" ({reason.split(':')[0]})"
                    lines.append(f"| `{param_name}` | {status} |")

            lines.append("")

        # 错误统计
        if summary['errors_count'] > 0:
            lines.append(f"## ⚠️ 错误摘要\n")
            lines.append(f"共 {summary['errors_count']} 个错误\n")

        markdown_content = "\n".join(lines)
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return markdown_path

    def _generate_html(self, report_dir: Path, report: dict[str, Any]) -> Path:
        """生成 HTML 格式的聚合报告 - 按 endpoint 分组显示参数"""
        html_path = report_dir / "report.html"

        summary = report['summary']
        endpoints = report['endpoints']
        aggregated_params = report['parameters']['aggregated']

        # HTML 模板 - 按 endpoint 分组
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{summary['provider'].upper()} API 参数支持聚合报告</title>
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{summary['provider'].upper()} API 参数支持聚合报告</h1>
            <p>聚合时间: {summary['aggregation_time']}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>总测试数</h3>
                <div class="value">{summary['test_summary']['total_tests']}</div>
            </div>
            <div class="stat-card">
                <h3>测试通过 ✅</h3>
                <div class="value" style="color: #27ae60;">{summary['test_summary']['passed']}</div>
            </div>
            <div class="stat-card">
                <h3>测试失败 ❌</h3>
                <div class="value" style="color: #e74c3c;">{summary['test_summary']['failed']}</div>
            </div>
            <div class="stat-card">
                <h3>通过率</h3>
                <div class="value">{summary['test_summary']['pass_rate']}</div>
            </div>
        </div>

        <div class="section">
            <h2>📋 各 Endpoint 参数支持情况</h2>
        """

        # 按 endpoint 分组显示
        for endpoint in sorted(endpoints.keys()):
            endpoint_data = endpoints[endpoint]
            ep_summary = endpoint_data['test_summary']

            total_tests = ep_summary.get('total_tests', 0)
            passed = ep_summary.get('passed', 0)
            failed = ep_summary.get('failed', 0)

            html_content += f"""
            <div class="endpoint-group">
                <h3>{endpoint}</h3>
                <div class="endpoint-stats">
                    <span>🔬 {total_tests} 个测试</span>
                    <span class="pass">✅ {passed} 通过</span>
                    <span class="fail">❌ {failed} 失败</span>
                </div>
                <table>
                    <tr>
                        <th style="width: 40%;">参数</th>
                        <th style="width: 60%;">状态</th>
                    </tr>
            """

            # 为这个 endpoint 的参数创建表格
            for param_name in sorted(aggregated_params.keys()):
                param_data = aggregated_params[param_name]
                endpoint_info = param_data['endpoints'].get(endpoint)

                if endpoint_info:
                    if endpoint_info['status'] == 'supported':
                        status_html = '<span class="support">✅ 支持</span>'
                    else:
                        reason = endpoint_info.get('reason', '不支持')
                        reason_short = reason.split(':')[0] if reason else '不支持'
                        status_html = f'<span class="unsupport">❌ {reason_short}</span>'

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

        html_content += """
        </div>
    </div>
</body>
</html>
        """

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return html_path
