import type {
  HttpTraceExchange,
  ProviderSummary,
  RunProgressHandler,
  RunSummary,
  StandardApiType,
  TestCaseHttpTrace,
  TestCaseResult,
} from '@/types'

interface BrowserRunConfig {
  apiType: StandardApiType
  apiKey?: string
  apiBaseUrl?: string
  model: string
  timeoutMs: number
  targetCases?: string
  customHeaders?: Record<string, string>
  apiVersion?: string
  failFast: boolean
  onProgress?: RunProgressHandler
}

interface BrowserCase {
  id: string
  description: string
  covers: string[]
  precondition?: () => string | undefined
  run: (testId: string) => Promise<BrowserCaseRunResult>
}

interface BrowserCaseRunResult {
  detail?: string
  exchanges: HttpTraceExchange[]
}

interface FetchTraceResult {
  text: string
  status: number
  statusText: string
  chunks?: number
  exchange: HttpTraceExchange
}

class BrowserCaseError extends Error {
  exchanges: HttpTraceExchange[]

  constructor(message: string, exchanges: HttpTraceExchange[]) {
    super(message)
    this.name = 'BrowserCaseError'
    this.exchanges = exchanges
  }
}

const PARAMS: Record<StandardApiType, string[]> = {
  'openai.chat': ['messages', 'model', 'stream', 'temperature', 'response_format'],
  'openai.responses': ['input', 'model', 'instructions', 'stream', 'temperature'],
  'anthropic.messages': ['messages', 'model', 'max_tokens', 'system', 'temperature'],
  'gemini.generateContent': ['contents', 'model', 'systemInstruction', 'generationConfig'],
}

export const OPENAI_CHAT_SERVED_MODEL_IDS = [
  'gpt-5.5',
  'gpt-5.5-2026-04-23',
  'gpt-5.4',
  'gpt-5.4-2026-03-05',
  'gpt-5.4-mini',
  'gpt-5.4-mini-2026-03-17',
  'gpt-5.4-nano',
  'gpt-5.4-nano-2026-03-17',
  'gpt-5.3-codex',
  'chat-latest',
  'gpt-5.3-chat-latest',
  'gpt-5.2',
  'gpt-5.2-2025-12-11',
  'gpt-5.2-chat-latest',
  'gpt-5.2-pro',
  'gpt-5.2-pro-2025-12-11',
  'gpt-5.2-codex',
  'gpt-5.1',
  'gpt-5.1-2025-11-13',
  'gpt-5.1-codex',
  'gpt-5.1-codex-mini',
  'gpt-5.1-mini',
  'gpt-5.1-chat-latest',
  'gpt-5',
  'gpt-5-mini',
  'gpt-5-nano',
  'gpt-5-2025-08-07',
  'gpt-5-mini-2025-08-07',
  'gpt-5-nano-2025-08-07',
  'gpt-5-chat-latest',
  'gpt-4.1',
  'gpt-4.1-mini',
  'gpt-4.1-nano',
  'gpt-4.1-2025-04-14',
  'gpt-4.1-mini-2025-04-14',
  'gpt-4.1-nano-2025-04-14',
  'o4-mini',
  'o4-mini-2025-04-16',
  'o3',
  'o3-2025-04-16',
  'o3-mini',
  'o3-mini-2025-01-31',
  'o1',
  'o1-2024-12-17',
  'gpt-4o',
  'gpt-4o-2024-11-20',
  'gpt-4o-2024-08-06',
  'gpt-4o-2024-05-13',
  'gpt-4o-audio-preview',
  'gpt-4o-audio-preview-2024-12-17',
  'gpt-4o-audio-preview-2025-06-03',
  'gpt-4o-mini-audio-preview',
  'gpt-4o-mini-audio-preview-2024-12-17',
  'gpt-4o-realtime-preview',
  'gpt-4o-realtime-preview-2024-12-17',
  'gpt-4o-mini-realtime-preview',
  'gpt-4o-mini-realtime-preview-2024-12-17',
  'gpt-4o-search-preview',
  'gpt-4o-search-preview-2025-03-11',
  'gpt-4o-mini-search-preview',
  'gpt-4o-mini-search-preview-2025-03-11',
  'gpt-4o-mini',
  'gpt-4o-mini-2024-07-18',
  'gpt-audio-1.5',
  'gpt-audio',
  'gpt-audio-2025-08-28',
  'gpt-audio-mini',
  'gpt-audio-mini-2025-12-15',
  'gpt-audio-mini-2025-10-06',
  'gpt-realtime-2',
  'gpt-realtime-1.5',
  'gpt-realtime',
  'gpt-realtime-2025-08-28',
  'gpt-realtime-mini',
  'gpt-realtime-mini-2025-12-15',
  'gpt-realtime-mini-2025-10-06',
  'gpt-4-turbo',
  'gpt-4-turbo-2024-04-09',
  'gpt-4',
  'gpt-4-0613',
  'gpt-3.5-turbo',
  'gpt-3.5-turbo-16k',
  'gpt-3.5-turbo-0125',
  'gpt-3.5-turbo-1106',
] as const

