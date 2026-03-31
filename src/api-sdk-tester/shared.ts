import { appendFileSync, writeFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';

import type { ProviderSummary, TestCaseResult } from '../types';

export interface TestCase {
  id: string;
  description: string;
  covers: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
  apiType?: 'chatCompletions' | 'responses';
}

let currentProvider = 'unknown';
const originalFetch = globalThis.fetch;
const STREAM_CONTENT_TYPE_HINTS = ['text/event-stream', 'application/x-ndjson'];
const REQUEST_LOG_FILE = resolvePath(process.cwd(), 'requests.log');

export function initializeRequestLogFile(): void {
  try {
    writeFileSync(REQUEST_LOG_FILE, '', 'utf8');
  } catch {
    // Ignore file initialization errors to avoid affecting test execution.
  }
}

export function appendRequestLog(lines: readonly string[]): void {
  const content = `${lines.join('\n')}\n`;
  try {
    appendFileSync(REQUEST_LOG_FILE, content, 'utf8');
  } catch {
    // Ignore file logging errors to avoid affecting test execution.
  }
}

export function logRequest(lines: readonly string[]): void {
  for (const line of lines) {
    console.log(line);
  }
  appendRequestLog(lines);
}

/**
 * 设置当前provider名称,用于日志记录
 */
export function setCurrentProvider(provider: string): void {
  currentProvider = provider;
}

/**
 * 将 HeadersInit 归一化为可遍历对象
 */
function normalizeHeaders(headers: RequestInit['headers'] | undefined): Record<string, string> | undefined {
  if (!headers) {
    return undefined;
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }

  return Object.fromEntries(Object.entries(headers).map(([key, value]) => [key, String(value)]));
}

function sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
  const sanitizedHeaders: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    const lowerKey = key.toLowerCase();
    if (lowerKey.includes('authorization') || lowerKey.includes('api-key')) {
      sanitizedHeaders[key] = '***REDACTED***';
      continue;
    }
    sanitizedHeaders[key] = value;
  }
  return sanitizedHeaders;
}

function truncateLogBody(text: string): string {
  return text;
}

function serializeBodyForLog(body: RequestInit['body']): string | undefined {
  if (!body) {
    return undefined;
  }

  if (typeof body === 'string') {
    return body;
  }

  if (body instanceof URLSearchParams) {
    return body.toString();
  }

  if (body instanceof ArrayBuffer) {
    return `[ArrayBuffer byteLength=${body.byteLength}]`;
  }

  if (ArrayBuffer.isView(body)) {
    return `[${body.constructor.name} byteLength=${body.byteLength}]`;
  }

  if (typeof Blob !== 'undefined' && body instanceof Blob) {
    return `[Blob size=${body.size} type=${body.type || 'unknown'}]`;
  }

  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return '[FormData]';
  }

  if (typeof ReadableStream !== 'undefined' && body instanceof ReadableStream) {
    return '[ReadableStream]';
  }

  try {
    return JSON.stringify(body, null, 2);
  } catch {
    return undefined;
  }
}

function looksLikeStreamingRequest(
  url: string,
  headers: Record<string, string> | undefined,
  bodyPreview: string | undefined,
): boolean {
  if (/\balt=sse\b/i.test(url)) {
    return true;
  }

  const acceptEntry = Object.entries(headers ?? {}).find(([key]) => key.toLowerCase() === 'accept');
  if (acceptEntry && acceptEntry[1].toLowerCase().includes('text/event-stream')) {
    return true;
  }

  return Boolean(bodyPreview && /"stream"\s*:\s*true/i.test(bodyPreview));
}

function isStreamingResponse(response: Response, streamRequested: boolean): boolean {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
  if (STREAM_CONTENT_TYPE_HINTS.some((hint) => contentType.includes(hint))) {
    return true;
  }
  return streamRequested && response.body !== null;
}

