import { appendFileSync, writeFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';

import type { HttpTraceExchange, TestCaseHttpTrace } from '../../types';
import type { PluginRequestParams } from '../../types';
import { runTestPluginBeforeCase } from '../plugins';
import { isUsageCaptureEnabled, recordUsageCapture } from '../../billing-audit/usage-capture';
import type { AnthropicUsage, GeminiUsage, OpenAIUsage } from '../../billing-audit/type';
import { getCurrentProvider } from './provider-context';
import { getActiveTestContext } from './test-context';

const originalFetch = globalThis.fetch;
const STREAM_CONTENT_TYPE_HINTS = ['text/event-stream', 'application/x-ndjson'];
const REQUEST_LOG_FILE = resolvePath(process.cwd(), 'requests.log');
const HTTP_TRACE_SOURCE = 'fetch-interceptor';

interface CapturedHttpTraceState {
  trace: TestCaseHttpTrace;
  exchangesByRequestId: Map<string, HttpTraceExchange>;
  pending: Set<Promise<void>>;
}

const capturedHttpTraceByTestId = new Map<string, CapturedHttpTraceState>();
let httpTraceRequestCounter = 0;

function appendLog(lines: readonly string[]): void {
  const content = `${lines.join('\n')}\n`;
  try {
    appendFileSync(REQUEST_LOG_FILE, content, 'utf8');
  } catch {
    // Ignore file logging errors to avoid affecting test execution.
  }
}

function logLines(lines: readonly string[], useErrorStream = false): void {
  for (const line of lines) {
    if (useErrorStream) {
      console.error(line);
      continue;
    }
    console.log(line);
  }
  appendLog(lines);
}

function logRequest(lines: readonly string[]): void {
  logLines(lines);
}

function logResponse(lines: readonly string[]): void {
  logLines(lines);
}

function logError(lines: readonly string[]): void {
  logLines(lines, true);
}

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

function formatUnknownError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function collectResponseHeaders(headers: Headers): Record<string, string> {
  const responseHeaders: Record<string, string> = {};
  headers.forEach((value, key) => {
    responseHeaders[key] = value;
  });
  return responseHeaders;
}

function headersEqual(
  left: Record<string, string> | undefined,
  right: Record<string, string> | undefined,
): boolean {
  const leftEntries = Object.entries(left ?? {});
  const rightEntries = Object.entries(right ?? {});
  if (leftEntries.length !== rightEntries.length) {
    return false;
  }

  for (const [key, value] of leftEntries) {
    if (right?.[key] !== value) {
      return false;
    }
  }
  return true;
}

function createFetchInit(
  init: RequestInit | undefined,
  request: PluginRequestParams,
  originalRequest: PluginRequestParams,
): RequestInit | undefined {
  const urlChanged = request.url !== originalRequest.url;
  const methodChanged = request.method !== originalRequest.method;
  const headersChanged = !headersEqual(request.headers, originalRequest.headers);
  const bodyChanged = request.body !== originalRequest.body;

  if (!urlChanged && !methodChanged && !headersChanged && !bodyChanged) {
    return init;
  }

  const nextInit: RequestInit = { ...(init ?? {}) };
  nextInit.method = request.method;
  nextInit.headers = request.headers;

  if (bodyChanged) {
    if (request.body === undefined) {
      delete nextInit.body;
    } else {
      nextInit.body = request.body;
    }
  }

  return nextInit;
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

async function readResponseBody(response: Response): Promise<string | undefined> {
  const clonedResponse = response.clone();

  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const bodyText = await clonedResponse.text();
      try {
        return JSON.stringify(JSON.parse(bodyText), null, 2);
      } catch {
        return bodyText;
      }
    }

    if (
      contentType.includes('text/')
      || STREAM_CONTENT_TYPE_HINTS.some((hint) => contentType.toLowerCase().includes(hint))
    ) {
      const bodyText = await clonedResponse.text();
      return bodyText;
    }

    if (!contentType) {
      const bodyText = await clonedResponse.text();
      return bodyText || undefined;
    }

    return `[${contentType}]`;
  } catch (error) {
    return `[Unable to read: ${formatUnknownError(error)}]`;
  }
}

function formatBodyLine(body: string | undefined): string {
  if (!body) {
    return '[empty]';
  }
  return truncateLogBody(body).replace(/\n/g, '\n  ');
}

