import type { ProviderSummary, TestCaseResult } from '../../types';
import { applyCaseFilter } from '../environment/case-filter';
import { consumeCapturedHttpTrace, flushCapturedHttpTrace, runWithActiveTestContext } from '../environment';
import type { TestCase } from './types';

let providerCaseExecutionCounter = 0;

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

function sanitizeCaseIdPart(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]+/g, '_');
}

function createCaseExecutionTestId(provider: string, caseId: string): string {
  providerCaseExecutionCounter += 1;
  return `${sanitizeCaseIdPart(provider)}-${sanitizeCaseIdPart(caseId)}-${Date.now()}-${providerCaseExecutionCounter}`;
}

async function collectCaseHttpTrace(testId: string): Promise<TestCaseResult['httpTrace']> {
  await flushCapturedHttpTrace(testId);
  return consumeCapturedHttpTrace(testId);
}

async function runCase(provider: string, testCase: TestCase): Promise<TestCaseResult> {
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
      protocol: testCase.protocol,
      modelScope: testCase.modelScope,
    };
  }

  const testId = createCaseExecutionTestId(provider, testCase.id);

  try {
    const detail = await runWithActiveTestContext({ provider, testId }, () => testCase.run());
    const httpTrace = await collectCaseHttpTrace(testId);
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'passed',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      detail,
      apiType: testCase.apiType,
      protocol: testCase.protocol,
      modelScope: testCase.modelScope,
      httpTrace,
    };
  } catch (error) {
    const httpTrace = await collectCaseHttpTrace(testId);
    return {
      id: testCase.id,
      description: testCase.description,
      status: 'failed',
      durationMs: Date.now() - started,
      coveredParams: [...testCase.covers],
      error: formatError(error),
      apiType: testCase.apiType,
      protocol: testCase.protocol,
      modelScope: testCase.modelScope,
      httpTrace,
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
    setupDetail: reason,
    startedAt: now,
    finishedAt: now,
    passed: 0,
    failed: 0,
    skipped: 1,
    caseResults: [],
    allParams: [...allParams],
    coveredParams: [],
    untestedParams: [...allParams],
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
    for (const testCase of filteredCases) {
      console.log(`[${provider}] running ${testCase.id} - ${testCase.description}`);
      const result = await runCase(provider, testCase);
      caseResults.push(result);

      logCaseResult(provider, result);

      if (failFast && result.status === 'failed') {
        console.log(`[${provider}] fail-fast enabled, stop remaining cases.`);
        break;
      }
    }
  } else {
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
        const result = await runCase(provider, testCase);
        caseResults[index] = result;

        logCaseResult(provider, result);

        if (failFast && result.status === 'failed') {
          stopped = true;
          console.log(`[${provider}] fail-fast enabled, stop remaining cases.`);
        }
      }
    };

    const placeholders = filteredCases.map(() => null);
    caseResults.push(...(placeholders as unknown as TestCaseResult[]));

    const workerCount = Math.min(concurrency, filteredCases.length);
    await Promise.all(Array.from({ length: workerCount }, () => worker()));

    for (let index = caseResults.length - 1; index >= 0; index--) {
      if (caseResults[index] === null) {
        caseResults.splice(index, 1);
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
