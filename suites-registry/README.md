# suites-registry

Community-maintained JSON5 suite registry for `llm-spec`.

## Layout

- `providers/<provider>/*.json5`: provider suite files.
- `schemas/`: schema files for suite validation.
- `scripts/`: registry tooling (lint/validate/format).

## Usage

By default, `llm-spec` reads suites from:

`./suites-registry/providers`

You can override with:

`uv run python -m llm_spec run --suites <path>`
