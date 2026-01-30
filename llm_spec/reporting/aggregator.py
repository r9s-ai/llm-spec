"""报告聚合器 - 合并多个 endpoint 的测试结果"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


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
        self.endpoints: Dict[str, Dict[str, Any]] = {}  # endpoint -> report_data
        self.aggregation_time = datetime.now().isoformat()

    def add_endpoint_report(self, endpoint: str, report_data: Dict[str, Any]) -> None:
        """添加单个 endpoint 的报告数据

        Args:
            endpoint: API endpoint (如 '/v1/chat/completions')
            report_data: 单个 endpoint 的报告 JSON 数据
        """
        self.endpoints[endpoint] = report_data

    def merge_reports(self, report_files: List[Path]) -> None:
        """从文件列表合并多个报告

        Args:
            report_files: 报告 JSON 文件的路径列表
        """
        for report_file in report_files:
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                    endpoint = report_data.get('endpoint', 'unknown')
                    self.add_endpoint_report(endpoint, report_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load report {report_file}: {e}")

    def get_aggregated_parameters(self) -> Dict[str, Dict[str, Any]]:
        """获取聚合后的参数信息，保持 endpoint 映射关系

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
        aggregated = {}
        all_endpoints = set(self.endpoints.keys())

        for endpoint, report in self.endpoints.items():
            # 处理已测试的参数
            tested_params = set(report.get('parameters', {}).get('tested', []))
            for param in tested_params:
                if param not in aggregated:
                    aggregated[param] = {
                        'endpoints': {},
                        'support_count': 0,
                        'total_endpoints': len(all_endpoints),
                    }
                aggregated[param]['endpoints'][endpoint] = {
                    'status': 'supported',
                    'test_count': report.get('test_summary', {}).get('total_tests', 0),
                }
                aggregated[param]['support_count'] += 1

            # 处理不支持的参数
            unsupported_params = report.get('parameters', {}).get('unsupported', [])
            for unsupported in unsupported_params:
                param_name = unsupported.get('parameter', '')
                if param_name:
                    if param_name not in aggregated:
                        aggregated[param_name] = {
                            'endpoints': {},
                            'support_count': 0,
                            'total_endpoints': len(all_endpoints),
                        }
                    if endpoint not in aggregated[param_name]['endpoints']:
                        aggregated[param_name]['endpoints'][endpoint] = {
                            'status': 'unsupported',
                            'reason': unsupported.get('reason', 'Unknown'),
                            'test_name': unsupported.get('test_name', ''),
                        }

        return aggregated

    def get_aggregated_summary(self) -> Dict[str, Any]:
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
        error_list = []

        for report in self.endpoints.values():
            summary = report.get('test_summary', {})
            total_tests += summary.get('total_tests', 0)
            passed_tests += summary.get('passed', 0)
            failed_tests += summary.get('failed', 0)
            error_list.extend(report.get('errors', []))

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

    def finalize(self, output_dir: str = "./reports") -> Dict[str, str]:
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
    def _serialize_aggregated_params(aggregated_params: Dict[str, Dict]) -> Dict[str, Any]:
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

    def _generate_markdown(self, report_dir: Path, report: Dict) -> Path:
        """生成 Markdown 格式的聚合报告"""
        markdown_path = report_dir / "report.md"

        summary = report['summary']
        endpoints = report['endpoints']
        aggregated_params = report['parameters']['aggregated']

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

        # 参数统计
        param_stats = summary['parameters']
        lines.append("## 📈 参数支持统计\n")
        lines.append(f"- **总参数数**: {param_stats['total_unique']}")
        lines.append(f"- **完全支持** (全endpoint): {param_stats['fully_supported']}")
        lines.append(f"- **部分支持** (部分endpoint): {param_stats['partially_supported']}")
        lines.append(f"- **不支持** (全endpoint): {param_stats['unsupported']}\n")

        # Endpoint 列表
        lines.append("## 🔗 测试的 Endpoint\n")
        for endpoint, ep_data in sorted(endpoints.items()):
            ep_summary = ep_data['test_summary']
            lines.append(
                f"- `{endpoint}` "
                f"({ep_summary.get('total_tests', 0)} 测试, "
                f"通过: {ep_summary.get('passed', 0)}, "
                f"失败: {ep_summary.get('failed', 0)})"
            )
        lines.append("")

        # 参数详细表格
        lines.append("## 📋 参数详细支持情况\n")
        lines.append("|  参数  | 支持度 | Endpoint 分布 |")
        lines.append("|--------|--------|--------|")

        for param_name in sorted(aggregated_params.keys()):
            param_data = aggregated_params[param_name]
            support_rate = param_data['support_rate']

            # 构建 endpoint 分布字符串
            endpoint_dist = []
            for endpoint in sorted(param_data['endpoints'].keys()):
                ep_status = param_data['endpoints'][endpoint]['status']
                status_char = "✅" if ep_status == 'supported' else "❌"
                endpoint_dist.append(f"{status_char} {endpoint}")

            endpoint_str = " / ".join(endpoint_dist)
            lines.append(f"| `{param_name}` | {support_rate} | {endpoint_str} |")

        lines.append("")

        # 错误统计
        if summary['errors_count'] > 0:
            lines.append(f"## ⚠️ 错误摘要\n")
            lines.append(f"共 {summary['errors_count']} 个错误\n")

        markdown_content = "\n".join(lines)
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        return markdown_path

    def _generate_html(self, report_dir: Path, report: Dict) -> Path:
        """生成 HTML 格式的聚合报告"""
        html_path = report_dir / "report.html"

        summary = report['summary']
        endpoints = report['endpoints']
        aggregated_params = report['parameters']['aggregated']

        # 简化的 HTML 模板
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{summary['provider'].upper()} API 参数支持聚合报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ font-size: 14px; opacity: 0.9; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card h3 {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
        .stat-card .value {{ font-size: 32px; font-weight: bold; color: #667eea; }}
        .table-section {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .table-section h2 {{ font-size: 18px; margin-bottom: 15px; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f8f8f8; padding: 12px; text-align: left; font-weight: 600; color: #333; border-bottom: 2px solid #ddd; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #fafafa; }}
        .endpoint {{ font-family: monospace; color: #667eea; }}
        .support-rate {{ font-weight: bold; }}
        .full-support {{ color: #27ae60; }}
        .partial-support {{ color: #f39c12; }}
        .no-support {{ color: #e74c3c; }}
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
                <h3>测试通过</h3>
                <div class="value" style="color: #27ae60;">{summary['test_summary']['passed']}</div>
            </div>
            <div class="stat-card">
                <h3>测试失败</h3>
                <div class="value" style="color: #e74c3c;">{summary['test_summary']['failed']}</div>
            </div>
            <div class="stat-card">
                <h3>通过率</h3>
                <div class="value">{summary['test_summary']['pass_rate']}</div>
            </div>
        </div>

        <div class="table-section">
            <h2>📊 参数支持统计</h2>
            <table>
                <tr>
                    <th>支持类型</th>
                    <th>数量</th>
                </tr>
                <tr>
                    <td>完全支持 (全endpoint)</td>
                    <td class="support-rate full-support">{summary['parameters']['fully_supported']}</td>
                </tr>
                <tr>
                    <td>部分支持 (部分endpoint)</td>
                    <td class="support-rate partial-support">{summary['parameters']['partially_supported']}</td>
                </tr>
                <tr>
                    <td>不支持 (全endpoint)</td>
                    <td class="support-rate no-support">{summary['parameters']['unsupported']}</td>
                </tr>
            </table>
        </div>

        <div class="table-section">
            <h2>🔗 测试的 Endpoint ({len(endpoints)})</h2>
            <table>
                <tr>
                    <th>Endpoint</th>
                    <th>总测试</th>
                    <th>通过</th>
                    <th>失败</th>
                </tr>
        """

        for endpoint in sorted(endpoints.keys()):
            ep_data = endpoints[endpoint]
            ep_summary = ep_data['test_summary']
            html_content += f"""        <tr>
                    <td><span class="endpoint">{endpoint}</span></td>
                    <td>{ep_summary.get('total_tests', 0)}</td>
                    <td style="color: #27ae60;">{ep_summary.get('passed', 0)}</td>
                    <td style="color: #e74c3c;">{ep_summary.get('failed', 0)}</td>
                </tr>
            """

        html_content += """            </table>
        </div>

        <div class="table-section">
            <h2>📋 参数详细支持情况</h2>
            <table>
                <tr>
                    <th>参数</th>
                    <th>支持率</th>
                    <th style="width: 50%;">Endpoint 分布</th>
                </tr>
        """

        for param_name in sorted(aggregated_params.keys()):
            param_data = aggregated_params[param_name]
            support_rate = param_data['support_rate']

            # 确定支持率样式
            if param_data['support_count'] == param_data['total_endpoints']:
                rate_class = "full-support"
            elif param_data['support_count'] == 0:
                rate_class = "no-support"
            else:
                rate_class = "partial-support"

            # 构建 endpoint 分布
            endpoint_dist_html = ""
            for endpoint in sorted(param_data['endpoints'].keys()):
                ep_status = param_data['endpoints'][endpoint]['status']
                if ep_status == 'supported':
                    endpoint_dist_html += f'<span class="endpoint" style="color: #27ae60;">✅ {endpoint}</span> / '
                else:
                    endpoint_dist_html += f'<span class="endpoint" style="color: #e74c3c;">❌ {endpoint}</span> / '

            endpoint_dist_html = endpoint_dist_html.rstrip(' / ')

            html_content += f"""        <tr>
                    <td><code>{param_name}</code></td>
                    <td class="support-rate {rate_class}">{support_rate}</td>
                    <td>{endpoint_dist_html}</td>
                </tr>
            """

        html_content += """            </table>
        </div>
    </div>
</body>
</html>
"""

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return html_path
