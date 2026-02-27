from pathlib import Path

from llm_spec.reporting.run_result_formatter import RunResultFormatter


def test_run_result_formatter_generates_md_and_html(tmp_path: Path) -> None:
    run_result = {
        "schema_version": "1.0",
        "run_id": "20260218_120000",
        "started_at": "2026-02-18T12:00:00Z",
        "finished_at": "2026-02-18T12:00:10Z",
        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
        "providers": [
            {
                "provider": "openai",
                "base_url": "https://api.openai.com",
                "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                "endpoints": [
                    {
                        "endpoint": "/v1/chat/completions",
                        "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                        "tests": [
                            {
                                "test_name": "test_param_temperature[0.7]",
                                "parameter": {
                                    "value": 0.7,
                                    "value_type": "float",
                                },
                                "result": {"status": "pass", "reason": None},
                            }
                        ],
                    }
                ],
            }
        ],
    }

    formatter = RunResultFormatter(run_result)
    md_path = formatter.save_markdown(str(tmp_path))
    html_path = formatter.save_html(str(tmp_path))

    assert Path(md_path).exists()
    assert Path(html_path).exists()
    md_text = Path(md_path).read_text(encoding="utf-8")
    html_text = Path(html_path).read_text(encoding="utf-8")
    assert "LLM Spec Run Report" in md_text
    assert "Parameter" not in md_text
    assert "Provider: <code>openai</code>" in html_text
    assert "<th>Parameter</th>" not in html_text
