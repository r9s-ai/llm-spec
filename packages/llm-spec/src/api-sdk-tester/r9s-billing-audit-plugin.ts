import { request as httpRequest } from 'node:http';
import { request as httpsRequest } from 'node:https';

import type {
  HttpTraceExchange,
  PluginCaseCompleteContext,
  R9SBillingAuditConfig,
  R9SBillingAuditLocalRecord,
  R9SBillingAuditModelComparison,
  R9SBillingAuditRemoteRecord,
  R9SBillingAuditReport,
  R9SBillingAuditUsageSummary,
  R9SBillingAuditUsageTotals,
  TestLifecyclePlugin,
} from '../types';

type JsonRecord = Record<string, unknown>;
type UsageMetricKey = 'inputTokens' | 'outputTokens' | 'cachedTokens' | 'totalTokens';

const DEFAULT_MANAGER_BASE_URL = 'https://portal-api.r9s.ai';
const USAGE_PATH = '/api/v1/portal/management/usage';
const PAGE_SIZE = 100;
const MAX_PAGES = 100;
const MAX_BILLING_RESPONSE_BYTES = 32 * 1024 * 1024;
const BILLING_FETCH_DELAY_MS = 5_000;
const USAGE_METRIC_KEYS: readonly UsageMetricKey[] = [
  'inputTokens',
  'outputTokens',
  'cachedTokens',
  'totalTokens',
];
const COMPARED_USAGE_METRIC_KEYS: readonly UsageMetricKey[] = [
  'inputTokens',
  'outputTokens',
  'cachedTokens',
];
const USAGE_METRIC_LABELS: Record<UsageMetricKey, string> = {
  inputTokens: 'input tokens',
  outputTokens: 'output tokens',
  cachedTokens: 'cached tokens',
  totalTokens: 'total tokens',
};

interface ExtractedUsage {
  model?: string;
  usage: R9SBillingAuditUsageTotals;
}

interface BillingFetchResult {
  endpoint: string;
  totalAvailable: number;
  records: R9SBillingAuditRemoteRecord[];
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function optionalNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function numberValue(value: unknown): number {
  return optionalNumber(value) ?? 0;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function emptyUsageTotals(): R9SBillingAuditUsageTotals {
  return {};
}

function zeroUsageTotals(): R9SBillingAuditUsageTotals {
  return {
    inputTokens: 0,
    outputTokens: 0,
    cachedTokens: 0,
    totalTokens: 0,
    amount: 0,
    totalAmount: 0,
  };
}

function setNumberIfDefined(
  target: R9SBillingAuditUsageTotals,
  key: UsageMetricKey | 'amount' | 'totalAmount',
  value: number | undefined,
): void {
  if (value !== undefined) {
    target[key] = value;
  }
}

function firstNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    const number = optionalNumber(value);
    if (number !== undefined) {
      return number;
    }
  }
  return undefined;
}

function sumIfAllKnown(...values: Array<number | undefined>): number | undefined {
  if (values.some((value) => value === undefined)) {
    return undefined;
  }
  let total = 0;
  for (const value of values) {
    total += value ?? 0;
  }
  return total;
}

function hasAnyUsageMetric(value: R9SBillingAuditUsageTotals): boolean {
  return USAGE_METRIC_KEYS.some((key) => value[key] !== undefined);
}

function cloneUsageTotals(value: R9SBillingAuditUsageTotals): R9SBillingAuditUsageTotals {
  const next: R9SBillingAuditUsageTotals = {};
  for (const key of USAGE_METRIC_KEYS) {
    setNumberIfDefined(next, key, value[key]);
  }
  if (value.amount !== undefined) {
    next.amount = value.amount;
  }
  if (value.totalAmount !== undefined) {
    next.totalAmount = value.totalAmount;
  }
  return next;
}

function addUsageTotals(target: R9SBillingAuditUsageTotals, value: R9SBillingAuditUsageTotals): void {
  for (const key of USAGE_METRIC_KEYS) {
    if (target[key] === undefined || value[key] === undefined) {
      target[key] = undefined;
    } else {
      target[key] += value[key];
    }
  }
  for (const key of ['amount', 'totalAmount'] as const) {
    if (target[key] === undefined || value[key] === undefined) {
      target[key] = undefined;
    } else {
      target[key] += value[key];
    }
  }
}