export const OPENAI_RESPONSES_ONLY_SERVED_MODEL_IDS = [
  'gpt-5.5-pro',
  'gpt-5.5-pro-2026-04-23',
  'gpt-5.4-pro',
  'gpt-5.4-pro-2026-03-05',
  'gpt-5-codex',
  'gpt-5-pro',
  'gpt-5-pro-2025-10-06',
  'gpt-5.1-codex-max',
  'o1-pro',
  'o1-pro-2025-03-19',
  'o3-pro',
  'o3-pro-2025-06-10',
  'o3-deep-research',
  'o3-deep-research-2025-06-26',
  'o4-mini-deep-research',
  'o4-mini-deep-research-2025-06-26',
  'computer-use-preview',
  'computer-use-preview-2025-03-11',
] as const

export const OPENAI_RESPONSES_SERVED_MODEL_IDS = [
  ...OPENAI_CHAT_SERVED_MODEL_IDS,
  ...OPENAI_RESPONSES_ONLY_SERVED_MODEL_IDS,
] as const

type GeminiGenerateContentModelKind = 'text' | 'image' | 'tts'

interface GeminiServedGenerateContentModel {
  id: string
  kind: GeminiGenerateContentModelKind
}

// Source: Google Gemini model pages and deprecations page checked on 2026-05-12.
// This browser catalog mirrors the Node runner and only includes generateContent smoke targets.
export const GEMINI_TEXT_SERVED_MODEL_IDS = [
  'gemini-3.1-pro-preview',
  'gemini-3.1-pro-preview-customtools',
  'gemini-3-flash-preview',
  'gemini-3.1-flash-lite',
  'gemini-3.1-flash-lite-preview',
  'gemini-2.5-pro',
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash',
  'gemini-2.0-flash-001',
  'gemini-2.0-flash-lite',
  'gemini-2.0-flash-lite-001',
  'gemini-robotics-er-1.6-preview',
] as const

export const GEMINI_IMAGE_SERVED_MODEL_IDS = [
  'gemini-3.1-flash-image-preview',
  'gemini-3-pro-image-preview',
  'gemini-2.5-flash-image',
] as const

export const GEMINI_TTS_SERVED_MODEL_IDS = [
  'gemini-3.1-flash-tts-preview',
  'gemini-2.5-flash-preview-tts',
  'gemini-2.5-pro-preview-tts',
] as const

export const GEMINI_GENERATE_CONTENT_SERVED_MODEL_IDS = [
  ...GEMINI_TEXT_SERVED_MODEL_IDS,
  ...GEMINI_IMAGE_SERVED_MODEL_IDS,
  ...GEMINI_TTS_SERVED_MODEL_IDS,
] as const

const GEMINI_SERVED_GENERATE_CONTENT_MODELS: readonly GeminiServedGenerateContentModel[] = [
  ...GEMINI_TEXT_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'text' as const })),
  ...GEMINI_IMAGE_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'image' as const })),
  ...GEMINI_TTS_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'tts' as const })),
]

function providerNameForApiType(apiType: StandardApiType): string {
  if (apiType === 'openai.chat') {
    return 'openai(chatCompletions)'
  }
  if (apiType === 'openai.responses') {
    return 'openai(responses)'
  }
  if (apiType === 'anthropic.messages') {
    return 'anthropic'
  }
  return 'gemini'
}

