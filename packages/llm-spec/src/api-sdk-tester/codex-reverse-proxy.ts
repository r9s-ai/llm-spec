import { randomUUID } from 'node:crypto';
import { appendFile } from 'node:fs/promises';
import {
  createServer,
  request as httpRequest,
  type IncomingMessage,
  type OutgoingHttpHeaders,
  type ServerResponse,
} from 'node:http';
import { request as httpsRequest } from 'node:https';
import type { Socket } from 'node:net';
import { resolve as resolvePath } from 'node:path';
import type { Duplex } from 'node:stream';
import { pipeline } from 'node:stream/promises';

import WebSocket, { WebSocketServer, type RawData } from 'ws';

import type { HttpTraceExchange, TestCaseHttpTrace } from '../types';

const CODEX_TRACE_SOURCE = 'codex-reverse-proxy';
const DEFAULT_UPSTREAM_BASE_URL = 'https://api.openai.com/v1';
const REDACTED_HEADER_VALUE = '[REDACTED]';
const REQUEST_LOG_FILE = resolvePath(process.cwd(), 'requests.log');
const WEBSOCKET_TRACE_BODY_LIMIT = 128_000;
const WEBSOCKET_MESSAGE_PREVIEW_LIMIT = 16_000;

interface ProxyTraceContext {
  testId: string;
  trace: TestCaseHttpTrace;
  exchangesByRequestId: Map<string, HttpTraceExchange>;
}

interface WebSocketTraceLogState {
  lines: string[];
  totalLength: number;
  truncated: boolean;
}

interface BufferedWebSocketMessage {
  payload: Buffer;
  isBinary: boolean;
}

interface ForwardWebSocketOptions {
  headers: Record<string, string>;
  protocols?: string[];
}

export interface CodexReverseProxy {
  baseUrl: string;
  upstreamBaseUrl: string;
  close(): Promise<TestCaseHttpTrace>;
}

const codexCaseHttpTraceByCaseId = new Map<string, TestCaseHttpTrace>();
let requestLogWriteQueue: Promise<void> = Promise.resolve();

function normalizeHeaders(
  headers: NodeJS.Dict<string | string[] | undefined>,
): Record<string, string> {
  const normalized: Record<string, string> = {};

  for (const [key, value] of Object.entries(headers)) {
    if (value === undefined) {
      continue;
    }
    normalized[key.toLowerCase()] = Array.isArray(value) ? value.join(', ') : value;
  }

  return normalized;
}

function findHeaderValue(
  headers: Record<string, string>,
  targetKey: string,
): string | undefined {
  return headers[targetKey.toLowerCase()];
}

function shouldRedactHeader(headerName: string): boolean {
  const normalized = headerName.trim().toLowerCase();
  return (
    normalized === 'authorization' ||
    normalized === 'proxy-authorization' ||
    normalized === 'x-api-key' ||
    normalized === 'api-key' ||
    normalized.includes('api-key')
  );
}

function sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
  const sanitized: Record<string, string> = {};

  for (const [key, value] of Object.entries(headers)) {
    sanitized[key] = shouldRedactHeader(key) ? REDACTED_HEADER_VALUE : value;
  }

  return sanitized;
}

function formatBodyForLog(body: string | undefined): string {
  if (!body) {
    return '[empty]';
  }

  return body.replace(/\n/g, '\n  ');
}

async function appendRequestLog(lines: readonly string[]): Promise<void> {
  const content = `${lines.join('\n')}\n`;
  const pendingWrite = requestLogWriteQueue
    .catch(() => undefined)
    .then(async () => {
      await appendFile(REQUEST_LOG_FILE, content, 'utf8');
    });

  requestLogWriteQueue = pendingWrite.catch(() => undefined);

  try {
    await pendingWrite;
  } catch {
    // Ignore request log write failures to avoid affecting test execution.
  }
}

