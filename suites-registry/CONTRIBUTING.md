# Contributing Suites

## Rules

1. One provider per directory under `providers/`.
2. Keep `provider.toml` at the provider root.
3. Put route templates under `routes/*.json5` and model definitions under `models/*.toml`.
4. Keep `route` and `model` IDs stable once published.
5. Add only reproducible tests with clear names.

## Review Checklist

1. JSON5 parses successfully.
2. Route JSON5 has `endpoint` + `tests`.
3. Model TOML has `routes` list.
4. New/changed tests pass in mock mode.
5. No credentials or secrets are committed.

## Local Check

```bash
uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -k baseline -v
```