function diffNumber(remote: number | undefined, local: number | undefined): number | undefined {
  return remote !== undefined && local !== undefined ? remote - local : undefined;
}

function diffUsageTotals(
  remote: R9SBillingAuditUsageTotals,
  local: R9SBillingAuditUsageTotals,
): R9SBillingAuditUsageTotals {
  const diff: R9SBillingAuditUsageTotals = {
    inputTokens: diffNumber(remote.inputTokens, local.inputTokens),
    outputTokens: diffNumber(remote.outputTokens, local.outputTokens),
    cachedTokens: diffNumber(remote.cachedTokens, local.cachedTokens),
    totalTokens: diffNumber(remote.totalTokens, local.totalTokens),
  };
  setNumberIfDefined(diff, 'amount', diffNumber(remote.amount, local.amount));
  setNumberIfDefined(diff, 'totalAmount', diffNumber(remote.totalAmount, local.totalAmount));
  return diff;
}

function usageDiffMatched(diff: R9SBillingAuditUsageTotals): boolean {
  return COMPARED_USAGE_METRIC_KEYS.every((key) => diff[key] === 0);
}

function formatUsageNumber(value: number | undefined): string {
  return value === undefined ? 'not fetched' : String(value);
}

function summarizeUsage<T extends { model: string; usage: R9SBillingAuditUsageTotals }>(
  records: readonly T[],
): R9SBillingAuditUsageSummary {
  const totals = records.length > 0 ? zeroUsageTotals() : emptyUsageTotals();
  const byModel = new Map<string, R9SBillingAuditUsageTotals>();

  for (const record of records) {
    addUsageTotals(totals, record.usage);
    const modelTotals = byModel.get(record.model) ?? zeroUsageTotals();
    addUsageTotals(modelTotals, record.usage);
    byModel.set(record.model, modelTotals);
  }

  return {
    recordCount: records.length,
    totals,
    byModel: Object.fromEntries(
      Array.from(byModel.entries()).sort(([left], [right]) => left.localeCompare(right)),
    ),
  };
}

function compareUsageByModel(
  local: R9SBillingAuditUsageSummary,
  remote: R9SBillingAuditUsageSummary,
): R9SBillingAuditModelComparison[] {
  const models = new Set([
    ...Object.keys(local.byModel),
    ...Object.keys(remote.byModel),
  ]);

  return Array.from(models)
    .sort((left, right) => left.localeCompare(right))
    .map((model) => {
      const localTotals = cloneUsageTotals(local.byModel[model] ?? emptyUsageTotals());
      const remoteTotals = cloneUsageTotals(remote.byModel[model] ?? emptyUsageTotals());
      const diff = diffUsageTotals(remoteTotals, localTotals);
      return {
        model,
        matched: usageDiffMatched(diff),
        local: localTotals,
        remote: remoteTotals,
        diff,
      };
    });
}

function parseJsonPayloads(body: string | undefined): JsonRecord[] {
  if (!body?.trim()) {
    return [];
  }

  const payloads: JsonRecord[] = [];
  const trimmed = body.trim();
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (isRecord(parsed)) {
      return [parsed];
    }
    if (Array.isArray(parsed)) {
      return parsed.filter(isRecord);
    }
  } catch {
    // Fall through to SSE / line-delimited parsing.
  }

  for (const rawLine of trimmed.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith(':') || line.startsWith('event:')) {
      continue;
    }
    const data = line.startsWith('data:') ? line.slice(5).trim() : line;
    if (!data || data === '[DONE]') {
      continue;
    }
    try {
      const parsed = JSON.parse(data) as unknown;
      if (isRecord(parsed)) {
        payloads.push(parsed);
      }
    } catch {
      // Ignore non-JSON stream fragments.
    }
  }

  return payloads;
}

function modelFromPayload(payload: JsonRecord): string | undefined {
  const response = isRecord(payload.response) ? payload.response : undefined;
  const message = isRecord(payload.message) ? payload.message : undefined;
  return optionalString(payload.model) ?? optionalString(response?.model) ?? optionalString(message?.model);
}

