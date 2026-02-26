# Contributing Suites

## Rules

1. One provider per directory under `providers/`.
2. One endpoint-oriented suite per JSON5 file.
3. Keep `provider` and `endpoint` stable once published.
4. Add only reproducible tests with clear names.

## Review Checklist

1. JSON5 parses successfully.
2. `provider` and `endpoint` fields are present.
3. New/changed tests pass in mock mode.
4. No credentials or secrets are committed.

## Local Check

```bash
uv run python -m llm_spec run --suites suites-registry/providers -k test_baseline
```
