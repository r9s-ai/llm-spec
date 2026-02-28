# suites-registry

Registry layout follows [`_docs/DESIGN.md`](../_docs/DESIGN.md).

## Structure

```text
providers/<provider>/
  provider.toml
  routes/*.json5
  models/*.toml
```

## How to Add a New Provider

### 1) OpenAI-compatible provider (recommended path)

Use this for providers that follow OpenAI endpoints/schemas.

1. Create provider directory: `providers/<provider>/`.
2. Add `provider.toml` with `api_family = "openai"` and `routes_from = "openai"`.
3. Add one or more model files under `models/*.toml`.
4. (Optional) Add route overrides in `routes/*.json5` if this provider differs from upstream OpenAI behavior.

Example `provider.toml`:

```toml
name = "DeepSeek"
api_family = "openai"
routes_from = "openai"
```

### 2) Provider with custom routes on top of inherited routes

If a provider is mostly OpenAI-compatible but has extra endpoints:

1. Inherit from a base provider with `routes_from`.
2. Add provider-specific route files under `routes/*.json5`.
3. Reference those new route names from model `routes = [...]`.

Local route files override inherited route files with the same route name.

### 3) Fully new API family

For a provider that is not OpenAI/Anthropic/Gemini compatible:

1. Create `provider.toml`.
2. Add all required route templates in `routes/*.json5`.
3. Add model files in `models/*.toml`.
4. Ensure the runtime has a matching adapter/schema implementation.

## Test Config File Rules

### `provider.toml`

- `api_family` controls protocol behavior (auth/header/model placement).
- Optional `routes_from` enables recursive route inheritance.
- Optional `[headers]` adds provider-level custom headers for all requests.

Complete template example:

```toml
# providers/<provider>/provider.toml
name = "Provider Display Name"
api_family = "openai" # openai | anthropic | gemini | xai (or supported adapter family)
doc = "https://provider.example.com/docs/api"

# Optional: inherit all resolved routes from another provider.
# Typical for OpenAI-compatible providers.
routes_from = "openai"

# Optional: provider-level static headers.
[headers]
x-custom-header = "my-value"
# anthropic-version = "2023-06-01"
```

OpenAI-compatible minimal template:

```toml
name = "My OpenAI-Compatible Provider"
api_family = "openai"
routes_from = "openai"
```

### `routes/<route>.json5`

- Defines one endpoint template and its test set.
- Should not contain `provider`; provider comes from directory name.
- Exactly one `tests[]` entry must set `baseline: true`.
- Baseline defaults live in `baseline.params`.
- If there are no default baseline parameters, set `baseline.params` to `{}` explicitly.
- For non-Gemini routes, do not hardcode `model` in `baseline.params`; runtime injects it.
- For Gemini-style URLs, use `{model}` in `endpoint` and runtime will replace it.
- `tests[]` entries follow existing suite format (`name`, `params`, `focus_param`, `baseline`, `tags`, etc.).
- `baseline` cannot be skipped.
- Parameter precedence at runtime is: `baseline.params` -> `test.params` (test-level values override same keys in baseline params).

Complete template example (non-Gemini):

```json5
{
  endpoint: "/v1/chat/completions",

  schemas: {
    response: "openai.ChatCompletionResponse",
    stream_chunk: "openai.ChatCompletionChunkResponse",
  },

  stream_expectations: {
    min_observations: 2,
    checks: [
      { type: "required_terminal", value: "[DONE]" },
    ],
  },

  tests: [
    {
      name: "baseline",
      params: {
        messages: [
          { role: "user", content: "Say hello in one short sentence." },
        ],
        max_tokens: 64,
      },
      baseline: true,
      tags: ["core"],
    },
    {
      name: "temperature",
      params: { temperature: 0.7 },
      focus_param: { name: "temperature", value: 0.7 },
      tags: ["core"],
    },
    {
      name: "stream",
      params: { stream: true },
      focus_param: { name: "stream", value: true },
      tags: ["streaming"],
    },
    {
      name: "file_upload",
      files: { file: "assets/audio/hello_en.mp3" },
      tags: ["multimodal"],
    },
  ],
}
```