async function logProxyRequest(options: {
  testId: string;
  requestId: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}): Promise<void> {
  const lines: string[] = [];
  lines.push('');
  lines.push('[codex] 📤 HTTP REQUEST');
  lines.push(`  Test ID: ${options.testId}`);
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Method: ${options.method}`);
  lines.push(`  Headers: ${JSON.stringify(options.headers, null, 2).replace(/\n/g, '\n  ')}`);
  lines.push(`  Body: ${formatBodyForLog(options.body)}`);
  await appendRequestLog(lines);
}

async function logProxyResponse(options: {
  testId: string;
  requestId: string;
  url: string;
  status?: number;
  statusText?: string;
  durationMs: number;
  headers: Record<string, string>;
  body?: string;
}): Promise<void> {
  const lines: string[] = [];
  lines.push('');
  lines.push('[codex] 📥 HTTP RESPONSE');
  lines.push(`  Test ID: ${options.testId}`);
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Status: ${String(options.status ?? '(unknown)')}${options.statusText ? ` ${options.statusText}` : ''}`);
  lines.push(`  Duration: ${options.durationMs}ms`);
  lines.push(`  Headers: ${JSON.stringify(options.headers, null, 2).replace(/\n/g, '\n  ')}`);
  lines.push(`  Body: ${formatBodyForLog(options.body)}`);
  await appendRequestLog(lines);
}

async function logProxyError(options: {
  testId: string;
  requestId: string;
  url: string;
  durationMs: number;
  error: string;
  headers?: Record<string, string>;
  body?: string;
}): Promise<void> {
  const lines: string[] = [];
  lines.push('');
  lines.push('[codex] ❌ HTTP ERROR');
  lines.push(`  Test ID: ${options.testId}`);
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Duration: ${options.durationMs}ms`);
  lines.push(`  Error: ${options.error}`);
  if (options.headers) {
    lines.push(`  Headers: ${JSON.stringify(options.headers, null, 2).replace(/\n/g, '\n  ')}`);
  }
  if (options.body !== undefined) {
    lines.push(`  Body: ${formatBodyForLog(options.body)}`);
  }
  await appendRequestLog(lines);
}

function serializeBody(body: Buffer, contentType: string | undefined): string | undefined {
  if (body.length === 0) {
    return undefined;
  }

  const normalizedContentType = contentType?.toLowerCase() ?? '';
  const isTextLike =
    normalizedContentType === '' ||
    normalizedContentType.startsWith('text/') ||
    normalizedContentType.includes('json') ||
    normalizedContentType.includes('xml') ||
    normalizedContentType.includes('javascript') ||
    normalizedContentType.includes('event-stream') ||
    normalizedContentType.includes('x-www-form-urlencoded');

  return isTextLike ? body.toString('utf8') : `base64:${body.toString('base64')}`;
}

async function readRequestBody(request: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];

  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  return Buffer.concat(chunks);
}

function joinUrlPath(prefix: string, suffix: string): string {
  const normalizedPrefix = prefix === '/' ? '' : prefix.replace(/\/+$/, '');
  const normalizedSuffix = suffix.startsWith('/') ? suffix : `/${suffix}`;

  if (!normalizedPrefix) {
    return normalizedSuffix || '/';
  }

  if (
    normalizedSuffix === normalizedPrefix ||
    normalizedSuffix.startsWith(`${normalizedPrefix}/`)
  ) {
    return normalizedSuffix;
  }

  const joined = `${normalizedPrefix}${normalizedSuffix}`;
  return joined || '/';
}

function createUpstreamUrl(baseUrl: string, requestUrl: string | undefined): URL {
  const upstreamBaseUrl = new URL(baseUrl);
  const incomingUrl = new URL(requestUrl ?? '/', 'http://127.0.0.1');
  upstreamBaseUrl.pathname = joinUrlPath(upstreamBaseUrl.pathname, incomingUrl.pathname);
  upstreamBaseUrl.search = incomingUrl.search;
  return upstreamBaseUrl;
}

function createUpstreamWebSocketUrl(baseUrl: string, requestUrl: string | undefined): URL {
  const upstreamUrl = createUpstreamUrl(baseUrl, requestUrl);
  upstreamUrl.protocol = upstreamUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return upstreamUrl;
}

function createForwardHttpHeaders(
  requestHeaders: Record<string, string>,
  body: Buffer,
  upstreamUrl: URL,
): Record<string, string> {
  const forwardHeaders: Record<string, string> = {
    ...requestHeaders,
    host: upstreamUrl.host,
    'accept-encoding': 'identity',
  };

  delete forwardHeaders.connection;
  delete forwardHeaders['proxy-connection'];
  delete forwardHeaders['transfer-encoding'];
  delete forwardHeaders['content-length'];

  if (body.length > 0) {
    forwardHeaders['content-length'] = String(body.length);
  }

  return forwardHeaders;
}

function createForwardWebSocketOptions(
  requestHeaders: Record<string, string>,
  upstreamUrl: URL,
): ForwardWebSocketOptions {
  const headers: Record<string, string> = {
    ...requestHeaders,
    host: upstreamUrl.host,
  };

  const protocolHeader = headers['sec-websocket-protocol'];
  delete headers.connection;
  delete headers.upgrade;
  delete headers['proxy-connection'];
  delete headers['sec-websocket-key'];
  delete headers['sec-websocket-version'];
  delete headers['sec-websocket-extensions'];
  delete headers['sec-websocket-protocol'];

  const protocols = protocolHeader
    ?.split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    headers,
    protocols: protocols && protocols.length > 0 ? protocols : undefined,
  };
}

function createTraceExchange(
  traceContext: ProxyTraceContext,
  requestId: string,
  request: HttpTraceExchange['request'],
): HttpTraceExchange {
  const exchange: HttpTraceExchange = { request };
  traceContext.trace.exchanges.push(exchange);
  traceContext.trace.exchangeCount = traceContext.trace.exchanges.length;
  traceContext.exchangesByRequestId.set(requestId, exchange);
  return exchange;
}

function getTraceExchange(
  traceContext: ProxyTraceContext,
  requestId: string,
): HttpTraceExchange | undefined {
  return traceContext.exchangesByRequestId.get(requestId);
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength)}...[truncated ${text.length - maxLength} chars]`;
}