function usageFromOpenAIUsage(usage: JsonRecord): R9SBillingAuditUsageTotals | undefined {
  const inputTokens = firstNumber(usage.prompt_tokens, usage.input_tokens);
  const outputTokens = firstNumber(usage.completion_tokens, usage.output_tokens);
  const promptDetails = isRecord(usage.prompt_tokens_details) ? usage.prompt_tokens_details : undefined;
  const inputDetails = isRecord(usage.input_tokens_details) ? usage.input_tokens_details : undefined;
  const cachedTokens = firstNumber(promptDetails?.cached_tokens, inputDetails?.cached_tokens);
  const totalTokens = firstNumber(usage.total_tokens) ?? sumIfAllKnown(inputTokens, outputTokens);
  const result: R9SBillingAuditUsageTotals = {};
  setNumberIfDefined(result, 'inputTokens', inputTokens);
  setNumberIfDefined(result, 'outputTokens', outputTokens);
  setNumberIfDefined(result, 'cachedTokens', cachedTokens);
  setNumberIfDefined(result, 'totalTokens', totalTokens);
  return hasAnyUsageMetric(result) ? result : undefined;
}

function usageFromAnthropicUsage(usage: JsonRecord): R9SBillingAuditUsageTotals | undefined {
  const rawInputTokens = firstNumber(usage.input_tokens);
  const cacheCreationTokens = firstNumber(usage.cache_creation_input_tokens);
  const cachedTokens = firstNumber(usage.cache_read_input_tokens);
  const inputTokens =
    rawInputTokens === undefined && cacheCreationTokens === undefined
      ? undefined
      : (rawInputTokens ?? 0) + (cacheCreationTokens ?? 0);
  const outputTokens = firstNumber(usage.output_tokens);
  const totalTokens = sumIfAllKnown(inputTokens, outputTokens, cachedTokens);
  const result: R9SBillingAuditUsageTotals = {};
  setNumberIfDefined(result, 'inputTokens', inputTokens);
  setNumberIfDefined(result, 'outputTokens', outputTokens);
  setNumberIfDefined(result, 'cachedTokens', cachedTokens);
  setNumberIfDefined(result, 'totalTokens', totalTokens);
  return hasAnyUsageMetric(result) ? result : undefined;
}

function usageFromGeminiMetadata(usage: JsonRecord): R9SBillingAuditUsageTotals | undefined {
  const promptTokens = firstNumber(usage.promptTokenCount);
  const toolUsePromptTokens = firstNumber(usage.toolUsePromptTokenCount);
  const inputTokens =
    promptTokens === undefined && toolUsePromptTokens === undefined
      ? undefined
      : (promptTokens ?? 0) + (toolUsePromptTokens ?? 0);
  const candidateTokens = firstNumber(usage.candidatesTokenCount);
  const thoughtTokens = firstNumber(usage.thoughtsTokenCount);
  const outputTokens =
    candidateTokens === undefined && thoughtTokens === undefined
      ? undefined
      : (candidateTokens ?? 0) + (thoughtTokens ?? 0);
  const cachedTokens = firstNumber(usage.cachedContentTokenCount);
  const totalTokens = firstNumber(usage.totalTokenCount) ?? sumIfAllKnown(inputTokens, outputTokens, cachedTokens);
  const result: R9SBillingAuditUsageTotals = {};
  setNumberIfDefined(result, 'inputTokens', inputTokens);
  setNumberIfDefined(result, 'outputTokens', outputTokens);
  setNumberIfDefined(result, 'cachedTokens', cachedTokens);
  setNumberIfDefined(result, 'totalTokens', totalTokens);
  return hasAnyUsageMetric(result) ? result : undefined;
}

function maxAnthropicStreamUsage(payloads: readonly JsonRecord[]): JsonRecord | undefined {
  const aggregate: JsonRecord = {};
  let hasUsage = false;

  for (const payload of payloads) {
    const message = isRecord(payload.message) ? payload.message : undefined;
    const usage = isRecord(payload.usage)
      ? payload.usage
      : isRecord(message?.usage)
        ? message.usage
        : undefined;
    if (!usage) {
      continue;
    }

    hasUsage = true;
    for (const key of [
      'input_tokens',
      'output_tokens',
      'cache_creation_input_tokens',
      'cache_read_input_tokens',
    ]) {
      aggregate[key] = Math.max(numberValue(aggregate[key]), numberValue(usage[key]));
    }
  }

  return hasUsage ? aggregate : undefined;
}

