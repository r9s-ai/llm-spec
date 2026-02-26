# suites-registry

Registry layout follows `DESIGN.md`.

## Structure

```text
providers/<provider>/
  provider.toml
  routes/*.json5
  models/*.toml
```

## Key Rules

- `routes/*.json5` are provider-agnostic route templates.
- `models/*.toml` declare route coverage (`routes = [...]`) and optional overrides.
- Runtime expands `route × model` into final suites.
- OpenAI-compatible providers can inherit routes with `routes_from = "openai"`.
- Shared file assets live in `suites-registry/assets/` (for `tests[].files`).
- Provider-only assets can be put in `providers/<provider>/assets/`.
- For JSON fields that require inline file content, use:
  - `$asset_base64(path)` -> base64 string
  - `$asset_data_uri(path,mime)` -> `data:<mime>;base64,...`

## Validate by Running

```bash
uv run python -m llm_spec run --suites suites-registry/providers -k test_baseline
```
