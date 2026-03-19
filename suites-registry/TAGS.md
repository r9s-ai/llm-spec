# Test Tags

This document defines the recommended test tag taxonomy for `suites-registry`.

Tags are used to classify test intent and make suites easier to filter, review,
and expand over time. They are not currently enforced by the loader as a fixed
enum, but new route definitions should follow this document.

## Goals

Tags should help answer questions like:

- Is this test a minimal baseline, a parameter-focused test, or a realistic scenario?
- Is this test mainly about streaming, tool calling, multimodal input, or reasoning?
- Which tests should be included when validating one specific capability area?

## Tag Model

Use tags in two layers:

1. **Role tags**
2. **Capability tags**

Each test should usually have:

- exactly 1 role tag
- 0 to 2 capability tags

Avoid over-tagging. In most cases, 1 to 3 tags total is enough.

## Role Tags

### `baseline`

Use for the single minimum viable test of a route.

Purpose:

- verify the route works with the smallest supported request
- provide a stable sanity check

Rules:

- each route must have exactly one `baseline` test
- keep inputs minimal and low-risk
- avoid mixing in optional parameters unless they are required by the API

Example:

```json5
{
  name: "baseline",
  baseline: true,
  tags: ["baseline"],
}
```

### `parameter`

Use for tests whose main purpose is to validate support for one parameter, or a
small required dependency set for that parameter.

Purpose:

- answer “is this parameter supported?”
- provide focused regression coverage

Rules:

- keep unrelated parameters to a minimum
- required helper parameters are allowed
- if one parameter depends on another, cover both in `cover_params`

Examples:

- `tool_choice` together with `tools`
- `top_logprobs` together with `logprobs`
- `stream_options.include_usage` together with `stream`

### `scenario`

Use for realistic multi-parameter workflows that model common day-to-day usage.

Purpose:

- validate that useful combinations work together
- catch compatibility problems between individually supported parameters

Rules:

- may combine multiple parameters intentionally
- should reflect a real user workflow, not just an arbitrary bundle
- include all intentionally covered parameters in `cover_params`

Examples:

- structured output workflow
- tool calling workflow
- multimodal prompt with output controls

### `edge`

Use for boundary conditions, fragile interactions, or unusual but meaningful
inputs.

Purpose:

- stress known weak points
- catch behavior that is valid but easy to break

Examples:

- refusal cases
- complex multi-turn tool conversations
- unusual input modality combinations

### `compatibility`

Use for legacy, transitional, or compatibility-oriented API behavior.

Purpose:

- validate older but still supported request shapes
- document compatibility expectations explicitly

Examples:

- Chat Completions `functions`
- Chat Completions `function_call`

## Capability Tags

### `streaming`

Use when the test is primarily about streamed behavior.

Examples:

- `stream`
- `stream_options.include_usage`
- `stream_options.include_obfuscation`

### `tooling`

Use when the test is mainly about model tool use or tool orchestration.

Examples:

- `tools`
- `tool_choice`
- `parallel_tool_calls`
- realistic tool-calling scenarios

### `multimodal`

Use when the test includes multiple modalities in either input or output.

Examples:

- image input plus text
- text plus audio output

### `structured-output`

Use when the test focuses on constrained output formats.

Examples:

- JSON object output
- JSON schema output
- text configuration with structured formatting behavior

### `reasoning`

Use when the test targets reasoning-specific controls or outputs.

Examples:

- `reasoning.effort`
- `reasoning_effort`
- reasoning-only output fields

## Recommended Initial Tag Set

The recommended working set is:

- `baseline`
- `parameter`
- `scenario`
- `edge`
- `compatibility`
- `streaming`
- `tooling`
- `multimodal`
- `structured-output`
- `reasoning`

This set is intentionally small. Add new tags only when they introduce clear,
reusable meaning across multiple routes or providers.

## Tagging Guidelines

### Prefer one clear role

Good:

```json5
tags: ["parameter", "tooling"]
```

Avoid:

```json5
tags: ["parameter", "scenario", "edge", "tooling"]
```

### Use capability tags only when they add value

If a test is just a plain scalar parameter check, a single `parameter` tag is
often enough.

### Keep role and coverage separate

Tags describe **why the test exists**.

`cover_params` describes **which parameters the test is intended to cover**.

These are related, but not the same thing.

## `cover_params` Guidance

`cover_params` must be a list of `{ name, value }` objects.

Use it to record the intentional coverage of the test.

Single-parameter example:

```json5
cover_params: [
  { name: "temperature", value: 0.7 },
]
```

Dependent-parameter example:

```json5
cover_params: [
  { name: "tools", value: [{ type: "function" }] },
  { name: "tool_choice", value: "auto" },
]
```

Scenario example:

```json5
cover_params: [
  { name: "text.format.type", value: "json_schema" },
  { name: "text.verbosity", value: "low" },
  { name: "max_output_tokens", value: 200 },
]
```

## Suggested Conventions

### For route baselines

- `tags: ["baseline"]`

### For focused parameter tests

- `tags: ["parameter"]`
- `tags: ["parameter", "streaming"]`
- `tags: ["parameter", "tooling"]`
- `tags: ["parameter", "structured-output"]`
- `tags: ["parameter", "reasoning"]`

### For realistic workflows

- `tags: ["scenario", "tooling"]`
- `tags: ["scenario", "structured-output"]`
- `tags: ["scenario", "multimodal"]`

### For legacy support

- `tags: ["compatibility", "tooling"]`

## Non-Goals

This document does not define:

- a hard enum enforced by code
- pass/fail semantics
- model-specific inclusion rules

Those concerns should continue to be handled by loader validation, runtime
execution, and model-level `include_tests` / `exclude_tests`.
