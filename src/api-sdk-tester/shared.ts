import type { ProviderName, ProviderSummary, TestCaseResult } from '../types';

export interface TestCase {
  id: string;
  description: string;
  covers: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
}

let currentProvider = 'unknown';
const originalFetch = globalThis.fetch;

/**
 * 设置当前provider名称,用于日志记录
 */
export function setCurrentProvider(provider: string): void {
  currentProvider = provider;
}

/**
 * 创建一个带有日志记录功能的自定义 fetch 函数
 * 记录 HTTP 请求和响应的详细信息
 */
export function createLoggingFetch(provider: string): typeof fetch {
  return async function loggingFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? 'GET';

    // 记录请求信息
    console.log(`\n[${provider}] 📤 HTTP REQUEST`);
    console.log(`  URL: ${url}`);
    console.log(`  Method: ${method}`);

    if (init?.headers) {
      const headers =
        init.headers instanceof Headers
          ? Object.fromEntries(init.headers.entries())
          : Array.isArray(init.headers)
            ? Object.fromEntries(init.headers)
            : init.headers;

      // 隐藏敏感信息
      const sanitizedHeaders: Record<string, string> = {};
      for (const [key, value] of Object.entries(headers)) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('authorization') || lowerKey.includes('api-key')) {
          sanitizedHeaders[key] = '***REDACTED***';
        } else {
          sanitizedHeaders[key] = String(value);
        }
      }
      console.log(`  Headers: ${JSON.stringify(sanitizedHeaders, null, 2).replace(/\n/g, '\n  ')}`);
    }

    if (init?.body) {
      try {
        const bodyPreview =
          typeof init.body === 'string' ? init.body : JSON.stringify(init.body, null, 2);
        const truncated =
          bodyPreview.length > 500 ? bodyPreview.slice(0, 500) + '...(truncated)' : bodyPreview;
        console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
      } catch {
        console.log(`  Body: [Unable to serialize]`);
      }
    }

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

      // 克隆响应以便读取body而不影响原始响应
      const clonedResponse = response.clone();
      try {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          const bodyText = await clonedResponse.text();
          try {
            const bodyJson = JSON.parse(bodyText);
            const bodyPreview = JSON.stringify(bodyJson, null, 2);
            const truncated =
              bodyPreview.length > 500 ? bodyPreview.slice(0, 500) + '...(truncated)' : bodyPreview;
            console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
          } catch {
            const truncated =
              bodyText.length > 500 ? bodyText.slice(0, 500) + '...(truncated)' : bodyText;
            console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
          }
        } else if (contentType.includes('text/')) {
          const bodyText = await clonedResponse.text();
          const truncated =
            bodyText.length > 500 ? bodyText.slice(0, 500) + '...(truncated)' : bodyText;
          console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
        } else {
          console.log(`  Body: [${contentType || 'unknown content type'}]`);
        }
      } catch (error) {
        console.log(`  Body: [Unable to read: ${error}]`);
      }

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
 * 安装全局的fetch拦截器,用于记录所有HTTP请求
 */
export function installGlobalFetchInterceptor(): void {
  globalThis.fetch = async function (input: string | URL | Request, init?: RequestInit): Promise<Response> {
    const provider = currentProvider;
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? 'GET';

    // 记录请求信息
    console.log(`\n[${provider}] 📤 HTTP REQUEST`);
    console.log(`  URL: ${url}`);
    console.log(`  Method: ${method}`);

    if (init?.headers) {
      const headers =
        init.headers instanceof Headers
          ? Object.fromEntries(init.headers.entries())
          : Array.isArray(init.headers)
            ? Object.fromEntries(init.headers)
            : init.headers;

      // 隐藏敏感信息
      const sanitizedHeaders: Record<string, string> = {};
      for (const [key, value] of Object.entries(headers)) {
        const lowerKey = key.toLowerCase();
        if (lowerKey.includes('authorization') || lowerKey.includes('api-key')) {
          sanitizedHeaders[key] = '***REDACTED***';
        } else {
          sanitizedHeaders[key] = String(value);
        }
      }
      console.log(`  Headers: ${JSON.stringify(sanitizedHeaders, null, 2).replace(/\n/g, '\n  ')}`);
    }

    if (init?.body) {
      try {
        const bodyPreview =
          typeof init.body === 'string' ? init.body : JSON.stringify(init.body, null, 2);
        const truncated =
          bodyPreview.length > 500 ? bodyPreview.slice(0, 500) + '...(truncated)' : bodyPreview;
        console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
      } catch {
        console.log(`  Body: [Unable to serialize]`);
      }
    }

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

      // 克隆响应以便读取body而不影响原始响应
      const clonedResponse = response.clone();
      try {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          const bodyText = await clonedResponse.text();
          try {
            const bodyJson = JSON.parse(bodyText);
            const bodyPreview = JSON.stringify(bodyJson, null, 2);
            const truncated =
              bodyPreview.length > 500 ? bodyPreview.slice(0, 500) + '...(truncated)' : bodyPreview;
            console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
          } catch {
            const truncated =
              bodyText.length > 500 ? bodyText.slice(0, 500) + '...(truncated)' : bodyText;
            console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
          }
        } else if (contentType.includes('text/')) {
          const bodyText = await clonedResponse.text();
          const truncated =
            bodyText.length > 500 ? bodyText.slice(0, 500) + '...(truncated)' : bodyText;
          console.log(`  Body: ${truncated.replace(/\n/g, '\n  ')}`);
        } else {
          console.log(`  Body: [${contentType || 'unknown content type'}]`);
        }
      } catch (error) {
        console.log(`  Body: [Unable to read: ${error}]`);
      }

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
  };

  const stopReason = obj.stop_reason ?? 'unknown';
  const text = (obj.content ?? [])
    .filter((item) => item.type === 'text' && typeof item.text === 'string')
    .map((item) => item.text as string)
    .join(' ');
  const toolUseCount = (obj.content ?? []).filter((item) => item.type === 'tool_use').length;
  return `stop_reason=${stopReason}, tool_use=${toolUseCount}, text="${truncate(text)}"`;
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
    };
  } catch (error) {
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'failed',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      error: formatError(error),
    };
  }
}

export function createSetupSkippedSummary(
  provider: ProviderName,
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

export async function executeProviderCases(
  provider: ProviderName,
  model: string,
  apiBaseUrl: string | undefined,
  allParams: readonly string[],
  cases: readonly TestCase[],
  failFast: boolean,
): Promise<ProviderSummary> {
  const startedAt = new Date().toISOString();
  const caseResults: TestCaseResult[] = [];

  for (const testCase of cases) {
    console.log(`[${provider}] running ${testCase.id} - ${testCase.description}`);
    const result = await runCase(testCase);
    caseResults.push(result);

    const marker = result.status === 'passed' ? 'PASS' : result.status === 'failed' ? 'FAIL' : 'SKIP';
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

    if (failFast && result.status === 'failed') {
      console.log(`[${provider}] fail-fast enabled, stop remaining cases.`);
      break;
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