async function logResponseBody(response: Response): Promise<void> {
  const clonedResponse = response.clone();

  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const bodyText = await clonedResponse.text();
      try {
        const bodyJson = JSON.parse(bodyText);
        const bodyPreview = JSON.stringify(bodyJson, null, 2);
        console.log(`  Body: ${truncateLogBody(bodyPreview).replace(/\n/g, '\n  ')}`);
      } catch {
        console.log(`  Body: ${truncateLogBody(bodyText).replace(/\n/g, '\n  ')}`);
      }
      return;
    }

    if (contentType.includes('text/')) {
      const bodyText = await clonedResponse.text();
      console.log(`  Body: ${truncateLogBody(bodyText).replace(/\n/g, '\n  ')}`);
      return;
    }

    console.log(`  Body: [${contentType || 'unknown content type'}]`);
  } catch (error) {
    console.log(`  Body: [Unable to read: ${error}]`);
  }
}

function logStreamingResponseBody(response: Response): void {
  void logResponseBody(response).catch((error) => {
    console.log(`  Body: [Unable to read streaming response: ${error}]`);
  });
}

function createInstrumentedFetch(resolveProvider: () => string): typeof fetch {
  return async function loggingFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
    const provider = resolveProvider();
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? (input instanceof Request ? input.method : 'GET');
    const requestHeaders = normalizeHeaders(init?.headers);
    const requestBody = serializeBodyForLog(init?.body);
    const streamRequested = looksLikeStreamingRequest(url, requestHeaders, requestBody);

    // 记录请求信息
    const requestLines: string[] = [];
    requestLines.push('');
    requestLines.push(`[${provider}] 📤 HTTP REQUEST`);
    requestLines.push(`  URL: ${url}`);
    requestLines.push(`  Method: ${method}`);

    if (requestHeaders) {
      requestLines.push(
        `  Headers: ${JSON.stringify(sanitizeHeaders(requestHeaders), null, 2).replace(/\n/g, '\n  ')}`,
      );
    }

    if (requestBody) {
      requestLines.push(`  Body: ${truncateLogBody(requestBody).replace(/\n/g, '\n  ')}`);
    } else if (init?.body) {
      requestLines.push('  Body: [Unable to serialize]');
    }
    logRequest(requestLines);

    const startTime = Date.now();

    try {
      // 使用原始fetch执行实际的请求
      const response = await originalFetch(input, init);
      const duration = Date.now() - startTime;

      // 记录响应信息
      console.log(`\n[${provider}] 📥 HTTP RESPONSE`);
      console.log(`  URL: ${url}`);
      console.log(`  Status: ${response.status} ${response.statusText}`);
      console.log(`  Duration: ${duration}ms`);

      // 记录响应头
      const responseHeaders: Record<string, string> = {};
      response.headers.forEach((value, key) => {
        responseHeaders[key] = value;
      });
      console.log(
        `  Headers: ${JSON.stringify(responseHeaders, null, 2).replace(/\n/g, '\n  ')}`,
      );

      if (isStreamingResponse(response, streamRequested)) {
        logStreamingResponseBody(response);
        return response;
      }

      await logResponseBody(response);
      return response;
    } catch (error) {
      const duration = Date.now() - startTime;
      console.error(`\n[${provider}] ❌ HTTP ERROR`);
      console.error(`  URL: ${url}`);
      console.error(`  Duration: ${duration}ms`);
      console.error(`  Error: ${error}`);
      throw error;
    }
  };
}

/**
 * 创建一个带有日志记录功能的自定义 fetch 函数
 * 记录 HTTP 请求和响应的详细信息
 */
export function createLoggingFetch(provider: string): typeof fetch {
  return createInstrumentedFetch(() => provider);
}

/**
 * 安装全局的fetch拦截器,用于记录所有HTTP请求
 */
export function installGlobalFetchInterceptor(): void {
  globalThis.fetch = createInstrumentedFetch(() => currentProvider);
}

