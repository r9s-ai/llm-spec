import { randomUUID } from 'node:crypto';
import { appendFile, mkdir } from 'node:fs/promises';
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
import { pipeline } from 'node:stream/promises';

const CLAUDE_AGENT_TRACE_DIR = resolvePath(process.cwd(), '.llm-spec-traces');
const CLAUDE_AGENT_TEST_ID_HEADER = 'x-test-id';
const DEFAULT_UPSTREAM_BASE_URL = 'https://api.anthropic.com';
const REDACTED_HEADER_VALUE = '[REDACTED]';
const REQUEST_LOG_FILE = resolvePath(process.cwd(), 'requests.log');

interface TraceEntry {
  type: 'request' | 'response' | 'error';
  requestId: string;
  testId?: string;
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  status?: number;
  statusText?: string;
  durationMs?: number;
  error?: string;
}

export interface ClaudeAgentReverseProxy {
  baseUrl: string;
  upstreamBaseUrl: string;
  close(): Promise<void>;
}

const traceWriteQueueByFile = new Map<string, Promise<void>>();
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
    normalized === 'anthropic-api-key' ||
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
  testId?: string;
  requestId: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}): Promise<void> {
  const lines: string[] = [];
  lines.push('');
  lines.push('[claude-agent] 📤 HTTP REQUEST');
  if (options.testId) {
    lines.push(`  Test ID: ${options.testId}`);
  }
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Method: ${options.method}`);
  lines.push(`  Headers: ${JSON.stringify(options.headers, null, 2).replace(/\n/g, '\n  ')}`);
  lines.push(`  Body: ${formatBodyForLog(options.body)}`);
  await appendRequestLog(lines);
}

async function logProxyResponse(options: {
  testId?: string;
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
  lines.push('[claude-agent] 📥 HTTP RESPONSE');
  if (options.testId) {
    lines.push(`  Test ID: ${options.testId}`);
  }
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Status: ${String(options.status ?? '(unknown)')}${options.statusText ? ` ${options.statusText}` : ''}`);
  lines.push(`  Duration: ${options.durationMs}ms`);
  lines.push(`  Headers: ${JSON.stringify(options.headers, null, 2).replace(/\n/g, '\n  ')}`);
  lines.push(`  Body: ${formatBodyForLog(options.body)}`);
  await appendRequestLog(lines);
}

