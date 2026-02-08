# llm-spec

llm-spec is a config-driven LLM API compatibility and parameter support probing tool. It turns
"does this parameter work, how well does it work, and where does it break" into repeatable,
aggregatable tests with reports that are readable by humans and consumable by machines.

If you're working on:
- Capability alignment across multiple model providers (OpenAI / Anthropic / Gemini / xAI / ...)
- Verifying what your gateway/proxy actually forwards upstream
- Regression testing during API upgrades (a parameter suddenly becomes unsupported)

llm-spec aims to provide an **evidence chain**: request → response → verdict → aggregated report.

## Vision: an accurate parameter probe

Compatibility testing is easy to skew by "flaky pass / flaky fail". llm-spec focuses on stability:

- **Control-variable testing**: start from a baseline request, then introduce one parameter/value at a time.
- **Structured response validation**: validate responses with Pydantic schemas and report missing paths.
- **Streaming completeness (stream rules)**: validate not only chunks, but also required events/terminal events.
- **Aggregatable reporting**: roll up multiple endpoints into a support matrix and readable reports.

## Key features

- **Multi-provider, multi-endpoint suites**: adapters + schemas + stream rules.
- **Parameter support probing**: attribute failures to HTTP errors, upstream errors, schema mismatches, or stream rule violations.
- **Response validation**: unary responses and streaming chunks validated with schemas.
- **Reports**:
  - Per endpoint: `report.json` / `report.md` / `report.html`
  - Per provider (multiple endpoints): `*_aggregated_*` (JSON/MD/HTML)
- **Structured request logging**: optional request/response/error logs for debugging and traceability.

## Supported providers and endpoints

Built-in suite configs live under `suites/`.

### OpenAI

Provider: `openai` (default `base_url=https://api.openai.com`)

Supported endpoints:
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `POST /v1/audio/speech` (binary audio response)
- `POST /v1/audio/transcriptions`
- `POST /v1/audio/translations`

Default models/baselines (from suite `base_params` or the endpoint itself):
- Chat Completions：`gpt-4o-mini`
- Responses：`gpt-4o-mini`
- Embeddings：`text-embedding-3-small`
- Images Generations：`dall-e-3` (also includes GPT image baseline `gpt-image-1.5`)
- Images Edits：`gpt-image-1.5`
- Audio Speech：`gpt-4o-mini-tts`
- Audio Transcriptions：`whisper-1` (also `gpt-4o-mini-transcribe` appears in variants)
- Audio Translations：`whisper-1`

### Anthropic

Provider: `anthropic` (default `base_url=https://api.anthropic.com`)

Supported endpoints:
- `POST /v1/messages`

Default model:
- Messages：`claude-haiku-4.5`

### Google Gemini

Provider: `gemini` (default `base_url=https://generativelanguage.googleapis.com`)

Supported endpoints:
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent` (streaming)
- `POST /v1beta/models/{model}:batchGenerateContent`
- `POST /v1beta/models/{model}:embedContent`
- `POST /v1beta/models/{model}:countTokens`

Default models/baselines (Gemini model is usually in the URL path):
- Generate：`gemini-3-flash-preview`（`/v1beta/models/gemini-3-flash-preview:generateContent`）
- StreamGenerate：`gemini-3-flash-preview`（`...:streamGenerateContent`）
- BatchGenerate：`gemini-3-flash-preview`（`...:batchGenerateContent`）
- Embed：`text-embedding-005`（`/v1beta/models/text-embedding-005:embedContent`）
- CountTokens：`gemini-2.5-flash`（`/v1beta/models/gemini-2.5-flash:countTokens`）

### xAI (OpenAI-compatible)

Provider: `xai` (default `base_url=https://api.x.ai/v1`)

Supported endpoints:
- `POST /v1/chat/completions`

Default model:
- Chat Completions：`grok-beta`

## Install with uv

This is a standard `pyproject.toml` project. Recommended: use **uv** for env/deps.

```bash
# 1) Create a venv (Python 3.11+)
uv venv -p 3.11

# 2) Install (including dev dependencies)
uv sync --extra dev

# 3) Activate (optional)
source .venv/bin/activate
# Or run without activation:
# uv run python -m llm_spec ...
```

## Configuration

Copy the example config and fill in API keys:

```bash
cp llm-spec.example.toml llm-spec.toml
```

Key fields in `llm-spec.toml`:

- `[report].output_dir`: report output directory (default `./reports`)
- `[log]`: logging settings (including request/response body logging)
- `[openai] / [anthropic] / [gemini] / [xai]`: `api_key` / `base_url` / `timeout`

Example (excerpt):

```toml
[report]
output_dir = "./reports"

[openai]
api_key = "sk-..."
base_url = "https://api.openai.com"
timeout = 30.0
```

## Config-driven suites (JSON5)

Built-in suites live under `suites/**/*.json5`. Each JSON5 file describes one **suite**
(typically one provider + endpoint). The `tests` array contains test cases (baseline / parameter probing /
streaming / file uploads / ...).

Minimal example (streaming):