export function truncate(text: string, maxLength = 120): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 3)}...`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatError(error: unknown): string {
  if (error instanceof Error) {
    const anyError = error as {
      status?: unknown;
      code?: unknown;
      type?: unknown;
      error?: { message?: unknown; type?: unknown };
    };
    const details: string[] = [];
    if (typeof anyError.status === 'number') {
      details.push(`status=${String(anyError.status)}`);
    }
    if (typeof anyError.code === 'string') {
      details.push(`code=${anyError.code}`);
    }
    if (typeof anyError.type === 'string') {
      details.push(`type=${anyError.type}`);
    }
    if (anyError.error && typeof anyError.error.message === 'string') {
      details.push(`api_error=${anyError.error.message}`);
    }
    const suffix = details.length > 0 ? ` (${details.join(', ')})` : '';
    return `${error.message}${suffix}`;
  }

  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

export function summarizeOpenAIResponse(response: unknown): string {
  const obj = response as {
    choices?: Array<{
      finish_reason?: string;
      message?: {
        content?: unknown;
        tool_calls?: unknown[];
      };
    }>;
  };

  const choice = obj.choices?.[0];
  const finishReason = choice?.finish_reason ?? 'unknown';
  const toolCalls = Array.isArray(choice?.message?.tool_calls) ? choice.message.tool_calls.length : 0;

  let content = '';
  const rawContent = choice?.message?.content;
  if (typeof rawContent === 'string') {
    content = rawContent;
  } else if (Array.isArray(rawContent)) {
    content = JSON.stringify(rawContent);
  }

  return `finish=${finishReason}, tool_calls=${toolCalls}, text="${truncate(content)}"`;
}

export function summarizeOpenAIResponses(response: unknown): string {
  const obj = response as {
    id?: string;
    status?: string | null;
    output_text?: unknown;
    output?: unknown[];
  };

  const status = obj.status ?? 'unknown';
  const outputCount = Array.isArray(obj.output) ? obj.output.length : 0;
  const text = typeof obj.output_text === 'string' ? obj.output_text : '';
  return `status=${status}, output_items=${outputCount}, text="${truncate(text)}"`;
}

export function summarizeAnthropicResponse(response: unknown): string {
  const obj = response as {
    stop_reason?: string | null;
    content?: Array<{ type?: string; text?: string }>;
    usage?: {
      speed?: string;
      input_tokens?: number;
      output_tokens?: number;
    };
  };

  const stopReason = obj.stop_reason ?? 'unknown';
  const text = (obj.content ?? [])
    .filter((item) => item.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text as string)
    .join(' ');
  const toolUseCount = (obj.content ?? []).filter((item) => item.type === 'tool_use').length;

  const parts: string[] = [`stop_reason=${stopReason}`, `tool_use=${toolUseCount}`];

  // 添加 usage 信息
  if (obj.usage) {
    if (obj.usage.speed) {
      parts.push(`speed=${obj.usage.speed}`);
    }
    if (typeof obj.usage.input_tokens === 'number' && typeof obj.usage.output_tokens === 'number') {
      parts.push(`tokens=${obj.usage.input_tokens}+${obj.usage.output_tokens}`);
    }
  }

  parts.push(`text="${truncate(text)}"`);
  return parts.join(', ');
}

export function summarizeGeminiResponse(response: unknown): string {
  const obj = response as {
    text?: string;
    functionCalls?: unknown[];
    candidates?: unknown[];
  };
  const text = typeof obj.text === 'string' ? obj.text : '';
  const functionCalls = Array.isArray(obj.functionCalls) ? obj.functionCalls.length : 0;
  const candidates = Array.isArray(obj.candidates) ? obj.candidates.length : 0;
  return `candidates=${candidates}, function_calls=${functionCalls}, text="${truncate(text)}"`;
}

async function runCase(testCase: TestCase): Promise<TestCaseResult> {
  const started = Date.now();
  const skipReason = testCase.precondition?.();
  if (skipReason) {
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'skipped',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      detail: skipReason,
      apiType: testCase.apiType,
    };
  }

  try {
    const detail = await testCase.run();
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'passed',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      detail,
      apiType: testCase.apiType,
    };
  } catch (error) {
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'failed',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      error: formatError(error),
      apiType: testCase.apiType,
    };
  }
}

export function createSetupSkippedSummary(
  provider: string,
  model: string,
  apiBaseUrl: string | undefined,
  allParams: readonly string[],
  reason: string,
): ProviderSummary {
  const now = new Date().toISOString();
  return {
    provider,
    model,
    apiBaseUrl,
    startedAt: now,
    finishedAt: now,
    passed: 0,
    failed: 0,
    skipped: 1,
    caseResults: [
      {
        id: 'provider_setup',
        description: 'Provider setup validation',
        status: 'skipped',
        durationMs: 0,
        coveredParams: [],
        detail: reason,
      },
    ],
    allParams: [...allParams],
    coveredParams: [],
    untestedParams: [...allParams],
  };
}

interface CaseFilterEnv {
  key: string;
  value: string;
}

interface CaseSelector {
  provider?: string;
  caseIdPattern: RegExp;
}

function resolveCaseFilterEnv(): CaseFilterEnv | undefined {
  const keys = ['TARGET_CASES', 'TEST_CASES', 'CASE_IDS'];
  for (const key of keys) {
    const value = process.env[key]?.trim();
    if (value) {
      return { key, value };
    }
  }
  return undefined;
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normalizeProviderSelector(raw: string): string {
  const normalized = raw.trim().toLowerCase();
  if (normalized === 'claude') {
    return 'anthropic';
  }
  if (normalized === 'claudeagent') {
    return 'claude-agent';
  }
  return normalized;
}

function buildCaseIdPattern(raw: string): RegExp {
  const source = raw.trim() || '*';
  const regexSource = escapeRegExp(source).replace(/\\\*/g, '.*').replace(/\\\?/g, '.');
  return new RegExp(`^${regexSource}$`);
}

function parseCaseSelectors(raw: string): CaseSelector[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const separatorIndex = item.indexOf(':');
      if (separatorIndex <= 0) {
        return {
          caseIdPattern: buildCaseIdPattern(item),
        };
      }

      const providerPart = normalizeProviderSelector(item.slice(0, separatorIndex));
      const casePart = item.slice(separatorIndex + 1).trim();
      return {
        provider: providerPart,
        caseIdPattern: buildCaseIdPattern(casePart),
      };
    });
}

function matchesProviderSelector(provider: string, selectorProvider: string): boolean {
  const normalizedProvider = provider.trim().toLowerCase();
  if (normalizedProvider === selectorProvider) {
    return true;
  }
  return normalizedProvider.startsWith(`${selectorProvider}(`);
}

function applyCaseFilter(
  provider: string,
  cases: readonly TestCase[],
): {
  filteredCases: readonly TestCase[];
  filterEnv?: CaseFilterEnv;
} {
  const filterEnv = resolveCaseFilterEnv();
  if (!filterEnv) {
    return { filteredCases: cases };
  }

  const selectors = parseCaseSelectors(filterEnv.value);
  if (selectors.length === 0) {
    return { filteredCases: cases, filterEnv };
  }

  const filteredCases = cases.filter((testCase) =>
    selectors.some((selector) => {
      if (selector.provider && !matchesProviderSelector(provider, selector.provider)) {
        return false;
      }
      return selector.caseIdPattern.test(testCase.id);
    }),
  );

  return {
    filteredCases,
    filterEnv,
  };
}

function logCaseResult(provider: string, result: TestCaseResult): void {
  const marker =
    result.status === 'passed' ? 'PASS' : result.status === 'failed' ? 'FAIL' : 'SKIP';
  const messageParts: string[] = [
    `[${provider}] ${marker} ${result.id} (${formatDuration(result.durationMs)})`,
  ];
  if (result.detail) {
    messageParts.push(`detail=${truncate(result.detail, 180)}`);
  }
  if (result.error) {
    messageParts.push(`error=${truncate(result.error, 220)}`);
  }
  console.log(messageParts.join(' | '));
}

export async function executeProviderCases(
  provider: string,
  model: string,
  apiBaseUrl: string | undefined,
  allParams: readonly string[],
  cases: readonly TestCase[],
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  const startedAt = new Date().toISOString();
  const caseResults: TestCaseResult[] = [];
  const { filteredCases, filterEnv } = applyCaseFilter(provider, cases);

  if (filterEnv) {
    console.log(
      `[${provider}] case filter enabled: ${filterEnv.key}=${filterEnv.value} (${filteredCases.length}/${cases.length} selected)`,
    );
  }

  if (filteredCases.length === 0) {
    const detail = filterEnv
      ? `no cases matched ${filterEnv.key}=${filterEnv.value}`
      : 'no cases selected';

    return {
      provider,
      model,
      apiBaseUrl,
      startedAt,
      finishedAt: new Date().toISOString(),
      passed: 0,
      failed: 0,
      skipped: 1,
      caseResults: [
        {
          id: 'case_filter',
          description: 'Case selection filter',
          status: 'skipped',
          durationMs: 0,
          coveredParams: [],
          detail,
        },
      ],
      allParams: [...allParams],
      coveredParams: [],
      untestedParams: [...allParams],
    };
  }

  if (concurrency <= 1) {
    // Sequential execution (backward compatible)
    for (const testCase of filteredCases) {
      console.log(`[${provider}] running ${testCase.id} - ${testCase.description}`);
      const result = await runCase(testCase);
      caseResults.push(result);

      logCaseResult(provider, result);

      if (failFast && result.status === 'failed') {
        console.log(`[${provider}] fail-fast enabled, stop remaining cases.`);
        break;
      }
    }
  } else {
    // Concurrent execution with worker pool
    let stopped = false;
    let nextIndex = 0;

    const worker = async (): Promise<void> => {
      while (nextIndex < filteredCases.length && !stopped) {
        const index = nextIndex++;
        if (index >= filteredCases.length) {
          break;
        }

        const testCase = filteredCases[index]!;
        if (stopped) {
          caseResults[index] = {
            id: testCase.id,
            description: testCase.description,
            status: 'skipped',
            durationMs: 0,
            coveredParams: [...testCase.covers],
            detail: 'skipped due to fail-fast',
          };
          continue;
        }

        console.log(`[${provider}] running ${testCase.id} - ${testCase.description}`);
        const result = await runCase(testCase);
        caseResults[index] = result;

        logCaseResult(provider, result);

        if (failFast && result.status === 'failed') {
          stopped = true;
          console.log(`[${provider}] fail-fast enabled, stop remaining cases.`);
        }
      }
    };

    // Initialize results array with placeholders
    const placeholders = filteredCases.map(() => null);
    caseResults.push(...(placeholders as unknown as TestCaseResult[]));

    const workerCount = Math.min(concurrency, filteredCases.length);
    await Promise.all(Array.from({ length: workerCount }, () => worker()));

    // Remove any null placeholders that weren't filled
    for (let i = caseResults.length - 1; i >= 0; i--) {
      if (caseResults[i] === null) {
        caseResults.splice(i, 1);
      }
    }
  }

  const passed = caseResults.filter((item) => item.status === 'passed').length;
  const failed = caseResults.filter((item) => item.status === 'failed').length;
  const skipped = caseResults.filter((item) => item.status === 'skipped').length;

  const coveredParamSet = new Set<string>();
  for (const result of caseResults) {
    if (result.status !== 'passed') {
      continue;
    }
    for (const covered of result.coveredParams) {
      coveredParamSet.add(covered);
    }
  }

  const coveredParams = Array.from(coveredParamSet).sort();
  const untestedParams = allParams.filter((param) => !coveredParamSet.has(param));

  return {
    provider,
    model,
    apiBaseUrl,
    startedAt,
    finishedAt: new Date().toISOString(),
    passed,
    failed,
    skipped,
    caseResults,
    allParams: [...allParams],
    coveredParams,
    untestedParams,
  };
}