function createWebSocketTraceLogState(): WebSocketTraceLogState {
  return {
    lines: [],
    totalLength: 0,
    truncated: false,
  };
}

function appendWebSocketTraceLine(state: WebSocketTraceLogState, line: string): void {
  if (state.truncated) {
    return;
  }

  const normalizedLine = truncateText(line, WEBSOCKET_MESSAGE_PREVIEW_LIMIT);
  const addedLength = normalizedLine.length + 1;

  if (state.totalLength + addedLength > WEBSOCKET_TRACE_BODY_LIMIT) {
    state.lines.push('[truncated]');
    state.totalLength += '[truncated]'.length + 1;
    state.truncated = true;
    return;
  }

  state.lines.push(normalizedLine);
  state.totalLength += addedLength;
}

function finalizeWebSocketTraceBody(state: WebSocketTraceLogState): string {
  if (state.lines.length === 0) {
    return '[websocket session established; no frames captured]';
  }

  return state.lines.join('\n');
}

function normalizeWebSocketData(data: RawData): Buffer {
  if (typeof data === 'string') {
    return Buffer.from(data, 'utf8');
  }

  if (Buffer.isBuffer(data)) {
    return data;
  }

  if (Array.isArray(data)) {
    return Buffer.concat(data.map((chunk) => Buffer.from(chunk)));
  }

  if (data instanceof ArrayBuffer) {
    return Buffer.from(data);
  }

  return Buffer.from(data);
}

function formatWebSocketPayload(payload: Buffer, isBinary: boolean): string {
  if (isBinary) {
    return `base64:${payload.toString('base64')}`;
  }

  return payload.toString('utf8');
}

function normalizeWebSocketCloseCode(code: number): number | undefined {
  if (code === 0 || code === 1005 || code === 1006 || code === 1015) {
    return undefined;
  }

  return code;
}

function safeCloseWebSocket(socket: WebSocket, code?: number): void {
  if (socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING) {
    return;
  }

  if (socket.readyState === WebSocket.CONNECTING) {
    socket.terminate();
    return;
  }

  try {
    if (code !== undefined) {
      socket.close(code);
      return;
    }
    socket.close();
  } catch {
    socket.terminate();
  }
}

function writeUpgradeErrorResponse(
  socket: Duplex,
  statusCode: number,
  statusText: string,
  body: string,
): void {
  if (socket.destroyed) {
    return;
  }

  const bodyBuffer = Buffer.from(body, 'utf8');
  socket.write(
    `HTTP/1.1 ${statusCode} ${statusText}\r\n`
      + 'Connection: close\r\n'
      + 'Content-Type: application/json; charset=utf-8\r\n'
      + `Content-Length: ${String(bodyBuffer.length)}\r\n`
      + '\r\n',
  );
  socket.write(bodyBuffer);
  socket.destroy();
}

