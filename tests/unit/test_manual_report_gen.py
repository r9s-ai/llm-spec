from pathlib import Path

from llm_spec.reporting.formatter import ParameterTableFormatter
from llm_spec.reporting.report_types import ReportData


def test_manual_generate_html_report(tmp_path: Path) -> None:
    """Generate a sample HTML report for manual inspection.

    This test always passes, but outputs the report location for the user to check.
    Run with: pytest tests/unit/test_manual_report_gen.py -s
    """

    mock_report_data: ReportData = {
        "provider": "Anthropic",
        "endpoint": "/v1/messages",
        "test_time": "2026-02-08T15:13:13",
        "base_url": "https://api.anthropic.com",
        "test_summary": {"total_tests": 12, "passed": 8, "failed": 2, "skipped": 2},
        "parameters": {
            "tested": ["model", "messages", "max_tokens", "stream", "temperature"],
            "untested": [],
            "supported": [],
            "unsupported": [],
        },
        "parameter_support_details": [
            {
                "parameter": "model",
                "request_ok": True,
                "validation_ok": True,
                "value": "claude-3-opus-20240229",
                "test_name": "test_model",
            },
            {
                "parameter": "messages",
                "request_ok": True,
                "validation_ok": True,
                "value": [{"role": "user", "content": "hello"}],
                "test_name": "test_messages",
            },
            {
                "parameter": "stream",
                "request_ok": False,
                "request_error": "HTTP 400: Stream not supported",
                "validation_ok": False,
                "value": True,
                "test_name": "test_stream",
            },
            {
                "parameter": "temperature",
                "request_ok": True,
                "validation_ok": False,
                "validation_error": "Value 2.0 exceeds max 1.0",
                "value": 2.0,
                "test_name": "test_temperature",
            },
            {
                "parameter": "top_p[0.5]",
                "variant_value": "0.5",
                "request_ok": True,
                "validation_ok": True,
                "value": 0.5,
                "test_name": "test_top_p_variant",
            },
        ],
        "response_fields": {},
        "errors": [],
        "details": {},
    }

    # Define output directory (using a fixed path for easy access, or tmp_path)
    # The user requested to check report format, so a fixed predictable path is better.
    output_dir = Path("reports/manual_debug_report")
    output_dir.mkdir(parents=True, exist_ok=True)

    formatter = ParameterTableFormatter(mock_report_data)

    # Geneate HTML
    html_path = formatter.save_html(str(output_dir))
    print(f"\nGenerated HTML Report: {html_path}")

    # Generate Markdown
    md_path = formatter.save_markdown(str(output_dir))
    print(f"Generated Markdown Report: {md_path}")

    # Generate JSON
    import json

    json_path = output_dir / "report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(mock_report_data, f, indent=2, ensure_ascii=False)
    print(f"Generated JSON Report: {json_path}")

    assert Path(html_path).exists()
    assert Path(md_path).exists()
    assert json_path.exists()
    assert "Anthropic" in Path(html_path).read_text()
    assert "# LLM API Compliance Report" in Path(md_path).read_text()