function extractUsage(payloads: readonly JsonRecord[], provider: string): ExtractedUsage | undefined {
  if (payloads.length === 0) {
    return undefined;
  }

  const lowerProvider = provider.toLowerCase();
  const reversedPayloads = [...payloads].reverse();
  const model = reversedPayloads.map(modelFromPayload).find((value): value is string => Boolean(value));

  if (lowerProvider.includes('gemini')) {
    const geminiPayload = reversedPayloads.find((payload) => isRecord(payload.usageMetadata));
    const usage = isRecord(geminiPayload?.usageMetadata) ? geminiPayload.usageMetadata : undefined;
    const totals = usage ? usageFromGeminiMetadata(usage) : undefined;
    return totals ? { model, usage: totals } : undefined;
  }

  if (lowerProvider.includes('anthropic') || lowerProvider.includes('claude-agent')) {
    const directPayload = reversedPayloads.find((payload) => isRecord(payload.usage) || isRecord(payload.message));
    const message = isRecord(directPayload?.message) ? directPayload.message : undefined;
    const directUsage = isRecord(directPayload?.usage)
      ? directPayload.usage
      : isRecord(message?.usage)
        ? message.usage
        : undefined;
    const usage = directUsage ?? maxAnthropicStreamUsage(payloads);
    const totals = usage ? usageFromAnthropicUsage(usage) : undefined;
    return totals ? { model, usage: totals } : undefined;
  }

  const openAiPayload = reversedPayloads.find((payload) => isRecord(payload.usage));
  const usage = isRecord(openAiPayload?.usage) ? openAiPayload.usage : undefined;
  const totals = usage ? usageFromOpenAIUsage(usage) : undefined;
  return totals ? { model, usage: totals } : undefined;
}

function extractExchangeUsage(
  context: PluginCaseCompleteContext,
  exchange: HttpTraceExchange,
): R9SBillingAuditLocalRecord | undefined {
  if (!exchange.response?.body) {
    return undefined;
  }

  const usage = extractUsage(parseJsonPayloads(exchange.response.body), context.provider);
  if (!usage) {
    return undefined;
  }

  return {
    provider: context.provider,
    model: usage.model ?? context.model,
    apiBaseUrl: context.apiBaseUrl,
    caseId: context.id,
    name: context.name,
    description: context.description,
    requestId: exchange.request.requestId ?? exchange.response.requestId,
    usage: usage.usage,
  };
}

function resolveUsageEndpoint(managerBaseUrl: string | undefined): string {
  const rawBaseUrl = (managerBaseUrl?.trim() || DEFAULT_MANAGER_BASE_URL).replace(/\/+$/, '');
  const url = new URL(rawBaseUrl);
  if (url.pathname.endsWith('/management/usage')) {
    return url.toString();
  }
  if (url.pathname.endsWith('/api/v1/portal')) {
    url.pathname = `${url.pathname}/management/usage`;
    return url.toString();
  }
  url.pathname = `${url.pathname.replace(/\/+$/, '')}${USAGE_PATH}`;
  return url.toString();
}

function unixSeconds(isoTimestamp: string, round: 'floor' | 'ceil'): number {
  const timestamp = Date.parse(isoTimestamp);
  if (!Number.isFinite(timestamp)) {
    return Math[round](Date.now() / 1000);
  }
  return Math[round](timestamp / 1000);
}

function redactSecret(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  if (value.length <= 8) {
    return `${value.slice(0, 2)}***`;
  }
  return `${value.slice(0, 4)}***${value.slice(-4)}`;
}

function formatError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function nestedRecord(value: JsonRecord, key: string): JsonRecord | undefined {
  return isRecord(value[key]) ? value[key] : undefined;
}

function numberFromRecords(records: readonly JsonRecord[], keys: readonly string[]): number | undefined {
  for (const record of records) {
    for (const key of keys) {
      const value = optionalNumber(record[key]);
      if (value !== undefined) {
        return value;
      }
    }
  }
  return undefined;
}