```json5
{
  provider: "anthropic",
  endpoint: "/v1/messages",

  schemas: {
    response: "anthropic.MessagesResponse",
    stream_chunk: "anthropic.AnthropicStreamChunk",
  },

  base_params: {
    model: "claude-...",
    max_tokens: 128,
    messages: [{ role: "user", content: "Hello" }],
  },

  // (optional) suite-level stream rules shared by all stream tests
  stream_rules: {
    min_observations: 1,
    checks: [
      { type: "required_terminal", value: "message_stop" },
    ],
  },

  tests: [
    // 1) baseline: establish a known-good request
    { name: "test_baseline", is_baseline: true },

    // 2) probe one parameter: control-variable testing (change one thing)
    {
      name: "test_param_temperature",
      params: { temperature: 0.7 },
      test_param: { name: "temperature", value: 0.7 },
    },

    // 3) streaming test: can override suite.stream_rules
    {
      name: "test_streaming_basic",
      stream: true,
      params: { stream: true },
      test_param: { name: "stream", value: true },
      stream_rules: {
        min_observations: 1,
        checks: [
          { type: "required_sequence", values: ["message_start", "message_stop"] },
          { type: "required_terminal", value: "message_stop" },
        ],
      },
    },
  ],
}
```

More fields and examples: `_docs/WRITING_TESTCASES.md`.

## Running

llm-spec is config-driven: suites are JSON5 files under `suites/`. No Python test code is needed to add coverage.

### Run via CLI (recommended)

```bash
# List all discoverable tests (no requests)
uv run python -m llm_spec list

# Run (will call external APIs and write reports/<run_id>/...)
uv run python -m llm_spec run
```

### Filter runs

```bash
# Only run OpenAI
uv run python -m llm_spec run --provider openai

# Like pytest -k: substring match on "provider/endpoint::test_name"
uv run python -m llm_spec run -k "openai/v1/chat/completions"
uv run python -m llm_spec run --provider openai -k "test_param_temperature"
```

### Debug logging

Enable logging in `llm-spec.toml` under `[log]`.

```bash
uv run python -m llm_spec run --provider openai -k "openai/v1/chat/completions"
```

Note: each run creates a `run_id` (timestamp). All outputs go into `reports/<run_id>/...`.

### Run via pytest (dev/compat)

If you prefer pytest, you can also run (will call external APIs):

```bash
uv run pytest tests/integration/test_suite_runner.py -v
```

## Reports

### 1) Find the latest run directory

```bash
ls -lt reports | head
```

You will see something like:

```
reports/20260130_141530/
  openai_v1_chat_completions_20260130_141531/
    report.json
    report.md
    report.html
  openai_aggregated_20260130_141620/
    report.json
    report.md
    report.html
```

### 2) Open the HTML report

- Per endpoint: `reports/<run_id>/<provider>_<endpoint>_<timestamp>/report.html`
- Aggregated: `reports/<run_id>/<provider>_aggregated_<timestamp>/report.html`

Open it locally in your browser.

### 3) View JSON/Markdown

```bash
cat reports/<run_id>/openai_v1_responses_*/report.json
cat reports/<run_id>/openai_v1_responses_*/report.md
```

## What do reports look like? (example)

Below is a **mock example** showing how llm-spec can pinpoint failure modes: HTTP unsupported,
schema missing fields, or missing stream events.

### `report.md` (excerpt)

```md
## Parameter support

| Parameter | Request status | Validation status |
|------|----------|--------------|
| `temperature` | ✅ | ✅ |
| `response_format.type` | ❌ HTTP 400: Unsupported value: json_schema | N/A |
| `stream` | ✅ | ❌ Missing fields: stream.required_events (Missing required stream events: message_stop, terminal:message_stop) |
```

### `report.json` (excerpt)

```json
{
  "provider": "anthropic",
  "endpoint": "/v1/messages",
  "test_summary": { "total_tests": 12, "passed": 9, "failed": 3 },
  "errors": [
    {
      "test_name": "test_param_response_format",
      "type": "http_error",
      "status_code": 400,
      "error": "HTTP 400: {\"error\":{\"message\":\"Unsupported value: json_schema\"}}",
      "response_body": { "error": { "message": "Unsupported value: json_schema" } }
    },
    {
      "test_name": "test_streaming_basic",
      "type": "validation_error",
      "status_code": 200,
      "error": "Missing required stream events: message_stop, terminal:message_stop",
      "response_body": {
        "chunks_count": 18,
        "content_length": 42,
        "validation_errors": [
          "Missing required stream events: message_stop, terminal:message_stop"
        ]
      }
    }
  ],
  "parameter_support_details": [
    {
      "parameter": "temperature",
      "request_ok": true,
      "validation_ok": true,
      "http_status_code": 200,
      "test_name": "test_param_temperature",
      "value": 0.7
    },
    {
      "parameter": "response_format.type",
      "request_ok": false,
      "request_error": "HTTP 400: Unsupported value: json_schema",
      "validation_ok": false,
      "http_status_code": 400,
      "test_name": "test_param_response_format",
      "value": "json_schema"
    }
  ]
}
```

## Documentation

- **[_docs/WRITING_TESTCASES.md](_docs/WRITING_TESTCASES.md)**: how to write JSON5 suites (stream rules / schema config).
- **_docs/BLOG_LLM_SPEC.md**: design notes and background.

## Roadmap (direction, not a promise)

- **More endpoint coverage**: expand suites for providers and common gateway compatibility layers.
- **Multimodal and binary streaming**: bring audio/image/video streaming under the same rules framework.
- **Stronger accuracy mechanisms**: better failure attribution, sampling/flakiness hints, cross-run diffs.
- **CLI-first suite runner**: keep `tests/integration/test_suite_runner.py` as compat, then deprecate it once CLI coverage is complete.
- **CI/platformization**: publish reports as artifacts and build a team-facing capability baseline dashboard.

## License

MIT