async function logProxyError(options: {
  testId?: string;
  requestId: string;
  url: string;
  durationMs: number;
  error: string;
}): Promise<void> {
  const lines: string[] = [];
  lines.push('');
  lines.push('[claude-agent] ❌ HTTP ERROR');
  if (options.testId) {
    lines.push(`  Test ID: ${options.testId}`);
  }
  lines.push(`  Request ID: ${options.requestId}`);
  lines.push(`  URL: ${options.url}`);
  lines.push(`  Duration: ${options.durationMs}ms`);
  lines.push(`  Error: ${options.error}`);
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

async function appendTraceEntry(testId: string | undefined, entry: TraceEntry): Promise<void> {
  if (!testId) {
    return;
  }

  const traceFile = resolvePath(CLAUDE_AGENT_TRACE_DIR, `${testId}.ndjson`);
  const line = `${JSON.stringify(entry)}\n`;
  const pendingWrite = (traceWriteQueueByFile.get(traceFile) ?? Promise.resolve())
    .catch(() => undefined)
    .then(async () => {
      await mkdir(CLAUDE_AGENT_TRACE_DIR, { recursive: true });
      await appendFile(traceFile, line, 'utf8');
    });

  traceWriteQueueByFile.set(traceFile, pendingWrite);

  try {
    await pendingWrite;
  } finally {
    if (traceWriteQueueByFile.get(traceFile) === pendingWrite) {
      traceWriteQueueByFile.delete(traceFile);
    }
  }
}

function createForwardHeaders(
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

async function handleProxyRequest(
  request: IncomingMessage,
  response: ServerResponse,
  upstreamBaseUrl: string,
): Promise<void> {
  const startedAt = Date.now();
  const requestId = randomUUID();

  try {
    const requestBody = await readRequestBody(request);
    const incomingHeaders = normalizeHeaders(request.headers);
    const upstreamUrl = createUpstreamUrl(upstreamBaseUrl, request.url);
    const forwardHeaders = createForwardHeaders(incomingHeaders, requestBody, upstreamUrl);
    const testId = findHeaderValue(forwardHeaders, CLAUDE_AGENT_TEST_ID_HEADER);
    const requestMethod = request.method ?? 'GET';

    await appendTraceEntry(testId, {
      type: 'request',
      requestId,
      testId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizeHeaders(forwardHeaders),
      body: serializeBody(requestBody, findHeaderValue(forwardHeaders, 'content-type')),
    });
    await logProxyRequest({
      testId,
      requestId,
      url: upstreamUrl.toString(),
      method: requestMethod,
      headers: sanitizeHeaders(forwardHeaders),
      body: serializeBody(requestBody, findHeaderValue(forwardHeaders, 'content-type')),
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

        if (!response.headersSent) {
          response.writeHead(502, 'Bad Gateway', {
            'content-type': 'application/json; charset=utf-8',
          });
          response.end(JSON.stringify({ error: 'reverse proxy error', detail: errorMessage }));
        } else if (!response.destroyed) {
          response.destroy(error instanceof Error ? error : new Error(errorMessage));
        }

        await appendTraceEntry(testId, {
          type: 'error',
          requestId,
          testId,
          url: upstreamUrl.toString(),
          durationMs: Date.now() - startedAt,
          error: errorMessage,
        });
        await logProxyError({
          testId,
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
            const responseBody = serializeBody(
              Buffer.concat(responseChunks),
              findHeaderValue(normalizedResponseHeaders, 'content-type'),
            );
            await appendTraceEntry(testId, {
              type: 'response',
              requestId,
              testId,
              url: upstreamUrl.toString(),
              status: upstreamResponse.statusCode,
              statusText: upstreamResponse.statusMessage,
              durationMs: Date.now() - startedAt,
              headers: sanitizeHeaders(normalizedResponseHeaders),
              body: responseBody,
            });
            await logProxyResponse({
              testId,
              requestId,
              url: upstreamUrl.toString(),
              status: upstreamResponse.statusCode,
              statusText: upstreamResponse.statusMessage,
              durationMs: Date.now() - startedAt,
              headers: normalizedResponseHeaders,
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

export async function startClaudeAgentReverseProxy(
  upstreamBaseUrl: string = DEFAULT_UPSTREAM_BASE_URL,
): Promise<ClaudeAgentReverseProxy> {
  const normalizedUpstreamBaseUrl = new URL(upstreamBaseUrl);
  if (normalizedUpstreamBaseUrl.protocol !== 'http:' && normalizedUpstreamBaseUrl.protocol !== 'https:') {
    throw new Error(`Unsupported Claude Agent upstream protocol: ${normalizedUpstreamBaseUrl.protocol}`);
  }

  await mkdir(CLAUDE_AGENT_TRACE_DIR, { recursive: true });

  const sockets = new Set<Socket>();
  const activeRequests = new Set<Promise<void>>();
  const server = createServer((request, response) => {
    const requestPromise = handleProxyRequest(request, response, normalizedUpstreamBaseUrl.toString())
      .finally(() => {
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
    throw new Error('Claude Agent reverse proxy failed to bind to a TCP port');
  }

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    upstreamBaseUrl: normalizedUpstreamBaseUrl.toString(),
    async close(): Promise<void> {
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

      await Promise.allSettled(activeRequests);

      for (const socket of sockets) {
        if (!socket.destroyed) {
          socket.destroy();
        }
      }
    },
  };
}