function normalizeBillingRecord(value: unknown): R9SBillingAuditRemoteRecord | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const usageRecord = nestedRecord(value, 'usage');
  const billingRecord = nestedRecord(value, 'billing');
  const tokenRecord = nestedRecord(value, 'tokens');
  const records = [value, usageRecord, billingRecord, tokenRecord].filter(isRecord);
  const model =
    optionalString(value.model) ??
    optionalString(value.model_name) ??
    optionalString(value.modelName);
  if (!model) {
    return undefined;
  }

  const inputTokens = numberFromRecords(records, [
    'input_token',
    'input_tokens',
    'inputToken',
    'inputTokens',
    'prompt_token',
    'prompt_tokens',
    'promptTokenCount',
  ]);
  const outputTokens = numberFromRecords(records, [
    'output_token',
    'output_tokens',
    'outputToken',
    'outputTokens',
    'completion_token',
    'completion_tokens',
    'candidatesTokenCount',
  ]);
  const cachedTokens = numberFromRecords(records, [
    'cached_token',
    'cached_tokens',
    'cachedToken',
    'cachedTokens',
    'cache_token',
    'cache_tokens',
    'cache_read_input_tokens',
    'cachedContentTokenCount',
  ]);
  const totalTokens =
    numberFromRecords(records, [
      'total_token',
      'total_tokens',
      'totalToken',
      'totalTokens',
      'totalTokenCount',
    ]) ?? sumIfAllKnown(inputTokens, outputTokens, cachedTokens);
  const amount = numberFromRecords(records, ['amount', 'cost']);
  const totalAmount = numberFromRecords(records, ['total_amount', 'totalAmount', 'total_cost', 'totalCost']);
  const usage: R9SBillingAuditUsageTotals = {};
  setNumberIfDefined(usage, 'inputTokens', inputTokens);
  setNumberIfDefined(usage, 'outputTokens', outputTokens);
  setNumberIfDefined(usage, 'cachedTokens', cachedTokens);
  setNumberIfDefined(usage, 'totalTokens', totalTokens);
  if (amount !== undefined) {
    usage.amount = amount;
  }
  if (totalAmount !== undefined) {
    usage.totalAmount = totalAmount;
  }

  const record: R9SBillingAuditRemoteRecord = {
    id: optionalString(value.id),
    requestTime: optionalNumber(value.request_time),
    userId: optionalString(value.user_id),
    customUserId: optionalString(value.custom_user_id),
    tokenId: optionalString(value.token_id),
    model,
    modelType: optionalString(value.model_type),
    usage,
  };
  if (value.ext !== undefined) {
    record.ext = value.ext;
  }
  return record;
}