Gemini-style endpoint template:

```json5
{
  endpoint: "/v1beta/models/{model}:generateContent",
  schemas: {
    response: "gemini.GenerateContentResponse",
  },
  tests: [
    {
      name: "baseline",
      baseline: true,
      params: {
        contents: [
          {
            role: "user",
            parts: [{ text: "Say hello" }],
          },
        ],
      },
      tags: ["core"],
    },
  ],
}
```

### `models/<model-id>.toml`

- File name is the model ID.
- `routes = [...]` is required and lists supported route names.
- Optional `skip_tests = [...]` removes route tests by test name, but cannot include `baseline`.
- Optional `[baseline_params_override]` deep-merges into route baseline params.
- Optional `[[extra_tests]]` appends model-specific tests (use `route = "<route_name>"` to target route).
- `[[extra_tests]]` entries use the same test schema as `routes[].tests`; if an extra test includes `params`, those values also override baseline params when that test runs.

Minimal template:

```toml
# providers/<provider>/models/<model-id>.toml
name = "Model Display Name"
routes = ["chat_completions"]
```

Complete template example:

```toml
# providers/<provider>/models/gpt-4o-mini.toml
name = "GPT-4o mini"
routes = ["chat_completions", "responses"]

# Optional: skip route tests by test name
skip_tests = [
  "logit_bias",
  "service_tier",
]

# Optional: override route baseline params (deep merge)
[baseline_params_override]
max_completion_tokens = 1024
temperature = 0.2

# Optional: append model-specific tests for a route
[[extra_tests]]
route = "chat_completions"
name = "reasoning_effort[high]"
description = "Model-specific reasoning_effort coverage"
params = { reasoning_effort = "high", max_completion_tokens = 2048 }
focus_param = { name = "reasoning_effort", value = "high" }
tags = ["core", "reasoning"]

# Variant values: declare one [[extra_tests]] block per value.
[[extra_tests]]
route = "chat_completions"
name = "reasoning_effort[medium]"
description = "Model-specific reasoning_effort=medium coverage"
params = { reasoning_effort = "medium", max_completion_tokens = 2048 }
focus_param = { name = "reasoning_effort", value = "medium" }
tags = ["core", "reasoning"]

[[extra_tests]]
route = "chat_completions"
name = "reasoning_effort[low]"
description = "Model-specific reasoning_effort=low coverage"
params = { reasoning_effort = "low", max_completion_tokens = 2048 }
focus_param = { name = "reasoning_effort", value = "low" }
tags = ["core", "reasoning"]

[[extra_tests]]
route = "responses"
name = "text.verbosity[low]"
description = "Model-specific verbosity check"
params = { text = { verbosity = "low" } }
focus_param = { name = "text.verbosity", value = "low" }
tags = ["rare"]
```

Notes for variants:

- `[[extra_tests]]` does not support automatic cartesian expansion.
- To test multiple values for one parameter, add multiple `[[extra_tests]]` blocks.
- Keep `name` unique for each variant (for filtering/reporting).

### Asset and file references

- Shared assets: `suites-registry/assets/`.
- Provider-specific assets: `providers/<provider>/assets/` (optional).
- For uploaded files in `tests[].files`, use relative paths; runtime resolves by config location and registry root.
- For inline binary content in JSON fields, use:
  - `$asset_base64(path)` for raw base64.
  - `$asset_data_uri(path,mime)` for `data:<mime>;base64,...`.

## Runtime Expansion Rules

- Runtime loads provider metadata, routes, and models.
- Routes are resolved with recursive `routes_from` inheritance.
- Each selected `model × route` pair becomes one expanded suite.
- Expansion pipeline:
  1. start from route template
  2. inject model (`baseline.params.model` for non-Gemini, endpoint placeholder replacement for Gemini)
  3. apply `baseline_params_override`
  4. remove `skip_tests`
  5. append `extra_tests`

## Validate by Running

```bash
uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -k baseline -v
```