function aliasesForApiType(apiType: StandardApiType): string[] {
  if (apiType === 'openai.chat') {
    return ['openai', 'openai.chat', 'chat', 'chatcompletions', 'openai.chatcompletions']
  }
  if (apiType === 'openai.responses') {
    return ['openai', 'openai.responses', 'responses']
  }
  if (apiType === 'anthropic.messages') {
    return ['anthropic', 'anthropic.messages', 'claude', 'claude.messages', 'messages']
  }
  return ['gemini', 'gemini.generatecontent', 'google', 'google.generatecontent', 'genai']
}

function defaultBaseUrl(apiType: StandardApiType): string {
  if (apiType === 'anthropic.messages') {
    return 'https://api.anthropic.com/v1'
  }
  if (apiType === 'gemini.generateContent') {
    return 'https://generativelanguage.googleapis.com/v1beta'
  }
  return 'https://api.openai.com/v1'
}

function appendEndpoint(baseUrl: string | undefined, fallbackBaseUrl: string, endpointPath: string): string {
  const cleanBase = (baseUrl?.trim() || fallbackBaseUrl).replace(/\/+$/, '')
  const cleanPath = endpointPath.startsWith('/') ? endpointPath : `/${endpointPath}`
  if (cleanBase.endsWith(cleanPath)) {
    return cleanBase
  }
  return `${cleanBase}${cleanPath}`
}

function buildGeminiEndpoint(config: BrowserRunConfig, model = config.model): string {
  const cleanBase = (config.apiBaseUrl?.trim() || defaultBaseUrl(config.apiType)).replace(/\/+$/, '')
  const baseWithApiVersion = config.apiVersion && !config.apiBaseUrl
    ? `https://generativelanguage.googleapis.com/${config.apiVersion}`
    : cleanBase
  const endpoint = baseWithApiVersion.includes(':generateContent')
    ? baseWithApiVersion
    : `${baseWithApiVersion}/models/${encodeURIComponent(model)}:generateContent`
  const separator = endpoint.includes('?') ? '&' : '?'
  return `${endpoint}${separator}key=${encodeURIComponent(config.apiKey ?? '')}`
}

function sanitizeUrl(url: string): string {
  try {
    const parsed = new URL(url)
    if (parsed.searchParams.has('key')) {
      parsed.searchParams.set('key', '***REDACTED***')
    }
    return parsed.toString()
  } catch {
    return url
  }
}

function sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
  const sanitized: Record<string, string> = {}
  for (const [key, value] of Object.entries(headers)) {
    const lowerKey = key.toLowerCase()
    if (lowerKey.includes('authorization') || lowerKey.includes('api-key') || lowerKey.includes('x-api-key')) {
      sanitized[key] = '***REDACTED***'
    } else {
      sanitized[key] = value
    }
  }
  return sanitized
}