function fetchBillingJson(url: URL, managerKey: string): Promise<unknown> {
  const request = url.protocol === 'http:'
    ? httpRequest
    : url.protocol === 'https:'
      ? httpsRequest
      : undefined;
  if (!request) {
    throw new Error(`Unsupported R9S manager URL protocol: ${url.protocol}`);
  }

  return new Promise((resolve, reject) => {
    const clientRequest = request(
      url,
      {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${managerKey}`,
        },
      },
      (response) => {
        const chunks: Buffer[] = [];
        let size = 0;

        response.on('data', (chunk: Buffer | string) => {
          const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
          size += buffer.byteLength;
          if (size > MAX_BILLING_RESPONSE_BYTES) {
            clientRequest.destroy(new Error('R9S usage query response is too large'));
            return;
          }
          chunks.push(buffer);
        });

        response.on('end', () => {
          const statusCode = response.statusCode ?? 0;
          const statusMessage = response.statusMessage ?? '';
          const body = Buffer.concat(chunks).toString('utf8');
          if (statusCode < 200 || statusCode >= 300) {
            reject(new Error(`R9S usage query failed: ${statusCode} ${statusMessage}`.trim()));
            return;
          }
          try {
            resolve(JSON.parse(body) as unknown);
          } catch {
            reject(new Error('R9S usage query returned invalid JSON'));
          }
        });
      },
    );

    clientRequest.on('error', reject);
    clientRequest.end();
  });
}

async function fetchBillingRecords(
  config: R9SBillingAuditConfig,
  startTime: number,
  endTime: number,
): Promise<BillingFetchResult> {
  const managerKey = config.managerKey?.trim();
  if (!managerKey) {
    throw new Error('R9S manager key is required for billing audit');
  }

  const endpoint = resolveUsageEndpoint(config.managerBaseUrl);
  const tokenFilter = config.tokenId?.trim();
  const records: R9SBillingAuditRemoteRecord[] = [];
  let totalAvailable = 0;

  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const url = new URL(endpoint);
    url.searchParams.set('start_time', String(startTime));
    url.searchParams.set('end_time', String(endTime));
    url.searchParams.set('page', String(page));
    url.searchParams.set('pagesize', String(PAGE_SIZE));
    if (tokenFilter) {
      url.searchParams.set('token_id', tokenFilter);
    }

    const payload = await fetchBillingJson(url, managerKey);
    if (!isRecord(payload)) {
      throw new Error('R9S usage query returned a non-object payload');
    }

    const meta = isRecord(payload.meta) ? payload.meta : undefined;
    const code = optionalNumber(meta?.code);
    if (code !== undefined && code !== 0) {
      throw new Error(`R9S usage query failed: ${optionalString(meta?.message) ?? `code ${code}`}`);
    }

    const data = isRecord(payload.data) ? payload.data : undefined;
    const list = Array.isArray(data?.list) ? data.list : [];
    totalAvailable = optionalNumber(data?.total) ?? Math.max(totalAvailable, records.length + list.length);

    for (const item of list) {
      const record = normalizeBillingRecord(item);
      if (record) {
        records.push(record);
      }
    }

    if (list.length < PAGE_SIZE || records.length >= totalAvailable) {
      break;
    }
  }

  return { endpoint, totalAvailable, records };
}

function createEmptyRemoteSummary(): R9SBillingAuditReport['remote'] {
  return {
    ...summarizeUsage<R9SBillingAuditRemoteRecord>([]),
    totalAvailable: 0,
    records: [],
  };
}

function createLocalSummary(records: readonly R9SBillingAuditLocalRecord[]): R9SBillingAuditReport['local'] {
  return {
    ...summarizeUsage(records),
    records: records.map((record) => ({
      ...record,
      usage: cloneUsageTotals(record.usage),
    })),
  };
}

function missingUsageFields(usage: R9SBillingAuditUsageTotals): string[] {
  return COMPARED_USAGE_METRIC_KEYS
    .filter((key) => usage[key] === undefined)
    .map((key) => USAGE_METRIC_LABELS[key]);
}

function recordIdentifier(record: {
  model: string;
  id?: string;
  requestId?: string;
  caseId?: string;
}): string {
  return record.id ?? record.requestId ?? record.caseId ?? record.model;
}

function appendMissingUsageWarnings(
  warnings: string[],
  label: string,
  records: ReadonlyArray<{
    model: string;
    id?: string;
    requestId?: string;
    caseId?: string;
    usage: R9SBillingAuditUsageTotals;
  }>,
): void {
  const missing = records
    .map((record) => ({ record, fields: missingUsageFields(record.usage) }))
    .filter((item) => item.fields.length > 0);
  if (missing.length === 0) {
    return;
  }

  const examples = missing
    .slice(0, 3)
    .map(({ record, fields }) => `${recordIdentifier(record)} (${fields.join(', ')})`)
    .join('; ');
  const suffix = missing.length > 3 ? `; +${missing.length - 3} more` : '';
  warnings.push(`${label} usage was not fetched for ${missing.length} record(s): ${examples}${suffix}.`);
}

function buildWarnings(
  config: R9SBillingAuditConfig,
  localRecords: readonly R9SBillingAuditLocalRecord[],
  remoteRecords: readonly R9SBillingAuditRemoteRecord[],
): string[] {
  const warnings: string[] = [];
  if (localRecords.length === 0) {
    warnings.push('No local usage records were found in response traces.');
  }
  if (remoteRecords.length === 0) {
    warnings.push('No R9S billing records were returned for the queried window.');
  }
  if (!config.tokenId && config.apiKey) {
    warnings.push('R9S usage query did not include a token_id filter. Set billingAudit.tokenId or R9S_TOKEN_ID to scope by API key id.');
  }
  if (!config.tokenId && !config.apiKey) {
    warnings.push('R9S usage query did not include a token_id filter because no API key was configured.');
  }
  appendMissingUsageWarnings(warnings, 'Local trace', localRecords);
  appendMissingUsageWarnings(warnings, 'R9S billing', remoteRecords);
  return warnings;
}

function reportStatus(
  comparisons: readonly R9SBillingAuditModelComparison[],
  warnings: readonly string[],
): R9SBillingAuditReport['status'] {
  if (comparisons.some((comparison) => !comparison.matched)) {
    return 'mismatched';
  }
  if (warnings.length > 0) {
    return 'warning';
  }
  return 'passed';
}

function logAuditReport(report: R9SBillingAuditReport): void {
  console.log('\n============================================================');
  console.log('R9S Billing Audit');
  console.log('============================================================');
  console.log(`status: ${report.status}`);
  if (report.error) {
    console.log(`error: ${report.error}`);
  }
  console.log(`query: ${report.query.endpoint}`);
  console.log(`window: ${report.query.startTime} - ${report.query.endTime}`);
  console.log(`local records: ${report.local.recordCount}`);
  console.log(`billing records: ${report.remote.recordCount}/${report.remote.totalAvailable}`);
  for (const comparison of report.comparisons) {
    console.log(
      [
        `model=${comparison.model}`,
        `inputDiff=${formatUsageNumber(comparison.diff.inputTokens)}`,
        `outputDiff=${formatUsageNumber(comparison.diff.outputTokens)}`,
        `cachedDiff=${formatUsageNumber(comparison.diff.cachedTokens)}`,
      ].join(' '),
    );
  }
  for (const warning of report.warnings) {
    console.log(`warning: ${warning}`);
  }
}

export function createR9SBillingAuditPlugin(config: R9SBillingAuditConfig | undefined): TestLifecyclePlugin | undefined {
  if (!config?.enabled) {
    return undefined;
  }

  const localRecords: R9SBillingAuditLocalRecord[] = [];

  return {
    name: 'r9s-billing-audit',
    afterCase(context) {
      for (const exchange of context.exchanges) {
        const record = extractExchangeUsage(context, exchange);
        if (record) {
          localRecords.push(record);
        }
      }
    },
    async afterRun({ summary }) {
      const startTime = unixSeconds(summary.startedAt, 'floor');
      const endTime = unixSeconds(summary.finishedAt, 'ceil');
      const local = createLocalSummary(localRecords);
      const tokenFilter = config.tokenId?.trim();
      let remote = createEmptyRemoteSummary();
      let endpoint = resolveUsageEndpoint(config.managerBaseUrl);
      let comparisons: R9SBillingAuditModelComparison[] = [];
      let warnings: string[] = [];
      let error: string | undefined;

      try {
        console.log(`waiting ${BILLING_FETCH_DELAY_MS}ms before querying R9S usage...`);
        await delay(BILLING_FETCH_DELAY_MS);
        const fetched = await fetchBillingRecords(config, startTime, endTime);
        endpoint = fetched.endpoint;
        const remoteSummary = summarizeUsage(fetched.records);
        remote = {
          ...remoteSummary,
          totalAvailable: fetched.totalAvailable,
          records: fetched.records,
        };
        comparisons = compareUsageByModel(local, remote);
        warnings = buildWarnings(config, localRecords, fetched.records);
      } catch (auditError: unknown) {
        error = formatError(auditError);
        warnings = buildWarnings(config, localRecords, []);
      }

      const report: R9SBillingAuditReport = {
        status: error ? 'error' : reportStatus(comparisons, warnings),
        startedAt: summary.startedAt,
        finishedAt: summary.finishedAt,
        query: {
          endpoint,
          startTime,
          endTime,
          pageSize: PAGE_SIZE,
          tokenId: tokenFilter ? redactSecret(tokenFilter) : undefined,
          apiKeyFingerprint: redactSecret(config.apiKey),
        },
        local,
        remote,
        comparisons,
        warnings,
        error,
      };

      summary.billingAudit = report;
      logAuditReport(report);
    },
  };
}
