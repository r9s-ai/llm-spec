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
  R9SBillingAuditToolCallCounts,
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
const BILLING_FETCH_DELAY_MS = 10_000;
const R9S_BILLING_ID_MODULUS = 9_223_372_036_854_775_808n;
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
const RESPONSE_ID_HEADER_NAME = 'x-request-id';

interface ExtractedUsage {
  model?: string;
  usage: R9SBillingAuditUsageTotals;
}

interface BillingFetchResult {
  endpoint: string;
  totalAvailable: number;
  records: R9SBillingAuditRemoteRecord[];
}

interface GroupableBillingRecord {
  id?: string;
  requestId?: string;
  caseId?: string;
  responseId?: string;
  model: string;
  usage: R9SBillingAuditUsageTotals;
  toolCalls?: R9SBillingAuditToolCallCounts;
}

interface ResponseUsageGroup<T extends GroupableBillingRecord> {
  responseId?: string;
  models: Set<string>;
  records: T[];
  usage: R9SBillingAuditUsageTotals;
  toolCalls: R9SBillingAuditToolCallCounts;
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

function optionalRecord(value: unknown): JsonRecord | undefined {
  if (isRecord(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value) as unknown;
      return isRecord(parsed) ? parsed : undefined;
    } catch {
      return undefined;
    }
  }
  return undefined;
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

function addToolCallCount(target: R9SBillingAuditToolCallCounts, toolName: string | undefined, count: number | undefined): void {
  const normalizedToolName = toolName?.trim();
  if (
    !normalizedToolName ||
    isIgnoredToolCallMetricKey(normalizedToolName) ||
    count === undefined ||
    !Number.isFinite(count) ||
    count === 0
  ) {
    return;
  }
  target[normalizedToolName] = (target[normalizedToolName] ?? 0) + count;
}

function mergeToolCallCounts(
  target: R9SBillingAuditToolCallCounts,
  value: R9SBillingAuditToolCallCounts | undefined,
): void {
  for (const [toolName, count] of Object.entries(value ?? {})) {
    addToolCallCount(target, toolName, count);
  }
}

function cloneToolCallCounts(value: R9SBillingAuditToolCallCounts | undefined): R9SBillingAuditToolCallCounts | undefined {
  const entries = Object.entries(value ?? {})
    .filter(([toolName, count]) => !isIgnoredToolCallMetricKey(toolName) && Number.isFinite(count) && count !== 0)
    .sort(([left], [right]) => left.localeCompare(right));
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}

function diffToolCallCounts(
  remote: R9SBillingAuditToolCallCounts | undefined,
  local: R9SBillingAuditToolCallCounts | undefined,
): R9SBillingAuditToolCallCounts | undefined {
  const normalizedRemote = cloneToolCallCounts(remote) ?? {};
  const normalizedLocal = cloneToolCallCounts(local) ?? {};
  const toolNames = new Set([
    ...Object.keys(normalizedRemote),
    ...Object.keys(normalizedLocal),
  ]);
  const diff: R9SBillingAuditToolCallCounts = {};
  for (const toolName of toolNames) {
    const value = (normalizedRemote[toolName] ?? 0) - (normalizedLocal[toolName] ?? 0);
    if (value !== 0) {
      diff[toolName] = value;
    }
  }
  return cloneToolCallCounts(diff);
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

function toolCallDiffMatched(diff: R9SBillingAuditToolCallCounts | undefined): boolean {
  return Object.keys(diff ?? {}).length === 0;
}

function formatUsageNumber(value: number | undefined): string {
  return value === undefined ? 'not fetched' : String(value);
}

function formatComparisonModels(
  comparison: R9SBillingAuditModelComparison,
  side: 'local' | 'remote',
): string {
  const models = side === 'local' ? comparison.localModels : comparison.remoteModels;
  if (models && models.length > 0) {
    return models.join(',');
  }
  return hasAnyUsageMetric(side === 'local' ? comparison.local : comparison.remote)
    ? comparison.model
    : 'not found';
}

function formatComparisonResponseId(comparison: R9SBillingAuditModelComparison): string {
  return comparison.responseId ?? 'not found';
}

function formatToolCallCountNumber(value: number, signed: boolean): string {
  if (!signed) {
    return String(value);
  }
  return value > 0 ? `+${String(value)}` : String(value);
}

function formatToolCallCounts(
  toolCalls: R9SBillingAuditToolCallCounts | undefined,
  options: { signed?: boolean } = {},
): string {
  const entries = Object.entries(toolCalls ?? {})
    .filter(([toolName, count]) => !isIgnoredToolCallMetricKey(toolName) && Number.isFinite(count) && count !== 0)
    .sort(([left], [right]) => left.localeCompare(right));
  return entries.length > 0
    ? entries.map(([toolName, count]) => `${toolName}:${formatToolCallCountNumber(count, options.signed === true)}`).join(',')
    : 'none';
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

function sortedModelList(group: ResponseUsageGroup<GroupableBillingRecord> | undefined): string[] | undefined {
  if (!group || group.models.size === 0) {
    return undefined;
  }
  return Array.from(group.models).sort((left, right) => left.localeCompare(right));
}

function billingRecordFallbackKey(record: GroupableBillingRecord, index: number, side: 'local' | 'remote'): string {
  return `${side}:${record.id ?? record.requestId ?? record.caseId ?? record.model}:${index}`;
}

function groupUsageByResponseId<T extends GroupableBillingRecord>(
  records: readonly T[],
  side: 'local' | 'remote',
): Map<string, ResponseUsageGroup<T>> {
  const groups = new Map<string, ResponseUsageGroup<T>>();

  records.forEach((record, index) => {
    const responseId = record.responseId?.trim();
    const key = responseId ? `response:${responseId}` : billingRecordFallbackKey(record, index, side);
    const group = groups.get(key) ?? {
      responseId,
      models: new Set<string>(),
      records: [],
      usage: zeroUsageTotals(),
      toolCalls: {},
    };
    group.models.add(record.model);
    group.records.push(record);
    addUsageTotals(group.usage, record.usage);
    mergeToolCallCounts(group.toolCalls, record.toolCalls);
    groups.set(key, group);
  });

  return groups;
}

function comparisonModel(
  localGroup: ResponseUsageGroup<R9SBillingAuditLocalRecord> | undefined,
  remoteGroup: ResponseUsageGroup<R9SBillingAuditRemoteRecord> | undefined,
  responseId: string | undefined,
): string {
  const localModels = sortedModelList(localGroup);
  const remoteModels = sortedModelList(remoteGroup);
  return localModels?.[0] ?? remoteModels?.[0] ?? responseId ?? 'unknown';
}

function compareUsageByResponseId(
  localRecords: readonly R9SBillingAuditLocalRecord[],
  remoteRecords: readonly R9SBillingAuditRemoteRecord[],
): R9SBillingAuditModelComparison[] {
  const localGroups = groupUsageByResponseId(localRecords, 'local');
  const remoteGroups = groupUsageByResponseId(remoteRecords, 'remote');
  const keys = new Set(localGroups.keys());

  return Array.from(keys)
    .sort((left, right) => {
      const leftResponseId = localGroups.get(left)?.responseId ?? remoteGroups.get(left)?.responseId ?? left;
      const rightResponseId = localGroups.get(right)?.responseId ?? remoteGroups.get(right)?.responseId ?? right;
      return leftResponseId.localeCompare(rightResponseId);
    })
    .map((key) => {
      const localGroup = localGroups.get(key);
      const remoteGroup = remoteGroups.get(key);
      const responseId = localGroup?.responseId ?? remoteGroup?.responseId;
      const localTotals = cloneUsageTotals(localGroup?.usage ?? emptyUsageTotals());
      const remoteTotals = cloneUsageTotals(remoteGroup?.usage ?? emptyUsageTotals());
      const diff = diffUsageTotals(remoteTotals, localTotals);
      const localToolCalls = cloneToolCallCounts(localGroup?.toolCalls);
      const remoteToolCalls = cloneToolCallCounts(remoteGroup?.toolCalls);
      const toolCallDiff = diffToolCallCounts(remoteToolCalls, localToolCalls);
      return {
        responseId,
        model: comparisonModel(localGroup, remoteGroup, responseId),
        localModels: sortedModelList(localGroup),
        remoteModels: sortedModelList(remoteGroup),
        matched: usageDiffMatched(diff) && toolCallDiffMatched(toolCallDiff),
        local: localTotals,
        remote: remoteTotals,
        diff,
        localToolCalls,
        remoteToolCalls,
        toolCallDiff,
        toolCalls: remoteToolCalls,
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

function recordArray(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function explicitToolNameFromRecord(record: JsonRecord): string | undefined {
  return optionalString(record.name)
    ?? optionalString(record.tool_name)
    ?? optionalString(record.toolName)
    ?? optionalString(record.function_name)
    ?? optionalString(record.functionName)
    ?? optionalString(nestedOptionalRecord(record, 'function')?.name)
    ?? optionalString(nestedOptionalRecord(record, 'tool')?.name)
    ?? optionalString(record.tool);
}

function localToolNameFromRecord(
  record: JsonRecord,
  fallbackName?: string,
  options: { allowTypeFallback?: boolean } = {},
): string | undefined {
  const explicitName = explicitToolNameFromRecord(record);
  const fallbackType = options.allowTypeFallback ? optionalString(record.type) : undefined;
  return toolNameFromKey(explicitName)
    ?? toolNameFromKey(fallbackName)
    ?? toolNameFromKey(fallbackType);
}

function localToolCallIdentity(
  source: string,
  record: JsonRecord,
  fallbackKey: string,
  toolName: string,
): string {
  const stableId = optionalString(record.id)
    ?? optionalString(record.call_id)
    ?? optionalString(record.callId);
  if (stableId) {
    return `stable:${stableId}:${toolName}`;
  }
  const index = optionalNumber(record.index);
  return `${source}:${index !== undefined ? `index:${String(index)}` : fallbackKey}:${toolName}`;
}

function addLocalToolCall(
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
  source: string,
  record: JsonRecord,
  fallbackKey: string,
  fallbackName?: string,
  options: { allowTypeFallback?: boolean } = {},
): void {
  const toolName = localToolNameFromRecord(record, fallbackName, options);
  if (!toolName) {
    return;
  }
  const identity = localToolCallIdentity(source, record, fallbackKey, toolName);
  if (seen.has(identity)) {
    return;
  }
  seen.add(identity);
  addToolCallCount(target, toolName, 1);
}

function collectOpenAIChatToolCallsFromMessage(
  message: JsonRecord,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
  source: string,
): void {
  recordArray(message.tool_calls).forEach((toolCall, index) => {
    addLocalToolCall(target, seen, source, toolCall, `tool_calls:${String(index)}`, undefined, {
      allowTypeFallback: false,
    });
  });

  const functionCall = optionalRecord(message.function_call);
  if (functionCall) {
    addLocalToolCall(target, seen, source, functionCall, 'function_call', undefined, {
      allowTypeFallback: false,
    });
  }
}

function collectOpenAIChatToolCalls(
  payload: JsonRecord,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
): void {
  recordArray(payload.choices).forEach((choice, choiceIndex) => {
    const choiceKey = optionalNumber(choice.index) ?? choiceIndex;
    const message = optionalRecord(choice.message);
    if (message) {
      collectOpenAIChatToolCallsFromMessage(message, target, seen, `chat:message:${String(choiceKey)}`);
    }
    const delta = optionalRecord(choice.delta);
    if (delta) {
      collectOpenAIChatToolCallsFromMessage(delta, target, seen, `chat:delta:${String(choiceKey)}`);
    }
  });
}

function isResponsesToolCallRecord(record: JsonRecord): boolean {
  const type = optionalString(record.type);
  if (!type) {
    return false;
  }
  const normalized = toSnakeCase(type);
  return normalized === 'tool_call'
    || normalized === 'function_call'
    || normalized.endsWith('_call');
}

function collectResponsesOutputItems(
  value: unknown,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
  source: string,
): void {
  recordArray(value).forEach((item, index) => {
    if (!isResponsesToolCallRecord(item)) {
      return;
    }
    addLocalToolCall(target, seen, source, item, `output:${String(index)}`, undefined, {
      allowTypeFallback: true,
    });
  });
}

function collectOpenAIResponsesToolCalls(
  payload: JsonRecord,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
): void {
  collectResponsesOutputItems(payload.output, target, seen, 'responses:output');
  const response = optionalRecord(payload.response);
  if (response) {
    collectResponsesOutputItems(response.output, target, seen, 'responses:response.output');
  }

  const item = optionalRecord(payload.item);
  if (item && isResponsesToolCallRecord(item)) {
    addLocalToolCall(target, seen, 'responses:item', item, 'item', undefined, {
      allowTypeFallback: true,
    });
  }

  if (isResponsesToolCallRecord(payload)) {
    addLocalToolCall(target, seen, 'responses:payload', payload, 'payload', undefined, {
      allowTypeFallback: true,
    });
  }
}

function isAnthropicToolUseRecord(record: JsonRecord): boolean {
  return toSnakeCase(optionalString(record.type) ?? '') === 'tool_use';
}

function collectAnthropicContentBlocks(
  value: unknown,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
  source: string,
): void {
  recordArray(value).forEach((block, index) => {
    if (!isAnthropicToolUseRecord(block)) {
      return;
    }
    addLocalToolCall(target, seen, source, block, `content:${String(index)}`, undefined, {
      allowTypeFallback: true,
    });
  });
}

function collectAnthropicMessagesToolCalls(
  payload: JsonRecord,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
): void {
  collectAnthropicContentBlocks(payload.content, target, seen, 'anthropic:content');
  const message = optionalRecord(payload.message);
  if (message) {
    collectAnthropicContentBlocks(message.content, target, seen, 'anthropic:message.content');
  }

  const contentBlock = optionalRecord(payload.content_block);
  if (contentBlock && isAnthropicToolUseRecord(contentBlock)) {
    const index = optionalNumber(payload.index);
    addLocalToolCall(
      target,
      seen,
      'anthropic:content_block',
      contentBlock,
      index === undefined ? 'content_block' : `content_block:${String(index)}`,
      undefined,
      { allowTypeFallback: true },
    );
  }

  if (isAnthropicToolUseRecord(payload)) {
    addLocalToolCall(target, seen, 'anthropic:payload', payload, 'payload', undefined, {
      allowTypeFallback: true,
    });
  }
}

function collectGeminiToolCalls(
  payload: JsonRecord,
  target: R9SBillingAuditToolCallCounts,
  seen: Set<string>,
): void {
  recordArray(payload.candidates).forEach((candidate, candidateIndex) => {
    const content = optionalRecord(candidate.content);
    recordArray(content?.parts).forEach((part, partIndex) => {
      const functionCall = optionalRecord(part.functionCall) ?? optionalRecord(part.function_call);
      if (!functionCall) {
        return;
      }
      addLocalToolCall(
        target,
        seen,
        'gemini:function_call',
        functionCall,
        `${String(candidateIndex)}:${String(partIndex)}`,
        undefined,
        { allowTypeFallback: false },
      );
    });
  });
}

function localToolCallsFromPayloads(payloads: readonly JsonRecord[]): R9SBillingAuditToolCallCounts | undefined {
  const counts: R9SBillingAuditToolCallCounts = {};
  const seen = new Set<string>();

  for (const payload of payloads) {
    collectOpenAIChatToolCalls(payload, counts, seen);
    collectOpenAIResponsesToolCalls(payload, counts, seen);
    collectAnthropicMessagesToolCalls(payload, counts, seen);
    collectGeminiToolCalls(payload, counts, seen);
  }

  return cloneToolCallCounts(counts);
}

function modelFromPayload(payload: JsonRecord): string | undefined {
  const response = isRecord(payload.response) ? payload.response : undefined;
  const message = isRecord(payload.message) ? payload.message : undefined;
  return optionalString(payload.model) ?? optionalString(response?.model) ?? optionalString(message?.model);
}

function responseIdFromHeaders(headers: Record<string, string>): string | undefined {
  for (const [name, value] of Object.entries(headers)) {
    if (name.trim().toLowerCase() === RESPONSE_ID_HEADER_NAME) {
      return optionalString(value);
    }
  }
  return undefined;
}

function responseIdFromUnknownHeaders(value: unknown): string | undefined {
  const headers = optionalRecord(value);
  if (!headers) {
    return undefined;
  }

  for (const [name, headerValue] of Object.entries(headers)) {
    if (name.trim().toLowerCase() === RESPONSE_ID_HEADER_NAME) {
      return optionalString(headerValue);
    }
  }
  return undefined;
}

function billingIdFromXRequestId(xRequestId: string | undefined): string | undefined {
  if (!xRequestId || !/^\d+$/.test(xRequestId)) {
    return undefined;
  }
  return (BigInt(xRequestId) % R9S_BILLING_ID_MODULUS).toString();
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

  const payloads = parseJsonPayloads(exchange.response.body);
  const usage = extractUsage(payloads, context.provider);
  if (!usage) {
    return undefined;
  }

  const xRequestId = responseIdFromHeaders(exchange.response.headers);
  const billingId = billingIdFromXRequestId(xRequestId);
  const toolCalls = localToolCallsFromPayloads(payloads);

  return {
    provider: context.provider,
    model: usage.model ?? context.model,
    apiBaseUrl: context.apiBaseUrl,
    caseId: context.id,
    name: context.name,
    description: context.description,
    requestId: exchange.request.requestId ?? exchange.response.requestId,
    xRequestId,
    responseId: billingId,
    usage: usage.usage,
    toolCalls,
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

function nestedOptionalRecord(value: JsonRecord, key: string): JsonRecord | undefined {
  return optionalRecord(value[key]);
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

function stringFromRecords(records: readonly JsonRecord[], keys: readonly string[]): string | undefined {
  for (const record of records) {
    for (const key of keys) {
      const value = optionalString(record[key]);
      if (value !== undefined) {
        return value;
      }
    }
  }
  return undefined;
}

function toSnakeCase(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[\s.-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();
}

function isToolBillingMetricKey(key: string | undefined): boolean {
  if (!key) {
    return false;
  }
  const normalized = toSnakeCase(key);
  return normalized === 'amount'
    || normalized === 'price'
    || normalized === 'cost'
    || normalized.endsWith('_amount')
    || normalized.endsWith('_price')
    || normalized.endsWith('_cost');
}

function isIgnoredToolCallMetricKey(key: string | undefined): boolean {
  if (!key) {
    return false;
  }
  const normalized = toSnakeCase(key);
  if (!normalized) {
    return false;
  }
  if (isToolBillingMetricKey(normalized) || normalized.endsWith('_token') || normalized.endsWith('_tokens')) {
    return true;
  }
  return [
    'amount',
    'price',
    'cost',
    'input',
    'output',
    'cached',
    'cache',
    'prompt',
    'completion',
    'discount',
    'request_time',
    'status_code',
    'channel_id',
    'token_id',
    'user_id',
    'custom_user_id',
    'id',
  ].includes(normalized);
}

function isToolContainerKey(key: string | undefined): boolean {
  if (!key) {
    return false;
  }
  const normalized = toSnakeCase(key);
  return [
    'usage',
    'tool',
    'tools',
    'tool_call',
    'tool_calls',
    'tool_call_count',
    'tool_call_counts',
    'tool_usage',
    'tools_usage',
    'server_tool_usage',
    'server_tool_call_usage',
  ].includes(normalized);
}

function toolNameFromKey(key: string | undefined): string | undefined {
  if (!key) {
    return undefined;
  }

  let normalized = toSnakeCase(key);
  if (!normalized || isIgnoredToolCallMetricKey(normalized)) {
    return undefined;
  }

  const genericKeys = new Set([
    'usage',
    'tool',
    'tools',
    'tool_call',
    'tool_calls',
    'tool_call_count',
    'tool_call_counts',
    'tool_usage',
    'tools_usage',
    'server_tool_usage',
    'server_tool_call_usage',
    'count',
    'counts',
    'call_count',
    'call_counts',
    'calls',
    'usage_count',
    'usage_counts',
    'total',
    'total_count',
    'total_counts',
  ]);
  if (genericKeys.has(normalized)) {
    return undefined;
  }

  normalized = normalized
    .replace(/^(tool|tools|server_tool|server_tools)_/, '')
    .replace(/_(call|calls|usage|use|uses|count|counts|total|total_count)+$/g, '')
    .replace(/_(tool|tools)$/, '');

  if (!normalized || genericKeys.has(normalized)) {
    return undefined;
  }

  return normalized;
}

function genericToolCountNameFromKey(key: string | undefined): string | undefined {
  if (!key) {
    return undefined;
  }
  const normalized = toSnakeCase(key);
  return [
    'tool',
    'tools',
    'tool_call',
    'tool_calls',
    'tool_call_count',
    'tool_call_counts',
    'tool_usage',
    'tools_usage',
    'server_tool_usage',
    'server_tool_call_usage',
  ].includes(normalized)
    ? normalized
    : undefined;
}

function toolCallCountTotal(value: R9SBillingAuditToolCallCounts): number {
  return Object.values(value).reduce((total, count) => (
    Number.isFinite(count) ? total + count : total
  ), 0);
}

function countFromRecord(record: JsonRecord): number | undefined {
  return firstNumber(
    record.count,
    record.call_count,
    record.callCount,
    record.calls,
    record.total_count,
    record.totalCount,
    record.usage_count,
    record.usageCount,
  );
}

function isCountKey(key: string): boolean {
  return [
    'count',
    'counts',
    'call_count',
    'call_counts',
    'calls',
    'total_count',
    'total_counts',
    'usage_count',
    'usage_counts',
  ].includes(toSnakeCase(key));
}

function nameFromToolRecord(record: JsonRecord): string | undefined {
  return optionalString(record.name)
    ?? optionalString(record.tool_name)
    ?? optionalString(record.toolName)
    ?? optionalString(record.function_name)
    ?? optionalString(record.functionName)
    ?? optionalString(nestedOptionalRecord(record, 'function')?.name)
    ?? optionalString(nestedOptionalRecord(record, 'tool')?.name)
    ?? optionalString(record.tool)
    ?? optionalString(record.type);
}

function hasToolIdentity(record: JsonRecord): boolean {
  return nameFromToolRecord(record) !== undefined;
}

function hasToolBillingMetrics(record: JsonRecord): boolean {
  return Object.keys(record).some(isToolBillingMetricKey);
}

function isToolIdentityKey(key: string): boolean {
  return [
    'name',
    'type',
    'tool',
    'tool_name',
    'function',
    'function_name',
  ].includes(toSnakeCase(key));
}

function collectToolCallCounts(
  value: unknown,
  target: R9SBillingAuditToolCallCounts,
  contextKey?: string,
  contextToolName?: string,
): void {
  const contextContainer = isToolContainerKey(contextKey);
  const contextCallArray = toSnakeCase(contextKey ?? '') === 'tool_calls';
  const inheritedToolName = contextToolName ?? toolNameFromKey(contextKey);

  if (Array.isArray(value)) {
    for (const item of value) {
      if (!isRecord(item)) {
        continue;
      }
      const itemToolName = toolNameFromKey(nameFromToolRecord(item)) ?? inheritedToolName;
      const itemCount = countFromRecord(item);
      if (itemCount !== undefined) {
        addToolCallCount(target, itemToolName, itemCount);
        continue;
      } else if (itemToolName && (contextContainer || hasToolIdentity(item))) {
        addToolCallCount(target, itemToolName, 1);
        continue;
      } else if (contextCallArray) {
        addToolCallCount(target, itemToolName ?? 'tool_calls', 1);
        continue;
      }
      collectToolCallCounts(item, target, contextKey, itemToolName);
    }
    return;
  }

  const record = optionalRecord(value);
  if (!record) {
    return;
  }

  const countBeforeRecord = toolCallCountTotal(target);
  const recordToolName = toolNameFromKey(nameFromToolRecord(record)) ?? inheritedToolName;
  const recordCount = countFromRecord(record);
  if (recordCount !== undefined && recordToolName) {
    addToolCallCount(target, recordToolName, recordCount);
  }
  const namedRecordConsumed = recordCount !== undefined && Boolean(recordToolName);
  if (!namedRecordConsumed && recordToolName && (contextContainer || contextToolName !== undefined || hasToolIdentity(record))) {
    addToolCallCount(target, recordToolName, 1);
  }
  const recordCountConsumed = Boolean(recordToolName) && (recordCount !== undefined || contextContainer || contextToolName !== undefined || hasToolIdentity(record));

  for (const [key, rawValue] of Object.entries(record)) {
    if (isIgnoredToolCallMetricKey(key)) {
      continue;
    }
    if (recordCountConsumed && isToolIdentityKey(key)) {
      continue;
    }
    if (recordCountConsumed && isCountKey(key)) {
      continue;
    }
    const keyToolName = toolNameFromKey(key);
    const keyContainer = isToolContainerKey(key);
    const childToolName = keyToolName ?? (keyContainer || contextContainer ? undefined : recordToolName);

    const numericValue = optionalNumber(rawValue);
    if (numericValue !== undefined) {
      if (keyToolName) {
        addToolCallCount(target, keyToolName, numericValue);
      } else if (genericToolCountNameFromKey(key)) {
        addToolCallCount(target, genericToolCountNameFromKey(key), numericValue);
      } else if (isCountKey(key) && recordToolName) {
        addToolCallCount(target, recordToolName, numericValue);
      }
      continue;
    }

    if (keyContainer || keyToolName || recordToolName) {
      collectToolCallCounts(rawValue, target, key, childToolName);
    }
  }

  if (!recordToolName && contextContainer && toolCallCountTotal(target) === countBeforeRecord) {
    addToolCallCount(
      target,
      genericToolCountNameFromKey(contextKey),
      recordCount ?? (hasToolBillingMetrics(record) ? 1 : undefined),
    );
  }
}

function toolCallCountsFromExt(ext: unknown): R9SBillingAuditToolCallCounts | undefined {
  const counts: R9SBillingAuditToolCallCounts = {};
  collectToolCallCounts(ext, counts);
  return cloneToolCallCounts(counts);
}

function normalizeBillingRecord(value: unknown): R9SBillingAuditRemoteRecord | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const usageRecord = nestedOptionalRecord(value, 'usage');
  const billingRecord = nestedOptionalRecord(value, 'billing');
  const tokenRecord = nestedOptionalRecord(value, 'tokens');
  const extRecord = optionalRecord(value.ext);
  const metadataRecord = nestedOptionalRecord(value, 'metadata') ?? (extRecord ? nestedOptionalRecord(extRecord, 'metadata') : undefined);
  const responseRecord = nestedOptionalRecord(value, 'response') ?? (extRecord ? nestedOptionalRecord(extRecord, 'response') : undefined);
  const requestRecord = nestedOptionalRecord(value, 'request') ?? (extRecord ? nestedOptionalRecord(extRecord, 'request') : undefined);
  const responseHeadersRecord =
    optionalRecord(value.response_headers) ??
    optionalRecord(value.responseHeaders) ??
    optionalRecord(responseRecord?.headers) ??
    (extRecord
      ? optionalRecord(extRecord.response_headers) ??
        optionalRecord(extRecord.responseHeaders) ??
        optionalRecord(nestedOptionalRecord(extRecord, 'response')?.headers)
      : undefined);
  const records = [
    responseRecord,
    value,
    extRecord,
    metadataRecord,
    requestRecord,
    usageRecord,
    billingRecord,
    tokenRecord,
  ].filter(isRecord);
  const model = stringFromRecords(records, ['model', 'model_name', 'modelName']);
  if (!model) {
    return undefined;
  }
  const id = optionalString(value.id);
  const xRequestId = responseIdFromUnknownHeaders(responseHeadersRecord);
  const responseId = id ?? billingIdFromXRequestId(xRequestId);

  const nonCachedInputTokens = numberFromRecords(records, [
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
  const inputTokens =
    nonCachedInputTokens === undefined && cachedTokens === undefined
      ? undefined
      : (nonCachedInputTokens ?? 0) + (cachedTokens ?? 0);
  const totalTokens =
    numberFromRecords(records, [
      'total_token',
      'total_tokens',
      'totalToken',
      'totalTokens',
      'totalTokenCount',
    ]) ?? sumIfAllKnown(inputTokens, outputTokens);
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
    id,
    xRequestId,
    responseId,
    requestTime: optionalNumber(value.request_time),
    userId: optionalString(value.user_id),
    customUserId: optionalString(value.custom_user_id),
    tokenId: optionalString(value.token_id),
    model,
    modelType: optionalString(value.model_type),
    usage,
    toolCalls: toolCallCountsFromExt(value.ext),
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
      toolCalls: cloneToolCallCounts(record.toolCalls),
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

function appendMissingResponseIdWarnings(
  warnings: string[],
  label: string,
  missingLabel: string,
  records: ReadonlyArray<{
    model: string;
    id?: string;
    requestId?: string;
    caseId?: string;
    responseId?: string;
  }>,
): void {
  const missing = records.filter((record) => !record.responseId);
  if (missing.length === 0) {
    return;
  }

  const examples = missing
    .slice(0, 3)
    .map(recordIdentifier)
    .join('; ');
  const suffix = missing.length > 3 ? `; +${missing.length - 3} more` : '';
  warnings.push(`${label} ${missingLabel} was not found for ${missing.length} record(s): ${examples}${suffix}.`);
}

function appendUnmatchedRemoteResponseWarnings(
  warnings: string[],
  localRecords: readonly R9SBillingAuditLocalRecord[],
  remoteRecords: readonly R9SBillingAuditRemoteRecord[],
): void {
  const localResponseIds = new Set(localRecords.map((record) => record.responseId).filter((id): id is string => Boolean(id)));
  const unmatched = remoteRecords.filter((record) => record.responseId && !localResponseIds.has(record.responseId));
  if (unmatched.length === 0) {
    return;
  }

  const examples = unmatched
    .slice(0, 3)
    .map((record) => record.responseId ?? recordIdentifier(record))
    .join('; ');
  const suffix = unmatched.length > 3 ? `; +${unmatched.length - 3} more` : '';
  warnings.push(`R9S billing records were not matched to local billing id values for ${unmatched.length} record(s): ${examples}${suffix}.`);
}

function buildWarnings(
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
  appendMissingUsageWarnings(warnings, 'Local trace', localRecords);
  appendMissingUsageWarnings(warnings, 'R9S billing', remoteRecords);
  appendMissingResponseIdWarnings(warnings, 'Local trace', 'X-Request-Id-derived billing id', localRecords);
  appendMissingResponseIdWarnings(warnings, 'R9S billing', 'billing id', remoteRecords);
  appendUnmatchedRemoteResponseWarnings(warnings, localRecords, remoteRecords);
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
        `billingId=${formatComparisonResponseId(comparison)}`,
        `model=${comparison.model}`,
        `localModels=${formatComparisonModels(comparison, 'local')}`,
        `r9sModels=${formatComparisonModels(comparison, 'remote')}`,
        `inputDiff=${formatUsageNumber(comparison.diff.inputTokens)}`,
        `outputDiff=${formatUsageNumber(comparison.diff.outputTokens)}`,
        `cachedDiff=${formatUsageNumber(comparison.diff.cachedTokens)}`,
        `localToolCalls=${formatToolCallCounts(comparison.localToolCalls)}`,
        `r9sToolCalls=${formatToolCallCounts(comparison.remoteToolCalls ?? comparison.toolCalls)}`,
        `toolCallDiff=${formatToolCallCounts(comparison.toolCallDiff, { signed: true })}`,
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
        comparisons = compareUsageByResponseId(localRecords, fetched.records);
        warnings = buildWarnings(localRecords, fetched.records);
      } catch (auditError: unknown) {
        error = formatError(auditError);
        warnings = buildWarnings(localRecords, []);
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