function responseHeadersToRecord(headers: Headers): Record<string, string> {
  const output: Record<string, string> = {}
  headers.forEach((value, key) => {
    output[key] = value
  })
  return output
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function truncate(value: string, maxLength = 180): string {
  if (value.length <= maxLength) {
    return value
  }
  return `${value.slice(0, maxLength - 3)}...`
}

function parseJson(text: string): unknown {
  if (!text.trim()) {
    return undefined
  }
  return JSON.parse(text)
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return String(error)
}

async function readStreamBody(response: Response): Promise<{ text: string; chunks: number }> {
  if (!response.body) {
    return { text: '', chunks: 0 }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let text = ''
  let chunks = 0

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    chunks += 1
    text += decoder.decode(value, { stream: true })
  }

  text += decoder.decode()
  return { text, chunks }
}

async function tracedFetch(options: {
  url: string
  method: string
  headers: Record<string, string>
  body?: unknown
  timeoutMs: number
  stream?: boolean
}): Promise<FetchTraceResult> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => {
    controller.abort()
  }, options.timeoutMs)
  const bodyText = options.body === undefined ? undefined : prettyJson(options.body)
  const exchange: HttpTraceExchange = {
    request: {
      url: sanitizeUrl(options.url),
      method: options.method,
      headers: sanitizeHeaders(options.headers),
      body: bodyText,
    },
  }
  const started = performance.now()

  try {
    const response = await fetch(options.url, {
      method: options.method,
      headers: options.headers,
      body: bodyText,
      signal: controller.signal,
    })
    const durationMs = Math.round(performance.now() - started)
    const body = options.stream ? await readStreamBody(response) : { text: await response.text(), chunks: undefined }
    exchange.response = {
      kind: 'response',
      url: sanitizeUrl(options.url),
      status: response.status,
      statusText: response.statusText,
      durationMs,
      headers: responseHeadersToRecord(response.headers),
      body: body.text,
    }

    if (!response.ok) {
      throw new BrowserCaseError(
        `${response.status} ${response.statusText}: ${truncate(body.text, 260)}`,
        [exchange],
      )
    }

    return {
      text: body.text,
      status: response.status,
      statusText: response.statusText,
      chunks: body.chunks,
      exchange,
    }
  } catch (error) {
    if (error instanceof BrowserCaseError) {
      throw error
    }

    const durationMs = Math.round(performance.now() - started)
    const message = getErrorMessage(error)
    exchange.response = {
      kind: 'error',
      url: sanitizeUrl(options.url),
      durationMs,
      headers: {},
      error: message,
    }
    throw new BrowserCaseError(
      `${message}. Browser direct mode requires the API to allow CORS; switch to backend mode if this endpoint blocks browser requests.`,
      [exchange],
    )
  } finally {
    window.clearTimeout(timer)
  }
}