async function proxyWebSocketSession(options: {
  clientSocket: WebSocket;
  requestId: string;
  startedAt: number;
  traceContext: ProxyTraceContext;
  upstreamUrl: URL;
  headers: Record<string, string>;
  protocols?: string[];
}): Promise<void> {
  const {
    clientSocket,
    requestId,
    startedAt,
    traceContext,
    upstreamUrl,
    headers,
    protocols,
  } = options;

  const traceLogState = createWebSocketTraceLogState();
  const bufferedClientMessages: BufferedWebSocketMessage[] = [];
  const sanitizedResponseHeaders: Record<string, string> = {};
  const exchange = getTraceExchange(traceContext, requestId);
  let responseStatus = 101;
  let responseStatusText = 'Switching Protocols';
  let responseKind: 'response' | 'error' = 'response';
  let errorMessage: string | undefined;
  let clientClosed = false;
  let upstreamClosed = false;
  let upstreamOpen = false;
  let resolved = false;

  const upstreamSocket = new WebSocket(upstreamUrl, protocols, { headers });

  return new Promise<void>((resolve) => {
    const finalize = async (): Promise<void> => {
      if (resolved) {
        return;
      }
      resolved = true;

      const body = finalizeWebSocketTraceBody(traceLogState);
      const durationMs = Date.now() - startedAt;

      if (exchange) {
        exchange.response = {
          requestId,
          testId: traceContext.testId,
          kind: responseKind,
          url: upstreamUrl.toString(),
          status: responseKind === 'response' ? responseStatus : undefined,
          statusText: responseKind === 'response' ? responseStatusText : undefined,
          durationMs,
          headers: { ...sanitizedResponseHeaders },
          body,
          error: errorMessage,
        };
      }

      if (responseKind === 'response') {
        await logProxyResponse({
          testId: traceContext.testId,
          requestId,
          url: upstreamUrl.toString(),
          status: responseStatus,
          statusText: responseStatusText,
          durationMs,
          headers: sanitizedResponseHeaders,
          body,
        });
      } else {
        await logProxyError({
          testId: traceContext.testId,
          requestId,
          url: upstreamUrl.toString(),
          durationMs,
          error: errorMessage ?? 'websocket proxy failed',
          headers: Object.keys(sanitizedResponseHeaders).length > 0 ? sanitizedResponseHeaders : undefined,
          body,
        });
      }

      safeCloseWebSocket(clientSocket, normalizeWebSocketCloseCode(1011));
      safeCloseWebSocket(upstreamSocket, normalizeWebSocketCloseCode(1011));
      resolve();
    };

    const maybeFinalizeSuccess = (): void => {
      if (clientClosed && upstreamClosed) {
        void finalize();
      }
    };

    const fail = (message: string): void => {
      if (responseKind !== 'error') {
        responseKind = 'error';
        errorMessage = message;
      }

      appendWebSocketTraceLine(traceLogState, `[error] ${message}`);
      safeCloseWebSocket(clientSocket, normalizeWebSocketCloseCode(1011));
      safeCloseWebSocket(upstreamSocket, normalizeWebSocketCloseCode(1011));
      void finalize();
    };

    upstreamSocket.once('upgrade', (response) => {
      responseStatus = response.statusCode ?? 101;
      responseStatusText = response.statusMessage ?? 'Switching Protocols';
      Object.assign(sanitizedResponseHeaders, sanitizeHeaders(normalizeHeaders(response.headers)));
      appendWebSocketTraceLine(
        traceLogState,
        `[handshake] ${String(responseStatus)} ${responseStatusText}`,
      );
    });

    upstreamSocket.once('unexpected-response', (_request, response) => {
      responseStatus = response.statusCode ?? 502;
      responseStatusText = response.statusMessage ?? 'Bad Gateway';
      Object.assign(sanitizedResponseHeaders, sanitizeHeaders(normalizeHeaders(response.headers)));
      response.resume();
      fail(`unexpected websocket response: ${String(responseStatus)} ${responseStatusText}`);
    });

    upstreamSocket.once('open', () => {
      upstreamOpen = true;
      appendWebSocketTraceLine(traceLogState, '[open] upstream websocket connected');

      for (const message of bufferedClientMessages) {
        upstreamSocket.send(message.payload, { binary: message.isBinary });
      }
      bufferedClientMessages.length = 0;
    });

    clientSocket.on('message', (data, isBinary) => {
      const payload = normalizeWebSocketData(data);
      appendWebSocketTraceLine(
        traceLogState,
        `[client -> upstream ${isBinary ? 'binary' : 'text'}] ${formatWebSocketPayload(payload, isBinary)}`,
      );

      if (upstreamOpen && upstreamSocket.readyState === WebSocket.OPEN) {
        upstreamSocket.send(payload, { binary: isBinary });
        return;
      }

      bufferedClientMessages.push({ payload, isBinary });
    });

    upstreamSocket.on('message', (data, isBinary) => {
      const payload = normalizeWebSocketData(data);
      appendWebSocketTraceLine(
        traceLogState,
        `[upstream -> client ${isBinary ? 'binary' : 'text'}] ${formatWebSocketPayload(payload, isBinary)}`,
      );

      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.send(payload, { binary: isBinary });
      }
    });

    clientSocket.once('close', (code, reasonBuffer) => {
      clientClosed = true;
      const reason = reasonBuffer.toString('utf8');
      appendWebSocketTraceLine(
        traceLogState,
        `[client close] code=${String(code)}${reason ? ` reason=${reason}` : ''}`,
      );
      safeCloseWebSocket(upstreamSocket, normalizeWebSocketCloseCode(code));
      maybeFinalizeSuccess();
    });

    upstreamSocket.once('close', (code, reasonBuffer) => {
      upstreamClosed = true;
      const reason = reasonBuffer.toString('utf8');
      appendWebSocketTraceLine(
        traceLogState,
        `[upstream close] code=${String(code)}${reason ? ` reason=${reason}` : ''}`,
      );
      safeCloseWebSocket(clientSocket, normalizeWebSocketCloseCode(code));
      maybeFinalizeSuccess();
    });

    clientSocket.once('error', (error) => {
      fail(`client websocket error: ${error.message}`);
    });

    upstreamSocket.once('error', (error) => {
      fail(`upstream websocket error: ${error.message}`);
    });
  });
}

