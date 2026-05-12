import { useState, useCallback, useEffect } from 'react'
import type { RunSummary } from '@/types'
import { loadFromFile, loadFromUrl, parseReport } from '@/lib/data-loader'

const req = (_url: string, body: object) => JSON.stringify(body, null, 2)
const res = (body: object, status = 200) => {
  void status
  return JSON.stringify(body, null, 2)
}

const openaiBaseUrl = 'https://api.openai.com/v1/chat/completions'
const openaiHeaders = { 'Content-Type': 'application/json', Authorization: 'Bearer sk-***redacted***' }
const anthropicBaseUrl = 'https://api.anthropic.com/v1/messages'
const anthropicHeaders = { 'Content-Type': 'application/json', 'x-api-key': 'sk-ant-***redacted***', 'anthropic-version': '2023-06-01' }

const SAMPLE_DATA: RunSummary = {
  startedAt: '2026-03-30T10:00:00.000Z',
  finishedAt: '2026-03-30T10:02:30.000Z',
  totalPassed: 5,
  totalFailed: 1,
  totalSkipped: 1,
  providers: [
    {
      provider: 'openai(chatCompletions)',
      model: 'gpt-4o-mini',
      apiBaseUrl: 'https://api.openai.com/v1',
      startedAt: '2026-03-30T10:00:00.000Z',
      finishedAt: '2026-03-30T10:01:00.000Z',
      passed: 3,
      failed: 1,
      skipped: 0,
      caseResults: [
        {
          id: 'basic_prompt',
          description: '基本对话测试',
          status: 'passed',
          durationMs: 850,
          coveredParams: ['messages', 'model'],
          detail: 'finish=stop, text="Hello! How can I help you today?"',
          httpTrace: {
            source: 'requests.log',
            testId: 'basic-prompt-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: openaiBaseUrl,
                  method: 'POST',
                  headers: openaiHeaders,
                  body: req(openaiBaseUrl, {
                    model: 'gpt-4o-mini',
                    messages: [{ role: 'user', content: 'Hello, say hi!' }],
                  }),
                },
                response: {
                  kind: 'response',
                  url: openaiBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 680,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    id: 'chatcmpl-basic-001',
                    object: 'chat.completion',
                    created: 1743331200,
                    model: 'gpt-4o-mini',
                    choices: [{
                      index: 0,
                      message: { role: 'assistant', content: 'Hello! How can I help you today?' },
                      finish_reason: 'stop',
                    }],
                    usage: { prompt_tokens: 12, completion_tokens: 9, total_tokens: 21 },
                  }),
                },
              },
            ],
          },
        },
        {
          id: 'streaming',
          description: '流式响应测试',
          status: 'passed',
          durationMs: 1200,
          coveredParams: ['messages', 'model', 'stream'],
          detail: 'finish=stop, stream=true, chunks=18',
          httpTrace: {
            source: 'requests.log',
            testId: 'streaming-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: openaiBaseUrl,
                  method: 'POST',
                  headers: openaiHeaders,
                  body: req(openaiBaseUrl, {
                    model: 'gpt-4o-mini',
                    messages: [{ role: 'user', content: 'Count from 1 to 5, one number per line.' }],
                    stream: true,
                  }),
                },
                response: {
                  kind: 'response',
                  url: openaiBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 1100,
                  headers: { 'Content-Type': 'text/event-stream', 'Transfer-Encoding': 'chunked' },
                  body: 'data: {"id":"chatcmpl-stream-001","object":"chat.completion.chunk","choices":[{"delta":{"content":"1"},"index":0}]}\n\ndata: {"id":"chatcmpl-stream-001","choices":[{"delta":{"content":"\\n2"},"index":0}]}\n\ndata: {"id":"chatcmpl-stream-001","choices":[{"delta":{"content":"\\n3"},"index":0}]}\n\ndata: {"id":"chatcmpl-stream-001","choices":[{"delta":{"content":"\\n4"},"index":0}]}\n\ndata: {"id":"chatcmpl-stream-001","choices":[{"delta":{"content":"\\n5"},"index":0}]}\n\ndata: {"id":"chatcmpl-stream-001","choices":[{"delta":{},"finish_reason":"stop","index":0}]}\n\ndata: [DONE]',
                },
              },
            ],
          },
        },
        {
          id: 'tool_calling',
          description: '工具调用测试',
          status: 'passed',
          durationMs: 2100,
          coveredParams: ['messages', 'model', 'tools', 'tool_choice'],
          detail: 'finish=tool_calls, tool_calls=1',
          httpTrace: {
            source: 'requests.log',
            testId: 'tool-calling-001',
            exchangeCount: 2,
            exchanges: [
              {
                request: {
                  url: openaiBaseUrl,
                  method: 'POST',
                  headers: openaiHeaders,
                  body: req(openaiBaseUrl, {
                    model: 'gpt-4o-mini',
                    messages: [{ role: 'user', content: 'What is the weather in San Francisco?' }],
                    tools: [{
                      type: 'function',
                      function: { name: 'get_weather', description: 'Get the current weather for a location', parameters: { type: 'object', properties: { location: { type: 'string' } }, required: ['location'] } },
                    }],
                    tool_choice: 'auto',
                  }),
                },
                response: {
                  kind: 'response',
                  url: openaiBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 1500,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    id: 'chatcmpl-tool-001',
                    model: 'gpt-4o-mini',
                    choices: [{
                      message: {
                        role: 'assistant',
                        content: null,
                        tool_calls: [{
                          id: 'call_abc123',
                          type: 'function',
                          function: { name: 'get_weather', arguments: '{"location":"San Francisco, CA"}' },
                        }],
                      },
                      finish_reason: 'tool_calls',
                    }],
                  }),
                },
              },
              {
                request: {
                  url: openaiBaseUrl,
                  method: 'POST',
                  headers: openaiHeaders,
                  body: req(openaiBaseUrl, {
                    model: 'gpt-4o-mini',
                    messages: [
                      { role: 'user', content: 'What is the weather in San Francisco?' },
                      { role: 'assistant', content: null, tool_calls: [{ id: 'call_abc123', type: 'function', function: { name: 'get_weather', arguments: '{"location":"San Francisco, CA"}' } }] },
                      { role: 'tool', tool_call_id: 'call_abc123', content: '{"temperature": 65, "condition": "Sunny", "humidity": 72}' },
                    ],
                  }),
                },
                response: {
                  kind: 'response',
                  url: openaiBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 800,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    id: 'chatcmpl-tool-002',
                    model: 'gpt-4o-mini',
                    choices: [{
                      message: {
                        role: 'assistant',
                        content: 'The weather in San Francisco is currently sunny with a temperature of 65°F and 72% humidity.',
                      },
                      finish_reason: 'stop',
                    }],
                  }),
                },
              },
            ],
          },
        },
        {
          id: 'json_mode',
          description: 'JSON 模式测试',
          status: 'failed',
          durationMs: 3500,
          coveredParams: ['messages', 'model', 'response_format'],
          error: 'Error: Expected valid JSON output but got malformed response (status=400)',
          httpTrace: {
            source: 'requests.log',
            testId: 'json-mode-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: openaiBaseUrl,
                  method: 'POST',
                  headers: openaiHeaders,
                  body: req(openaiBaseUrl, {
                    model: 'gpt-4o-mini',
                    messages: [{ role: 'user', content: 'Return a JSON object with name and age fields.' }],
                    response_format: { type: 'json_object' },
                  }),
                },
                response: {
                  kind: 'response',
                  url: openaiBaseUrl,
                  status: 400,
                  statusText: 'Bad Request',
                  durationMs: 3200,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    error: {
                      message: "Invalid response_format: the 'json_object' response format is not supported by this model endpoint. Please use a model that supports structured outputs.",
                      type: 'invalid_request_error',
                      param: 'response_format',
                      code: 'unsupported_parameter',
                    },
                  }, 400),
                },
              },
            ],
          },
        },
      ],
      allParams: ['messages', 'model', 'stream', 'tools', 'tool_choice', 'temperature', 'max_tokens', 'response_format'],
      coveredParams: ['messages', 'model', 'stream', 'tools', 'tool_choice', 'response_format'],
      untestedParams: ['temperature', 'max_tokens'],
    },
    {
      provider: 'anthropic',
      model: 'claude-3-5-haiku-latest',
      apiBaseUrl: 'https://api.anthropic.com/v1',
      startedAt: '2026-03-30T10:01:00.000Z',
      finishedAt: '2026-03-30T10:02:30.000Z',
      passed: 2,
      failed: 0,
      skipped: 1,
      caseResults: [
        {
          id: 'basic_prompt',
          description: '基本对话测试',
          status: 'passed',
          durationMs: 620,
          coveredParams: ['messages', 'model', 'max_tokens'],
          detail: 'stop_reason=end_turn, text="Hi there! How can I assist you?"',
          httpTrace: {
            source: 'requests.log',
            testId: 'anthropic-basic-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: anthropicBaseUrl,
                  method: 'POST',
                  headers: anthropicHeaders,
                  body: req(anthropicBaseUrl, {
                    model: 'claude-3-5-haiku-latest',
                    max_tokens: 1024,
                    messages: [{ role: 'user', content: 'Say hello!' }],
                  }),
                },
                response: {
                  kind: 'response',
                  url: anthropicBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 520,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    id: 'msg_basic_001',
                    type: 'message',
                    role: 'assistant',
                    model: 'claude-3-5-haiku-latest',
                    content: [{ type: 'text', text: 'Hi there! How can I assist you?' }],
                    stop_reason: 'end_turn',
                    stop_sequence: null,
                    usage: { input_tokens: 10, output_tokens: 12 },
                  }),
                },
              },
            ],
          },
        },
        {
          id: 'system_message',
          description: '系统消息测试',
          status: 'passed',
          durationMs: 780,
          coveredParams: ['messages', 'model', 'max_tokens', 'system'],
          detail: 'stop_reason=end_turn',
          httpTrace: {
            source: 'requests.log',
            testId: 'anthropic-system-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: anthropicBaseUrl,
                  method: 'POST',
                  headers: anthropicHeaders,
                  body: req(anthropicBaseUrl, {
                    model: 'claude-3-5-haiku-latest',
                    max_tokens: 1024,
                    system: 'You are a helpful math tutor. Always show your work step by step.',
                    messages: [{ role: 'user', content: 'What is 15 * 23?' }],
                  }),
                },
                response: {
                  kind: 'response',
                  url: anthropicBaseUrl,
                  status: 200,
                  statusText: 'OK',
                  durationMs: 680,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    id: 'msg_system_001',
                    type: 'message',
                    role: 'assistant',
                    model: 'claude-3-5-haiku-latest',
                    content: [{ type: 'text', text: "Let me calculate 15 × 23:\n\nStep 1: Break it down: 15 × 23 = 15 × 20 + 15 × 3\nStep 2: 15 × 20 = 300\nStep 3: 15 × 3 = 45\nStep 4: 300 + 45 = 345\n\nThe answer is **345**." }],
                    stop_reason: 'end_turn',
                    usage: { input_tokens: 28, output_tokens: 65 },
                  }),
                },
              },
            ],
          },
        },
        {
          id: 'streaming',
          description: '流式响应测试',
          status: 'skipped',
          durationMs: 0,
          coveredParams: ['stream'],
          detail: 'Streaming test skipped: endpoint not configured for streaming',
          httpTrace: {
            source: 'requests.log',
            testId: 'anthropic-streaming-001',
            exchangeCount: 1,
            exchanges: [
              {
                request: {
                  url: anthropicBaseUrl,
                  method: 'POST',
                  headers: anthropicHeaders,
                  body: req(anthropicBaseUrl, {
                    model: 'claude-3-5-haiku-latest',
                    max_tokens: 1024,
                    stream: true,
                    messages: [{ role: 'user', content: 'Tell me a short joke.' }],
                  }),
                },
                response: {
                  kind: 'error',
                  url: anthropicBaseUrl,
                  status: 503,
                  statusText: 'Service Unavailable',
                  durationMs: 150,
                  headers: { 'Content-Type': 'application/json' },
                  body: res({
                    type: 'error',
                    error: {
                      type: 'api_error',
                      message: 'Streaming is not available for this endpoint. The streaming feature has not been configured.',
                    },
                  }, 503),
                  error: 'Streaming is not available for this endpoint. The streaming feature has not been configured.',
                },
              },
            ],
          },
        },
      ],
      allParams: ['messages', 'model', 'max_tokens', 'system', 'stream', 'stop_sequences', 'temperature'],
      coveredParams: ['messages', 'model', 'max_tokens', 'system', 'stream'],
      untestedParams: ['stop_sequences', 'temperature'],
    },
  ],
}

export function useReportData() {
  const [report, setReport] = useState<RunSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const loadSample = useCallback(() => {
    try {
      const parsed = parseReport(SAMPLE_DATA)
      setReport(parsed)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  const loadFile = useCallback(async (file: File) => {
    setLoading(true)
    setError(null)
    try {
      const data = await loadFromFile(file)
      setReport(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadReport = useCallback((data: RunSummary) => {
    try {
      const parsed = parseReport(data)
      setReport(parsed)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  const reset = useCallback(() => {
    setReport(null)
    setError(null)
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const reportUrl = params.get('report')
    if (reportUrl) {
      setLoading(true)
      loadFromUrl(reportUrl)
        .then((data) => { setReport(data) })
        .catch((e) => { setError((e as Error).message) })
        .finally(() => { setLoading(false) })
    }
  }, [])

  return { report, error, loading, loadSample, loadFile, loadReport, reset }
}