function buildOpenAIHeaders(config: BrowserRunConfig): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${config.apiKey ?? ''}`,
    ...(config.customHeaders ?? {}),
  }
}

function buildAnthropicHeaders(config: BrowserRunConfig): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'x-api-key': config.apiKey ?? '',
    'anthropic-version': '2023-06-01',
    'anthropic-dangerous-direct-browser-access': 'true',
    ...(config.customHeaders ?? {}),
  }
}

function buildJsonHeaders(config: BrowserRunConfig): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(config.customHeaders ?? {}),
  }
}

function summarizeOpenAIChat(text: string): string {
  const data = parseJson(text) as {
    choices?: Array<{ finish_reason?: string; message?: { content?: unknown } }>
  }
  const choice = data.choices?.[0]
  const content = typeof choice?.message?.content === 'string' ? choice.message.content : ''
  return `finish=${choice?.finish_reason ?? 'unknown'}, text="${truncate(content)}"`
}

function summarizeOpenAIResponses(text: string): string {
  const data = parseJson(text) as { status?: string; output_text?: unknown; output?: unknown[] }
  const outputText = typeof data.output_text === 'string' ? data.output_text : ''
  return `status=${data.status ?? 'unknown'}, output_items=${data.output?.length ?? 0}, text="${truncate(outputText)}"`
}

function modelCatalogCaseId(prefix: 'model_' | 'responses_model_', model: string): string {
  return `${prefix}${model.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`
}

function buildGeminiModelCatalogBody(model: GeminiServedGenerateContentModel): unknown {
  if (model.kind === 'image') {
    return {
      contents: [{ role: 'user', parts: [{ text: 'Generate a simple one-color square icon.' }] }],
      generationConfig: {
        responseModalities: ['IMAGE'],
        imageConfig: {
          aspectRatio: '1:1',
          imageSize: '1K',
        },
      },
    }
  }

  if (model.kind === 'tts') {
    return {
      contents: [{ role: 'user', parts: [{ text: 'Say: ok.' }] }],
      generationConfig: {
        responseModalities: ['AUDIO'],
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: {
              voiceName: 'Kore',
            },
          },
        },
      },
    }
  }

  return {
    contents: [{ role: 'user', parts: [{ text: 'Reply with exactly: ok' }] }],
    generationConfig: {
      maxOutputTokens: 64,
    },
  }
}

function isOpenAICompatibilityGateway(apiBaseUrl: string | undefined): boolean {
  if (!apiBaseUrl) {
    return false
  }
  try {
    const hostname = new URL(apiBaseUrl).hostname.toLowerCase()
    return !(hostname === 'api.openai.com' || hostname.endsWith('.openai.com'))
  } catch {
    return false
  }
}

function isLongRunningResponsesModel(model: string): boolean {
  const normalized = model.toLowerCase()
  return normalized.includes('-pro') || normalized.includes('deep-research')
}

function buildOpenAIModelCatalogPrecondition(config: BrowserRunConfig, apiSurface: 'chat.completions' | 'responses') {
  return () =>
    isOpenAICompatibilityGateway(config.apiBaseUrl)
      ? `OpenAI model catalog smoke tests target native OpenAI model IDs; skip ${apiSurface} on compatibility gateway ${config.apiBaseUrl ?? '(unknown)'}`
      : undefined
}

function buildOpenAIChatModelCatalogCases(config: BrowserRunConfig, url: string, headers: Record<string, string>): BrowserCase[] {
  return OPENAI_CHAT_SERVED_MODEL_IDS.map((model) => ({
    id: modelCatalogCaseId('model_', model),
    description: `OpenAI served model smoke: ${model}`,
    covers: ['model'],
    precondition: buildOpenAIModelCatalogPrecondition(config, 'chat.completions'),
    run: async () => {
      const result = await tracedFetch({
        url,
        method: 'POST',
        headers,
        timeoutMs: config.timeoutMs,
        body: {
          model,
          messages: [{ role: 'user', content: 'Reply with exactly: ok' }],
        },
      })
      return { detail: `model=${model}, ${summarizeOpenAIChat(result.text)}`, exchanges: [result.exchange] }
    },
  }))
}

function buildOpenAIResponsesModelCatalogCases(config: BrowserRunConfig, url: string, headers: Record<string, string>): BrowserCase[] {
  return OPENAI_RESPONSES_SERVED_MODEL_IDS.map((model) => ({
    id: modelCatalogCaseId('responses_model_', model),
    description: `OpenAI Responses served model smoke: ${model}`,
    covers: ['model'],
    precondition: buildOpenAIModelCatalogPrecondition(config, 'responses'),
    run: async () => {
      const result = await tracedFetch({
        url,
        method: 'POST',
        headers,
        timeoutMs: config.timeoutMs,
        body: {
          model,
          input: 'Reply with exactly: ok',
          max_output_tokens: 64,
          ...(isLongRunningResponsesModel(model) ? { background: true } : {}),
        },
      })
      return { detail: `model=${model}, ${summarizeOpenAIResponses(result.text)}`, exchanges: [result.exchange] }
    },
  }))
}

function buildGeminiModelCatalogCases(config: BrowserRunConfig, headers: Record<string, string>): BrowserCase[] {
  return GEMINI_SERVED_GENERATE_CONTENT_MODELS.map((model) => ({
    id: modelCatalogCaseId('model_', model.id),
    description: `Gemini served generateContent model smoke (${model.kind}): ${model.id}`,
    covers: ['model'],
    run: async () => {
      const result = await tracedFetch({
        url: buildGeminiEndpoint(config, model.id),
        method: 'POST',
        headers,
        timeoutMs: config.timeoutMs,
        body: buildGeminiModelCatalogBody(model),
      })
      return { detail: `model=${model.id}, kind=${model.kind}, ${summarizeGemini(result.text)}`, exchanges: [result.exchange] }
    },
  }))
}

function summarizeAnthropic(text: string): string {
  const data = parseJson(text) as {
    stop_reason?: string
    content?: Array<{ type?: string; text?: string }>
  }
  const output = (data.content ?? [])
    .filter((item) => item.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text)
    .join(' ')
  return `stop_reason=${data.stop_reason ?? 'unknown'}, text="${truncate(output)}"`
}

function summarizeGemini(text: string): string {
  const data = parseJson(text) as {
    candidates?: Array<{
      content?: {
        parts?: Array<{
          text?: string
          inlineData?: unknown
          fileData?: unknown
        }>
      }
    }>
  }
  const parts = (data.candidates ?? []).flatMap((candidate) => candidate.content?.parts ?? [])
  const output = parts
    .map((part) => part.text ?? '')
    .join(' ')
  const mediaParts = parts.filter((part) => part.inlineData !== undefined || part.fileData !== undefined).length
  return `candidates=${data.candidates?.length ?? 0}, media_parts=${mediaParts}, text="${truncate(output)}"`
}

function buildOpenAIChatCases(config: BrowserRunConfig): BrowserCase[] {
  const url = appendEndpoint(config.apiBaseUrl, defaultBaseUrl(config.apiType), '/chat/completions')
  const headers = buildOpenAIHeaders(config)
  const cases: BrowserCase[] = [
    {
      id: 'basic',
      description: 'Basic chat completion request from browser fetch',
      covers: ['messages', 'model'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            messages: [{ role: 'user', content: 'Reply with exactly: pong' }],
          },
        })
        return { detail: summarizeOpenAIChat(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'sampling_and_max_completion',
      description: 'Chat completion request with temperature',
      covers: ['messages', 'model', 'temperature'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            temperature: 0,
            messages: [{ role: 'user', content: 'Return the word stable.' }],
          },
        })
        return { detail: summarizeOpenAIChat(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'response_format_json_object',
      description: 'Chat completion request with JSON response format',
      covers: ['messages', 'model', 'response_format'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            response_format: { type: 'json_object' },
            messages: [{ role: 'user', content: 'Return a JSON object with one key named ok.' }],
          },
        })
        return { detail: summarizeOpenAIChat(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'stream_and_stream_options',
      description: 'Chat completion streaming request',
      covers: ['messages', 'model', 'stream'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers: { ...headers, Accept: 'text/event-stream' },
          timeoutMs: config.timeoutMs,
          stream: true,
          body: {
            model: config.model,
            stream: true,
            messages: [{ role: 'user', content: 'Count 1 to 3.' }],
          },
        })
        return { detail: `status=${result.status} ${result.statusText}, chunks=${result.chunks ?? 0}`, exchanges: [result.exchange] }
      },
    },
  ]
  return config.targetCases?.trim()
    ? [...cases, ...buildOpenAIChatModelCatalogCases(config, url, headers)]
    : cases
}

function buildOpenAIResponsesCases(config: BrowserRunConfig): BrowserCase[] {
  const url = appendEndpoint(config.apiBaseUrl, defaultBaseUrl(config.apiType), '/responses')
  const headers = buildOpenAIHeaders(config)
  const cases: BrowserCase[] = [
    {
      id: 'responses_basic',
      description: 'Basic Responses API request from browser fetch',
      covers: ['input', 'model'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            input: 'Reply with exactly: pong',
          },
        })
        return { detail: summarizeOpenAIResponses(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'responses_instructions',
      description: 'Responses API request with instructions',
      covers: ['input', 'model', 'instructions'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            instructions: 'Answer as a terse compatibility test.',
            input: 'Say ok.',
          },
        })
        return { detail: summarizeOpenAIResponses(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'responses_stream_and_options',
      description: 'Responses API streaming request',
      covers: ['input', 'model', 'stream'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers: { ...headers, Accept: 'text/event-stream' },
          timeoutMs: config.timeoutMs,
          stream: true,
          body: {
            model: config.model,
            stream: true,
            input: 'Count 1 to 3.',
          },
        })
        return { detail: `status=${result.status} ${result.statusText}, chunks=${result.chunks ?? 0}`, exchanges: [result.exchange] }
      },
    },
  ]
  return config.targetCases?.trim()
    ? [...cases, ...buildOpenAIResponsesModelCatalogCases(config, url, headers)]
    : cases
}

function buildAnthropicCases(config: BrowserRunConfig): BrowserCase[] {
  const url = appendEndpoint(config.apiBaseUrl, defaultBaseUrl(config.apiType), '/messages')
  const headers = buildAnthropicHeaders(config)
  return [
    {
      id: 'basic',
      description: 'Basic Anthropic Messages request from browser fetch',
      covers: ['messages', 'model', 'max_tokens'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            max_tokens: 64,
            messages: [{ role: 'user', content: 'Reply with exactly: pong' }],
          },
        })
        return { detail: summarizeAnthropic(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'system_message',
      description: 'Anthropic Messages request with system prompt',
      covers: ['messages', 'model', 'max_tokens', 'system'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            max_tokens: 64,
            system: 'Answer with short lowercase text.',
            messages: [{ role: 'user', content: 'Say ok.' }],
          },
        })
        return { detail: summarizeAnthropic(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'temperature',
      description: 'Anthropic Messages request with temperature',
      covers: ['messages', 'model', 'max_tokens', 'temperature'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            model: config.model,
            max_tokens: 64,
            temperature: 0,
            messages: [{ role: 'user', content: 'Return the word stable.' }],
          },
        })
        return { detail: summarizeAnthropic(result.text), exchanges: [result.exchange] }
      },
    },
  ]
}

function buildGeminiCases(config: BrowserRunConfig): BrowserCase[] {
  const url = buildGeminiEndpoint(config)
  const headers = buildJsonHeaders(config)
  const cases: BrowserCase[] = [
    {
      id: 'basic',
      description: 'Basic Gemini generateContent request from browser fetch',
      covers: ['contents', 'model'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            contents: [{ role: 'user', parts: [{ text: 'Reply with exactly: pong' }] }],
          },
        })
        return { detail: summarizeGemini(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'system_instruction',
      description: 'Gemini generateContent request with systemInstruction',
      covers: ['contents', 'model', 'systemInstruction'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            systemInstruction: { parts: [{ text: 'Answer with short lowercase text.' }] },
            contents: [{ role: 'user', parts: [{ text: 'Say ok.' }] }],
          },
        })
        return { detail: summarizeGemini(result.text), exchanges: [result.exchange] }
      },
    },
    {
      id: 'generation_config',
      description: 'Gemini generateContent request with generationConfig',
      covers: ['contents', 'model', 'generationConfig'],
      run: async () => {
        const result = await tracedFetch({
          url,
          method: 'POST',
          headers,
          timeoutMs: config.timeoutMs,
          body: {
            generationConfig: { temperature: 0 },
            contents: [{ role: 'user', parts: [{ text: 'Return the word stable.' }] }],
          },
        })
        return { detail: summarizeGemini(result.text), exchanges: [result.exchange] }
      },
    },
  ]

  return config.targetCases?.trim()
    ? [...cases, ...buildGeminiModelCatalogCases(config, headers)]
    : cases
}

function buildCases(config: BrowserRunConfig): BrowserCase[] {
  if (config.apiType === 'openai.chat') {
    return buildOpenAIChatCases(config)
  }
  if (config.apiType === 'openai.responses') {
    return buildOpenAIResponsesCases(config)
  }
  if (config.apiType === 'anthropic.messages') {
    return buildAnthropicCases(config)
  }
  return buildGeminiCases(config)
}

function wildcardToRegExp(pattern: string): RegExp {
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`^${escaped.replace(/\\\*/g, '.*').replace(/\\\?/g, '.')}$`)
}

function filterCases(cases: BrowserCase[], config: BrowserRunConfig): BrowserCase[] {
  const rawFilter = config.targetCases?.trim()
  if (!rawFilter) {
    return cases
  }

  const aliases = aliasesForApiType(config.apiType)
  const selectors = rawFilter.split(',').map((item) => item.trim()).filter(Boolean)
  return cases.filter((testCase) => selectors.some((selector) => {
    const separatorIndex = selector.indexOf(':')
    if (separatorIndex > 0) {
      const providerSelector = selector.slice(0, separatorIndex).trim().toLowerCase()
      if (!aliases.includes(providerSelector)) {
        return false
      }
      return wildcardToRegExp(selector.slice(separatorIndex + 1).trim() || '*').test(testCase.id)
    }
    return wildcardToRegExp(selector).test(testCase.id)
  }))
}

function buildTrace(testId: string, exchanges: HttpTraceExchange[]): TestCaseHttpTrace {
  return {
    source: 'browser-fetch',
    testId,
    exchangeCount: exchanges.length,
    exchanges,
  }
}

async function runCase(provider: string, testCase: BrowserCase): Promise<TestCaseResult> {
  const started = performance.now()
  const skipReason = testCase.precondition?.()
  if (skipReason) {
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'skipped',
      durationMs: Math.round(performance.now() - started),
      coveredParams: [...testCase.covers],
      detail: skipReason,
    }
  }

  const testId = `${provider.replace(/[^a-z0-9]+/gi, '_')}-${testCase.id}-${Date.now()}`
  try {
    const result = await testCase.run(testId)
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'passed',
      durationMs: Math.round(performance.now() - started),
      coveredParams: [...testCase.covers],
      detail: result.detail,
      httpTrace: buildTrace(testId, result.exchanges),
    }
  } catch (error) {
    const exchanges = error instanceof BrowserCaseError ? error.exchanges : []
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'failed',
      durationMs: Math.round(performance.now() - started),
      coveredParams: [...testCase.covers],
      error: getErrorMessage(error),
      httpTrace: buildTrace(testId, exchanges),
    }
  }
}

function skippedFilterSummary(
  provider: string,
  model: string,
  apiBaseUrl: string | undefined,
  allParams: string[],
  targetCases: string,
): ProviderSummary {
  const now = new Date().toISOString()
  return {
    provider,
    model,
    apiBaseUrl,
    startedAt: now,
    finishedAt: now,
    passed: 0,
    failed: 0,
    skipped: 1,
    caseResults: [{
      id: 'case_filter',
      description: 'Case selection filter',
      status: 'skipped',
      durationMs: 0,
      coveredParams: [],
      detail: `no cases matched TARGET_CASES=${targetCases}`,
    }],
    allParams,
    coveredParams: [],
    untestedParams: allParams,
  }
}

export async function runBrowserStandardCases(config: BrowserRunConfig): Promise<RunSummary> {
  if (!config.apiKey) {
    throw new Error('API key is required for browser direct mode')
  }

  const startedAt = new Date().toISOString()
  const provider = providerNameForApiType(config.apiType)
  const allParams = PARAMS[config.apiType]
  const cases = filterCases(buildCases(config), config)
  const apiBaseUrl = config.apiBaseUrl ?? defaultBaseUrl(config.apiType)
  const progressTotal = Math.max(cases.length, 1)

  config.onProgress?.({
    phase: 'provider-start',
    provider,
    completed: 0,
    total: progressTotal,
  })

  let providerSummary: ProviderSummary
  if (cases.length === 0 && config.targetCases?.trim()) {
    config.onProgress?.({
      phase: 'case-complete',
      provider,
      caseId: 'case_filter',
      description: 'Case selection filter',
      status: 'skipped',
      completed: 1,
      total: progressTotal,
    })
    providerSummary = skippedFilterSummary(provider, config.model, apiBaseUrl, allParams, config.targetCases.trim())
  } else {
    const caseResults: TestCaseResult[] = []
    let completedCases = 0
    for (const testCase of cases) {
      config.onProgress?.({
        phase: 'case-start',
        provider,
        caseId: testCase.id,
        description: testCase.description,
        completed: completedCases,
        total: progressTotal,
      })
      const result = await runCase(provider, testCase)
      caseResults.push(result)
      completedCases += 1
      config.onProgress?.({
        phase: 'case-complete',
        provider,
        caseId: result.id,
        description: result.description,
        status: result.status,
        completed: completedCases,
        total: progressTotal,
      })
    }

    const coveredSet = new Set<string>()
    for (const result of caseResults) {
      if (result.status !== 'passed') {
        continue
      }
      for (const coveredParam of result.coveredParams) {
        coveredSet.add(coveredParam)
      }
    }

    const coveredParams = Array.from(coveredSet).sort()
    providerSummary = {
      provider,
      model: config.model,
      apiBaseUrl,
      startedAt,
      finishedAt: new Date().toISOString(),
      passed: caseResults.filter((item) => item.status === 'passed').length,
      failed: caseResults.filter((item) => item.status === 'failed').length,
      skipped: caseResults.filter((item) => item.status === 'skipped').length,
      caseResults,
      allParams,
      coveredParams,
      untestedParams: allParams.filter((param) => !coveredSet.has(param)),
    }
  }

  config.onProgress?.({
    phase: 'provider-complete',
    provider,
    completed: progressTotal,
    total: progressTotal,
  })

  return {
    startedAt,
    finishedAt: new Date().toISOString(),
    providers: [providerSummary],
    totalPassed: providerSummary.passed,
    totalFailed: providerSummary.failed,
    totalSkipped: providerSummary.skipped,
  }
}