async function handleWebSocketUpgrade(
  request: IncomingMessage,
  socket: Duplex,
  head: Buffer,
  upstreamBaseUrl: string,
  traceContext: ProxyTraceContext,
  webSocketServer: WebSocketServer,
): Promise<void> {
  const startedAt = Date.now();
  const requestId = randomUUID();

  try {
    const incomingHeaders = normalizeHeaders(request.headers);
    const upstreamUrl = createUpstreamWebSocketUrl(upstreamBaseUrl, request.url);
    const { headers, protocols } = createForwardWebSocketOptions(incomingHeaders, upstreamUrl);
    const sanitizedRequestHeaders = sanitizeHeaders(headers);
    const requestMethod = request.method ?? 'GET';
    const requestBody = protocols && protocols.length > 0
      ? `[websocket upgrade protocols=${protocols.join(',')}]`
      : '[websocket upgrade]';

    createTraceExchange(traceContext, requestId, {
      requestId,
      testId: traceContext.testId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizedRequestHeaders,
      body: requestBody,
    });
    await logProxyRequest({
      testId: traceContext.testId,
      requestId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizedRequestHeaders,
      body: requestBody,
    });

    await new Promise<void>((resolve, reject) => {
      webSocketServer.handleUpgrade(request, socket, head, (clientSocket) => {
        void proxyWebSocketSession({
          clientSocket,
          requestId,
          startedAt,
          traceContext,
          upstreamUrl,
          headers,
          protocols,
        }).then(resolve, reject);
      });
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    const exchange = getTraceExchange(traceContext, requestId);

    if (exchange) {
      exchange.response = {
        requestId,
        testId: traceContext.testId,
        kind: 'error',
        url: exchange.request.url,
        durationMs: Date.now() - startedAt,
        headers: {},
        error: errorMessage,
      };
    }

    await logProxyError({
      testId: traceContext.testId,
      requestId,
      url: exchange?.request.url ?? createUpstreamWebSocketUrl(upstreamBaseUrl, request.url).toString(),
      durationMs: Date.now() - startedAt,
      error: errorMessage,
    });
    writeUpgradeErrorResponse(
      socket,
      502,
      'Bad Gateway',
      JSON.stringify({ error: 'reverse proxy websocket upgrade failed', detail: errorMessage }),
    );
  }
}

async function handleHttpRequest(
  request: IncomingMessage,
  response: ServerResponse,
  upstreamBaseUrl: string,
  traceContext: ProxyTraceContext,
): Promise<void> {
  const startedAt = Date.now();
  const requestId = randomUUID();

  try {
    const requestBody = await readRequestBody(request);
    const incomingHeaders = normalizeHeaders(request.headers);
    const upstreamUrl = createUpstreamUrl(upstreamBaseUrl, request.url);
    const forwardHeaders = createForwardHttpHeaders(incomingHeaders, requestBody, upstreamUrl);
    const requestMethod = request.method ?? 'GET';
    const serializedRequestBody = serializeBody(
      requestBody,
      findHeaderValue(forwardHeaders, 'content-type'),
    );
    createTraceExchange(traceContext, requestId, {
      requestId,
      testId: traceContext.testId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizeHeaders(forwardHeaders),
      body: serializedRequestBody,
    });
    await logProxyRequest({
      testId: traceContext.testId,
      requestId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizeHeaders(forwardHeaders),
      body: serializedRequestBody,
    });

    await new Promise<void>((resolve) => {
      const sendRequest = upstreamUrl.protocol === 'https:' ? httpsRequest : httpRequest;
      const upstreamRequest = sendRequest({
        protocol: upstreamUrl.protocol,
        hostname: upstreamUrl.hostname,
        port: upstreamUrl.port || undefined,
        method: requestMethod,
        path: `${upstreamUrl.pathname}${upstreamUrl.search}`,
        headers: forwardHeaders as OutgoingHttpHeaders,
      });

      const resolveWithError = async (error: unknown): Promise<void> => {
        const errorMessage = error instanceof Error ? error.message : String(error);
        const exchange = getTraceExchange(traceContext, requestId);

        if (exchange) {
          exchange.response = {
            requestId,
            testId: traceContext.testId,
            kind: 'error',
            url: upstreamUrl.toString(),
            durationMs: Date.now() - startedAt,
            headers: {},
            error: errorMessage,
          };
        }

        if (!response.headersSent) {
          response.writeHead(502, 'Bad Gateway', {
            'content-type': 'application/json; charset=utf-8',
          });
          response.end(JSON.stringify({ error: 'reverse proxy error', detail: errorMessage }));
        } else if (!response.destroyed) {
          response.destroy(error instanceof Error ? error : new Error(errorMessage));
        }

        await logProxyError({
          testId: traceContext.testId,
          requestId,
          url: upstreamUrl.toString(),
          durationMs: Date.now() - startedAt,
          error: errorMessage,
        });
        resolve();
      };

      upstreamRequest.once('error', (error) => {
        void resolveWithError(error);
      });

      upstreamRequest.once('response', (upstreamResponse) => {
        void (async () => {
          try {
            response.writeHead(
              upstreamResponse.statusCode ?? 502,
              upstreamResponse.statusMessage,
              upstreamResponse.headers,
            );

            const responseChunks: Buffer[] = [];
            upstreamResponse.on('data', (chunk) => {
              responseChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
            });

            await pipeline(upstreamResponse, response);

            const normalizedResponseHeaders = normalizeHeaders(upstreamResponse.headers);
            const sanitizedResponseHeaders = sanitizeHeaders(normalizedResponseHeaders);
            const responseBody = serializeBody(
              Buffer.concat(responseChunks),
              findHeaderValue(normalizedResponseHeaders, 'content-type'),
            );
            const exchange = getTraceExchange(traceContext, requestId);

            if (exchange) {
              exchange.response = {
                requestId,
                testId: traceContext.testId,
                kind: 'response',
                url: upstreamUrl.toString(),
                status: upstreamResponse.statusCode,
                statusText: upstreamResponse.statusMessage,
                durationMs: Date.now() - startedAt,
                headers: sanitizedResponseHeaders,
                body: responseBody,
              };
            }

            await logProxyResponse({
              testId: traceContext.testId,
              requestId,
              url: upstreamUrl.toString(),
              status: upstreamResponse.statusCode,
              statusText: upstreamResponse.statusMessage,
              durationMs: Date.now() - startedAt,
              headers: sanitizedResponseHeaders,
              body: responseBody,
            });
            resolve();
          } catch (error) {
            await resolveWithError(error);
          }
        })();
      });

      if (requestBody.length > 0) {
        upstreamRequest.write(requestBody);
      }
      upstreamRequest.end();
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    if (!response.headersSent) {
      response.writeHead(500, 'Internal Server Error', {
        'content-type': 'application/json; charset=utf-8',
      });
      response.end(JSON.stringify({ error: 'reverse proxy request handling failed', detail: errorMessage }));
    } else if (!response.destroyed) {
      response.destroy(error instanceof Error ? error : new Error(errorMessage));
    }
  }
}

export function resetCodexCaseHttpTraces(): void {
  codexCaseHttpTraceByCaseId.clear();
}

export function getCodexCaseHttpTrace(caseId: string): TestCaseHttpTrace | undefined {
  return codexCaseHttpTraceByCaseId.get(caseId);
}

export function setCodexCaseHttpTrace(caseId: string, trace: TestCaseHttpTrace): void {
  codexCaseHttpTraceByCaseId.set(caseId, trace);
}

export async function startCodexReverseProxy(
  testId: string,
  upstreamBaseUrl: string = DEFAULT_UPSTREAM_BASE_URL,
): Promise<CodexReverseProxy> {
  const normalizedUpstreamBaseUrl = new URL(upstreamBaseUrl);
  if (normalizedUpstreamBaseUrl.protocol !== 'http:' && normalizedUpstreamBaseUrl.protocol !== 'https:') {
    throw new Error(`Unsupported Codex upstream protocol: ${normalizedUpstreamBaseUrl.protocol}`);
  }

  const sockets = new Set<Socket>();
  const activeRequests = new Set<Promise<void>>();
  const traceContext: ProxyTraceContext = {
    testId,
    trace: {
      source: CODEX_TRACE_SOURCE,
      testId,
      exchangeCount: 0,
      exchanges: [],
    },
    exchangesByRequestId: new Map<string, HttpTraceExchange>(),
  };
  const webSocketServer = new WebSocketServer({ noServer: true });
  const server = createServer((request, response) => {
    const requestPromise = handleHttpRequest(
      request,
      response,
      normalizedUpstreamBaseUrl.toString(),
      traceContext,
    ).finally(() => {
      activeRequests.delete(requestPromise);
    });
    activeRequests.add(requestPromise);
  });

  server.on('upgrade', (request, socket, head) => {
    const requestPromise = handleWebSocketUpgrade(
      request,
      socket,
      head,
      normalizedUpstreamBaseUrl.toString(),
      traceContext,
      webSocketServer,
    ).finally(() => {
      activeRequests.delete(requestPromise);
    });
    activeRequests.add(requestPromise);
  });

  server.keepAliveTimeout = 1;
  server.headersTimeout = 30_000;
  server.on('connection', (socket) => {
    sockets.add(socket);
    socket.on('close', () => {
      sockets.delete(socket);
    });
  });

  await new Promise<void>((resolve, reject) => {
    const onError = (error: Error) => {
      server.off('listening', onListening);
      reject(error);
    };
    const onListening = () => {
      server.off('error', onError);
      resolve();
    };

    server.once('error', onError);
    server.once('listening', onListening);
    server.listen(0, '127.0.0.1');
  });

  const address = server.address();
  if (!address || typeof address === 'string') {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });
    throw new Error('Codex reverse proxy failed to bind to a TCP port');
  }

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    upstreamBaseUrl: normalizedUpstreamBaseUrl.toString(),
    async close(): Promise<TestCaseHttpTrace> {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) {
            reject(error);
            return;
          }
          resolve();
        });
        server.closeIdleConnections();
      });

      webSocketServer.close();
      await Promise.allSettled(activeRequests);

      for (const socket of sockets) {
        if (!socket.destroyed) {
          socket.destroy();
        }
      }

      traceContext.trace.exchangeCount = traceContext.trace.exchanges.length;
      return traceContext.trace;
    },
  };
}