function parseJsonObject(text: string | undefined): Record<string, unknown> | undefined {
  if (!text) {
    return undefined;
  }
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function parseRequestModel(requestBody: string | undefined): string | undefined {
  const parsed = parseJsonObject(requestBody);
  const model = parsed?.model;
  return typeof model === 'string' && model ? model : undefined;
}

function captureUsageFromJsonResponse(
  providerLabel: string,
  requestBody: string | undefined,
  responseBody: string | undefined,
): void {
  if (!isUsageCaptureEnabled()) {
    return;
  }

  const parsed = parseJsonObject(responseBody);
  if (!parsed) {
    return;
  }

  if (providerLabel === 'gemini' && parsed.usageMetadata && typeof parsed.usageMetadata === 'object') {
    const model = typeof parsed.modelVersion === 'string' ? parsed.modelVersion : parseRequestModel(requestBody);
    if (model) {
      recordUsageCapture({
        provider: 'gemini',
        model,
        usage: parsed.usageMetadata as GeminiUsage,
      });
    }
    return;
  }

  // openai family — label may be bare 'openai' or 'openai(chatCompletions)' etc.
  if ((providerLabel === 'openai' || providerLabel.startsWith('openai(')) && parsed.usage && typeof parsed.usage === 'object') {
    const model = typeof parsed.model === 'string' ? parsed.model : parseRequestModel(requestBody);
    if (model) {
      recordUsageCapture({
        provider: 'openai',
        model,
        usage: parsed.usage as OpenAIUsage,
      });
    }
    return;
  }

  if (providerLabel === 'anthropic' && parsed.usage && typeof parsed.usage === 'object') {
    const model = typeof parsed.model === 'string' ? parsed.model : parseRequestModel(requestBody);
    if (model) {
      recordUsageCapture({
        provider: 'anthropic',
        model,
        usage: parsed.usage as AnthropicUsage,
      });
    }
  }
}

function buildTraceRequestId(testId: string): string {
  httpTraceRequestCounter += 1;
  return `${testId}-${httpTraceRequestCounter}`;
}

function ensureCapturedHttpTrace(testId: string): CapturedHttpTraceState {
  let state = capturedHttpTraceByTestId.get(testId);
  if (state) {
    return state;
  }

  state = {
    trace: {
      source: HTTP_TRACE_SOURCE,
      testId,
      exchangeCount: 0,
      exchanges: [],
    },
    exchangesByRequestId: new Map<string, HttpTraceExchange>(),
    pending: new Set<Promise<void>>(),
  };
  capturedHttpTraceByTestId.set(testId, state);
  return state;
}

function createTraceExchange(
  testId: string,
  requestId: string,
  request: HttpTraceExchange['request'],
): HttpTraceExchange {
  const state = ensureCapturedHttpTrace(testId);
  const exchange: HttpTraceExchange = { request };
  state.trace.exchanges.push(exchange);
  state.trace.exchangeCount = state.trace.exchanges.length;
  state.exchangesByRequestId.set(requestId, exchange);
  return exchange;
}

function trackPendingTrace(testId: string, pendingPromise: Promise<void>): void {
  const state = ensureCapturedHttpTrace(testId);
  state.pending.add(pendingPromise);
  void pendingPromise.finally(() => {
    state.pending.delete(pendingPromise);
  });
}

function getCapturedHttpTraceExchange(
  testId: string,
  requestId: string,
): HttpTraceExchange | undefined {
  return capturedHttpTraceByTestId.get(testId)?.exchangesByRequestId.get(requestId);
}

export async function flushCapturedHttpTrace(testId: string): Promise<void> {
  const state = capturedHttpTraceByTestId.get(testId);
  if (!state) {
    return;
  }

  while (state.pending.size > 0) {
    await Promise.allSettled(Array.from(state.pending));
  }
}

export function consumeCapturedHttpTrace(testId: string): TestCaseHttpTrace | undefined {
  const state = capturedHttpTraceByTestId.get(testId);
  capturedHttpTraceByTestId.delete(testId);

  if (!state || state.trace.exchanges.length === 0) {
    return undefined;
  }

  state.trace.exchangeCount = state.trace.exchanges.length;
  return state.trace;
}

function createInstrumentedFetch(resolveProvider: () => string): typeof fetch {
  return async function loggingFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
    const provider = resolveProvider();
    const activeTestContext = getActiveTestContext();
    const testId = activeTestContext?.testId;
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? (input instanceof Request ? input.method : 'GET');
    const requestHeaders = normalizeHeaders(init?.headers);
    const requestBody = serializeBodyForLog(init?.body);
    const requestId = testId ? buildTraceRequestId(testId) : undefined;
    const requestIndex = testId ? ensureCapturedHttpTrace(testId).trace.exchanges.length + 1 : 1;
    const originalPluginRequest: PluginRequestParams = {
      url,
      method,
      headers: requestHeaders ?? {},
      body: requestBody,
    };
    const pluginRequest = testId && activeTestContext
      ? await runTestPluginBeforeCase({
          provider,
          testId,
          id: activeTestContext.caseId ?? testId,
          name: activeTestContext.caseId ?? testId,
          description: activeTestContext.description ?? '',
          requestId,
          requestIndex,
          request: originalPluginRequest,
        })
      : originalPluginRequest;
    const fetchInit = createFetchInit(init, pluginRequest, originalPluginRequest);
    const fetchInput: string | URL | Request = pluginRequest.url !== url ? pluginRequest.url : input;
    const sanitizedRequestHeaders = sanitizeHeaders(pluginRequest.headers);
    const streamRequested = looksLikeStreamingRequest(
      pluginRequest.url,
      pluginRequest.headers,
      pluginRequest.body,
    );

    if (testId && requestId) {
      createTraceExchange(testId, requestId, {
        requestId,
        testId,
        url: pluginRequest.url,
        method: pluginRequest.method,
        headers: sanitizedRequestHeaders,
        body: pluginRequest.body,
      });
    }

    const requestLines: string[] = [];
    requestLines.push('');
    requestLines.push(`[${provider}] 📤 HTTP REQUEST`);
    if (testId) {
      requestLines.push(`  Test ID: ${testId}`);
    }
    if (requestId) {
      requestLines.push(`  Request ID: ${requestId}`);
    }
    requestLines.push(`  URL: ${pluginRequest.url}`);
    requestLines.push(`  Method: ${pluginRequest.method}`);

    if (Object.keys(sanitizedRequestHeaders).length > 0) {
      requestLines.push(
        `  Headers: ${JSON.stringify(sanitizedRequestHeaders, null, 2).replace(/\n/g, '\n  ')}`,
      );
    }

    if (pluginRequest.body) {
      requestLines.push(`  Body: ${truncateLogBody(pluginRequest.body).replace(/\n/g, '\n  ')}`);
    } else if (fetchInit?.body) {
      requestLines.push('  Body: [Unable to serialize]');
    }
    logRequest(requestLines);

    const startTime = Date.now();

    try {
      const response = await originalFetch(fetchInput, fetchInit);
      const duration = Date.now() - startTime;
      const responseHeaders = collectResponseHeaders(response.headers);
      const exchange = testId && requestId ? getCapturedHttpTraceExchange(testId, requestId) : undefined;
      const responseBodyCapture = (async () => {
        const body = await readResponseBody(response);
        if (exchange) {
          exchange.response = {
            requestId,
            testId,
            kind: 'response',
            url: pluginRequest.url,
            status: response.status,
            statusText: response.statusText,
            durationMs: duration,
            headers: responseHeaders,
            body,
          };
        }

        const responseLines: string[] = [];
        responseLines.push('');
        responseLines.push(`[${provider}] 📥 HTTP RESPONSE`);
        if (testId) {
          responseLines.push(`  Test ID: ${testId}`);
        }
        if (requestId) {
          responseLines.push(`  Request ID: ${requestId}`);
        }
        responseLines.push(`  URL: ${pluginRequest.url}`);
        responseLines.push(`  Status: ${response.status} ${response.statusText}`);
        responseLines.push(`  Duration: ${duration}ms`);
        responseLines.push(
          `  Headers: ${JSON.stringify(responseHeaders, null, 2).replace(/\n/g, '\n  ')}`,
        );
        responseLines.push(`  Body: ${formatBodyLine(body)}`);
        logResponse(responseLines);
        captureUsageFromJsonResponse(provider, requestBody, body);
      })();

      if (testId) {
        trackPendingTrace(testId, responseBodyCapture);
      }

      if (isStreamingResponse(response, streamRequested)) {
        return response;
      }

      await responseBodyCapture;
      return response;
    } catch (error) {
      const duration = Date.now() - startTime;
      const errorMessage = formatUnknownError(error);
      const exchange = testId && requestId ? getCapturedHttpTraceExchange(testId, requestId) : undefined;
      if (exchange) {
        exchange.response = {
          requestId,
          testId,
          kind: 'error',
          url: pluginRequest.url,
          durationMs: duration,
          headers: {},
          error: errorMessage,
        };
      }

      const errorLines: string[] = [];
      errorLines.push('');
      errorLines.push(`[${provider}] ❌ HTTP ERROR`);
      if (testId) {
        errorLines.push(`  Test ID: ${testId}`);
      }
      if (requestId) {
        errorLines.push(`  Request ID: ${requestId}`);
      }
      errorLines.push(`  URL: ${pluginRequest.url}`);
      errorLines.push(`  Duration: ${duration}ms`);
      errorLines.push(`  Error: ${errorMessage}`);
      logError(errorLines);
      throw error;
    }
  };
}

export function initializeRequestLogFile(): void {
  try {
    writeFileSync(REQUEST_LOG_FILE, '', 'utf8');
  } catch {
    // Ignore file initialization errors to avoid affecting test execution.
  }
}

export function createLoggingFetch(provider: string): typeof fetch {
  return createInstrumentedFetch(() => provider);
}

export function installGlobalFetchInterceptor(): void {
  globalThis.fetch = createInstrumentedFetch(getCurrentProvider);
}
