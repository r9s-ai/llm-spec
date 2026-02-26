# Mock Data for Integration Tests

This directory contains mock HTTP response data for offline integration testing.

## Directory Structure

```
mocks/
├── openai/
│   ├── v1_chat_completions/
│   │   ├── test_baseline.json              # Non-streaming response
│   │   ├── test_baseline_stream.jsonl      # Streaming response
│   │   ├── test_param_temperature.json
│   │   └── ...
│   ├── v1_embeddings/
│   └── ...
├── anthropic/
│   └── v1_messages/
├── gemini/
│   └── ...
└── README.md
```

## File Naming Convention

- **Non-streaming responses**: `{test_name}.json`
- **Streaming responses**: `{test_name}_stream.jsonl`

The `{test_name}` must match the test case name in the corresponding suite JSON5 file.

## File Formats

### Non-Streaming Response (JSON)

```json
{
  "status_code": 200,
  "headers": {
    "content-type": "application/json"
  },
  "body": {
    // Actual API response data
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "choices": [...],
    "usage": {...}
  }
}
```

**Fields**:
- `status_code`: HTTP status code (e.g., 200, 400, 500)
- `headers`: Response headers (optional, defaults to `{"content-type": "application/json"}`)
- `body`: The actual response body (must match provider's schema)

### Streaming Response (JSONL)

Each line represents one Server-Sent Event (SSE):

```jsonl
{"type": "chunk", "data": {"id": "chatcmpl-123", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": null}]}}
{"type": "chunk", "data": {"id": "chatcmpl-123", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": null}]}}
{"type": "chunk", "data": {"id": "chatcmpl-123", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}}
{"type": "done", "data": "[DONE]"}
```

**Fields**:
- `type`: Event type
  - `"chunk"`: Data chunk (will be formatted as `data: {json}\n\n`)
  - `"done"`: Terminal marker (will be formatted as `data: [DONE]\n\n`)
- `data`: Event payload
  - For `"chunk"`: The actual chunk data (must match provider's streaming schema)
  - For `"done"`: The string `"[DONE]"` (for OpenAI) or provider-specific terminal marker

## Usage

### Running Tests with Mock Data

```bash
# Use --mock flag to enable mock mode
pytest packages/core/tests/integration/test_suite_runner.py --mock -v

# Or set environment variable
MOCK_MODE=1 pytest packages/core/tests/integration/test_suite_runner.py -v

# Run specific test with mock
pytest packages/core/tests/integration/test_suite_runner.py --mock -k "test_baseline" -v
```

### Running Tests with Real API

```bash
# Without --mock flag, tests use real API calls
pytest packages/core/tests/integration/test_suite_runner.py -v
```

## Creating New Mock Data

### Step 1: Identify the Test Case

Find the test case in the route file (e.g., `suites-registry/providers/openai/routes/chat_completions.json5`):

```json5
{
  name: "test_my_feature",
  description: "Test my feature",
  params: {...}
}
```

### Step 2: Create Mock File

Create a file with the appropriate name:
- Non-streaming: `mocks/openai/v1_chat_completions/test_my_feature.json`
- Streaming: `mocks/openai/v1_chat_completions/test_my_feature_stream.jsonl`

### Step 3: Populate with Response Data

**Option A**: Manually create based on API documentation

**Option B**: Record from real API (future feature)

```bash
# Future: record mode to capture real responses
MOCK_RECORD=1 pytest packages/core/tests/integration/test_suite_runner.py -k "test_my_feature"
```

## Best Practices

1. **Keep mock data realistic**: Use actual API response structures
2. **Update regularly**: Sync with API changes to maintain test validity
3. **Test both modes**: Run tests with both `--mock` and real API periodically
4. **Document edge cases**: Create mock data for error scenarios (4xx, 5xx)
5. **Minimal but complete**: Include all required fields, omit unnecessary ones

## Provider-Specific Notes

### OpenAI
- Streaming terminal marker: `data: [DONE]\n\n`
- Common endpoints: `/v1/chat/completions`, `/v1/embeddings`

### Anthropic
- Streaming uses different event types: `message_start`, `content_block_delta`, `message_stop`
- Terminal marker: `message_stop` event

### Gemini
- Uses different URL structure and parameter wrapping
- Refer to existing suite configs for details

## Troubleshooting

### Mock file not found

```
FileNotFoundError: Mock data not found: packages/core/tests/integration/mocks/openai/v1_chat_completions/test_my_test.json
```

**Solution**: Create the missing mock file with the exact name shown in the error.

### Schema validation fails

```
validation_error: Missing required field: choices[0].message.content
```

**Solution**: Ensure your mock data matches the provider's response schema. Check the schema definitions in `llm_spec/validation/schemas/`.

### Streaming test fails

```
stream_error: Missing required stream events: [DONE]
```

**Solution**: Ensure your JSONL file includes the terminal marker:
```jsonl
{"type": "done", "data": "[DONE]"}
```

## Future Enhancements

- [ ] Auto-record mode to capture real API responses
- [ ] Mock data validation tool
- [ ] Error scenario templates (rate limits, auth errors, etc.)
- [ ] Mock data versioning for API version changes
