const fs = require('node:fs');
const path = require('node:path');

const TRACE_LOG_DIR = path.resolve(process.cwd(), '.llm-spec-traces');
const STREAM_CONTENT_TYPE_HINTS = ['text/event-stream', 'application/x-ndjson'];
const TEST_ID_ENV_KEY = 'LLM_SPEC_TEST_ID';
const TEST_ID_HEADER = 'x-test-id';

const requestSequenceByTestId = new Map();

// Ensure trace directory exists at module load time.
try {
  fs.mkdirSync(TRACE_LOG_DIR, { recursive: true });
} catch {
  // Directory creation failure should not block the SDK.
}

function traceFilePath(testId) {
  return path.join(TRACE_LOG_DIR, `${testId || '_unassigned'}.ndjson`);
}

function appendTraceEntry(testId, entry) {
  const filePath = traceFilePath(testId);
  const line = JSON.stringify(entry) + '\n';
  try {
    fs.appendFileSync(filePath, line, 'utf8');
  } catch {
    // Ignore logging failures to avoid breaking SDK calls.
  }
}

function buildRequestId(testId) {
  const key = testId || '_default';
  const current = requestSequenceByTestId.get(key) || 0;
  const next = current + 1;
  requestSequenceByTestId.set(key, next);
  return `claude-agent-${next}`;
}

function normalizeHeaders(headers) {
  if (!headers) {
    return undefined;
  }
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return Object.fromEntries(Object.entries(headers).map(([key, value]) => [key, String(value)]));
}

function mergeHeaders(...headerMaps) {
  const merged = {};
  for (const headerMap of headerMaps) {
    const normalized = normalizeHeaders(headerMap);
    if (!normalized) {
      continue;
    }
    for (const [key, value] of Object.entries(normalized)) {
      merged[key] = value;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function findHeaderValue(headers, targetKey) {
  if (!headers) {
    return undefined;
  }
  const normalizedTargetKey = targetKey.toLowerCase();
  for (const [key, value] of Object.entries(headers)) {
    if (key.toLowerCase() === normalizedTargetKey) {
      return value;
    }
  }
  return undefined;
}

function sanitizeHeaders(headers) {
  const sanitized = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (lower.includes('authorization') || lower.includes('api-key')) {
      sanitized[key] = '***REDACTED***';
      continue;
    }
    sanitized[key] = value;
  }
  return sanitized;
}

function serializeBody(body) {
  if (!body) {
    return undefined;
  }
  if (typeof body === 'string') {
    return body;
  }
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) {
    return body.toString();
  }
  if (typeof ArrayBuffer !== 'undefined' && body instanceof ArrayBuffer) {
    return `[ArrayBuffer byteLength=${body.byteLength}]`;
  }
  if (typeof ArrayBuffer !== 'undefined' && ArrayBuffer.isView(body)) {
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
    return JSON.stringify(body);
  } catch {
    return '[Unserializable body]';
  }
}

function looksLikeStreamingRequest(url, headers, body) {
  if (/\balt=sse\b/i.test(url)) {
    return true;
  }

  const acceptHeader = findHeaderValue(headers, 'accept');
  if (acceptHeader && acceptHeader.toLowerCase().includes('text/event-stream')) {
    return true;
  }

  return Boolean(body && /"stream"\s*:\s*true/i.test(body));
}

function isStreamingResponse(response, streamRequested) {
  const contentType = response.headers.get('content-type')?.toLowerCase() || '';
  if (STREAM_CONTENT_TYPE_HINTS.some((hint) => contentType.includes(hint))) {
    return true;
  }
  return streamRequested && response.body !== null;
}

async function serializeResponseBody(response) {
  const clonedResponse = response.clone();
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const bodyText = await clonedResponse.text();
      try {
        const parsed = JSON.parse(bodyText);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return bodyText;
      }
    }

    if (contentType.includes('text/')) {
      const bodyText = await clonedResponse.text();
      return bodyText;
    }

    return `[${contentType || 'unknown content type'}]`;
  } catch (error) {
    return `[Unable to read response body: ${String(error)}]`;
  }
}

if (!globalThis.__LLM_SPEC_CLAUDE_FETCH_PATCHED__) {
  Object.defineProperty(globalThis, '__LLM_SPEC_CLAUDE_FETCH_PATCHED__', {
    value: true,
    writable: false,
    configurable: false,
  });

  const originalFetch = globalThis.fetch;
  if (typeof originalFetch === 'function') {
    globalThis.fetch = async function patchedFetch(input, init) {
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.href
            : input && typeof input === 'object' && 'url' in input
              ? String(input.url)
              : '(unknown)';
      const method =
        init?.method ??
        (input && typeof input === 'object' && 'method' in input ? String(input.method) : 'GET');

      const injectedTestId = process.env[TEST_ID_ENV_KEY];
      const headers = mergeHeaders(
        input && typeof input === 'object' && 'headers' in input ? input.headers : undefined,
        init?.headers,
        injectedTestId ? { [TEST_ID_HEADER]: injectedTestId } : undefined,
      );
      const testId = findHeaderValue(headers, TEST_ID_HEADER);
      const body = serializeBody(init?.body);
      const streamRequested = looksLikeStreamingRequest(url, headers, body);
      const nextInit = headers ? { ...init, headers } : init;

      const requestId = buildRequestId(testId);

      // Write structured request entry to per-test NDJSON file.
      appendTraceEntry(testId, {
        type: 'request',
        requestId,
        testId: testId || undefined,
        url,
        method,
        headers: headers ? sanitizeHeaders(headers) : undefined,
        body,
      });

      const startedAt = Date.now();
      try {
        const response = await originalFetch.call(this, input, nextInit);
        const responseHeaders = {};
        response.headers.forEach((value, key) => {
          responseHeaders[key] = value;
        });
        const appendResponseTrace = (responseBody) => {
          // Write structured response entry to per-test NDJSON file.
          appendTraceEntry(testId, {
            type: 'response',
            requestId,
            testId: testId || undefined,
            url,
            status: response.status,
            statusText: response.statusText,
            durationMs: Date.now() - startedAt,
            headers: responseHeaders,
            body: responseBody,
          });
        };

        if (isStreamingResponse(response, streamRequested)) {
          void serializeResponseBody(response)
            .then((responseBody) => {
              appendResponseTrace(responseBody);
            })
            .catch((error) => {
              appendResponseTrace(`[Unable to read response body: ${String(error)}]`);
            });
          return response;
        }

        appendResponseTrace(await serializeResponseBody(response));

        return response;
      } catch (error) {
        // Write structured error entry to per-test NDJSON file.
        appendTraceEntry(testId, {
          type: 'error',
          requestId,
          testId: testId || undefined,
          url,
          durationMs: Date.now() - startedAt,
          error: String(error),
        });
        throw error;
      }
    };
  }
}
