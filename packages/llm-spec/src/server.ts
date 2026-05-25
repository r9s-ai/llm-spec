import { randomUUID } from 'node:crypto';
import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { basename, resolve as resolvePath } from 'node:path';

import { formatError, resolveRuntimeConfig } from './api-sdk-tester';
import type { RuntimeConfig, TargetApiType } from './api-sdk-tester';
import { runRuntimeConfig } from './runner';
import type { RunProgressEvent, RunSnapshot, RunSummary } from './types';

type JsonRecord = Record<string, unknown>;
type AgentProvider = 'claude-agent' | 'codex';

const BODY_LIMIT_BYTES = 64 * 1024 * 1024;
const DEFAULT_BACKEND_PORT = 8788;
const RUN_HISTORY_DIR = resolvePath(process.cwd(), process.env.LLM_SPEC_HISTORY_DIR ?? '.llm-spec-history');
const RUN_HISTORY_ID_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_-]*$/;
const RUN_HISTORY_LIST_LIMIT = 200;
const RUN_JOB_LIST_LIMIT = 100;
const RUN_JOB_RETENTION_MS = 24 * 60 * 60 * 1000;

const CASE_FILTER_ENV_KEYS = ['TARGET_CASES', 'TEST_CASES', 'CASE_IDS'] as const;

let runQueue: Promise<void> = Promise.resolve();
const runJobs = new Map<string, BackendRunJob>();

type BackendRunJobStatus = 'queued' | 'running' | 'completed' | 'failed';
type BackendRunTargetStatus = 'pending' | 'running' | 'complete';

interface RunHistoryEntry {
  id: string;
  fileName: string;
  createdAt: string;
  startedAt: string;
  finishedAt: string;
  providerCount: number;
  providers: string[];
  models: string[];
  totalPassed: number;
  totalFailed: number;
  totalSkipped: number;
  siteName?: string;
  apiBaseUrl?: string;
  backendUrl?: string;
}

interface BackendRunJobTarget {
  id: string;
  kind: 'standard' | 'agent';
  enabled: boolean;
  apiType?: string;
  agentProvider?: AgentProvider;
  model?: string;
  targetCases?: string;
}

interface BackendRunJobRequest {
  apiKey?: string;
  apiBaseUrl?: string;
  backendUrl?: string;
  standardExecution: 'browser' | 'backend';
  timeoutMs: number;
  concurrency: number;
  customHeaders?: Record<string, string>;
  apiVersion?: string;
  workingDirectory?: string;
  skipGitRepoCheck?: boolean;
  testImagePath?: string;
  persistResult: boolean;
  runSnapshot?: RunSnapshot;
  targets: BackendRunJobTarget[];
}

interface BackendRunTargetProgress {
  id: string;
  label: string;
  status: BackendRunTargetStatus;
  completed: number;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  currentCase?: string;
}

interface BackendRunJobProgress {
  completed: number;
  total: number;
  percent: number;
  statusText: string;
  detailText: string;
  passed: number;
  failed: number;
  skipped: number;
  targets: BackendRunTargetProgress[];
}

interface BackendRunJob {
  id: string;
  status: BackendRunJobStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  request: BackendRunJobRequest;
  progressTargets: BackendRunTargetProgress[];
  error?: string;
  summary?: RunSummary;
  historyEntry?: RunHistoryEntry;
}

function getCorsHeaders(): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': process.env.LLM_SPEC_CORS_ORIGIN ?? '*',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'content-type,authorization',
  };
}

function sendJson(response: ServerResponse, statusCode: number, body: unknown): void {
  response.writeHead(statusCode, {
    ...getCorsHeaders(),
    'Content-Type': 'application/json; charset=utf-8',
  });
  response.end(`${JSON.stringify(body, null, 2)}\n`);
}

function sendNoContent(response: ServerResponse): void {
  response.writeHead(204, getCorsHeaders());
  response.end();
}

function startNdjson(response: ServerResponse): void {
  response.writeHead(200, {
    ...getCorsHeaders(),
    'Content-Type': 'application/x-ndjson; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
}

function writeNdjson(response: ServerResponse, body: unknown): void {
  response.write(`${JSON.stringify(body)}\n`);
}

function isJsonRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readJsonBody(request: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;

    request.on('data', (chunk: Buffer) => {
      size += chunk.byteLength;
      if (size > BODY_LIMIT_BYTES) {
        reject(new Error('request body is too large'));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });

    request.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8').trim();
      if (!raw) {
        resolve({});
        return;
      }

      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error('request body must be valid JSON'));
      }
    });

    request.on('error', reject);
  });
}

function optionalString(body: JsonRecord, key: string): string | undefined {
  const value = body[key];
  if (typeof value !== 'string') {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function optionalBoolean(body: JsonRecord, key: string): boolean | undefined {
  const value = body[key];
  return typeof value === 'boolean' ? value : undefined;
}

function optionalRunSnapshot(body: JsonRecord): RunSnapshot | undefined {
  const value = body.runSnapshot;
  if (!isJsonRecord(value)) {
    return undefined;
  }
  return value as unknown as RunSnapshot;
}

function optionalPositiveNumber(body: JsonRecord, key: string): number | undefined {
  const value = body[key];
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return undefined;
  }
  return value;
}

function optionalModel(body: JsonRecord, key: string): string | undefined {
  const value = optionalString(body, key);
  if (!value || value.toLowerCase() === 'default') {
    return undefined;
  }
  return value;
}

function optionalCustomHeaders(body: JsonRecord): Record<string, string> | undefined {
  const value = body.customHeaders;
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return parseCustomHeadersRecord(parsed);
    } catch {
      throw new Error('customHeaders must be a JSON object');
    }
  }
  return parseCustomHeadersRecord(value);
}

function parseCustomHeadersRecord(value: unknown): Record<string, string> | undefined {
  if (!isJsonRecord(value)) {
    return undefined;
  }

  const headers: Record<string, string> = {};
  for (const [key, headerValue] of Object.entries(value)) {
    if (typeof headerValue === 'string' && key.trim() && headerValue.trim()) {
      headers[key] = headerValue;
    }
  }

  return Object.keys(headers).length > 0 ? headers : undefined;
}

function normalizeTargetApiType(value: string | undefined): TargetApiType {
  const normalized = value?.trim().toLowerCase();
  if (
    normalized === 'openai.chat' ||
    normalized === 'openai.chatcompletions' ||
    normalized === 'openai.chat_completions' ||
    normalized === 'chat' ||
    normalized === 'chatcompletions'
  ) {
    return 'openai.chat';
  }

  if (normalized === 'openai.responses' || normalized === 'responses') {
    return 'openai.responses';
  }

  if (
    normalized === 'anthropic.messages' ||
    normalized === 'anthropic.message' ||
    normalized === 'claude.messages' ||
    normalized === 'messages'
  ) {
    return 'anthropic.messages';
  }

  if (
    normalized === 'gemini.generatecontent' ||
    normalized === 'gemini.generate_content' ||
    normalized === 'gemini' ||
    normalized === 'google.generatecontent'
  ) {
    return 'gemini.generateContent';
  }

  throw new Error('apiType must be one of openai.chat, openai.responses, anthropic.messages, gemini.generateContent');
}

function normalizeAgentProvider(value: string | undefined): AgentProvider {
  const normalized = value?.trim().toLowerCase();
  if (normalized === 'claude-agent' || normalized === 'claudeagent' || normalized === 'claude') {
    return 'claude-agent';
  }
  if (normalized === 'codex') {
    return 'codex';
  }
  throw new Error('agentProvider must be claude-agent or codex');
}

function defaultModelForApiType(apiType: TargetApiType): string {
  if (apiType === 'anthropic.messages') {
    return 'claude-3-5-haiku-latest';
  }
  if (apiType === 'gemini.generateContent') {
    return 'gemini-2.5-flash';
  }
  return 'gpt-4o-mini';
}

function commonConfig(baseConfig: RuntimeConfig, body: JsonRecord): RuntimeConfig {
  return {
    ...baseConfig,
    targetCases: optionalString(body, 'targetCases'),
    failFast: false,
    concurrency: optionalPositiveNumber(body, 'concurrency') ?? baseConfig.concurrency,
    reportFile: undefined,
  };
}

function buildStandardRuntimeConfig(body: JsonRecord): RuntimeConfig {
  const baseConfig = resolveRuntimeConfig();
  const config = commonConfig(baseConfig, body);
  const apiType = normalizeTargetApiType(optionalString(body, 'apiType'));
  const customHeaders = optionalCustomHeaders(body);
  const providerConfig = apiType === 'anthropic.messages'
    ? baseConfig.anthropic
    : apiType === 'gemini.generateContent'
      ? baseConfig.gemini
      : baseConfig.openai;
  const defaultCustomHeaders = apiType === 'openai.chat' || apiType === 'openai.responses'
    ? baseConfig.openai.customHeaders
    : undefined;
  const defaultApiVersion = apiType === 'gemini.generateContent' ? baseConfig.gemini.apiVersion : undefined;

  return {
    ...config,
    targetProviders: [],
    testTarget: {
      apiType,
      apiKey: optionalString(body, 'apiKey') ?? providerConfig.apiKey,
      apiBaseUrl: optionalString(body, 'apiBaseUrl') ?? providerConfig.apiBaseUrl,
      model: optionalString(body, 'model') ?? providerConfig.model ?? defaultModelForApiType(apiType),
      timeoutMs: optionalPositiveNumber(body, 'timeoutMs') ?? providerConfig.timeoutMs ?? 45_000,
      customHeaders: customHeaders ?? defaultCustomHeaders,
      apiVersion: optionalString(body, 'apiVersion') ?? defaultApiVersion,
    },
  };
}

function buildAgentRuntimeConfig(body: JsonRecord): RuntimeConfig {
  const baseConfig = resolveRuntimeConfig();
  const config = commonConfig(baseConfig, body);
  const provider = normalizeAgentProvider(optionalString(body, 'agentProvider') ?? optionalString(body, 'provider'));
  const customHeaders = optionalCustomHeaders(body);

  if (provider === 'claude-agent') {
    return {
      ...config,
      targetProviders: ['claude-agent'],
      testTarget: undefined,
      claudeAgent: {
        ...baseConfig.claudeAgent,
        apiKey: optionalString(body, 'apiKey') ?? baseConfig.claudeAgent.apiKey,
        apiBaseUrl: optionalString(body, 'apiBaseUrl') ?? baseConfig.claudeAgent.apiBaseUrl,
        model: optionalModel(body, 'model') ?? baseConfig.claudeAgent.model,
        workingDirectory: optionalString(body, 'workingDirectory') ?? baseConfig.claudeAgent.workingDirectory,
        skipGitRepoCheck: optionalBoolean(body, 'skipGitRepoCheck') ?? baseConfig.claudeAgent.skipGitRepoCheck,
        testImagePath: optionalString(body, 'testImagePath') ?? baseConfig.claudeAgent.testImagePath,
        timeoutMs: optionalPositiveNumber(body, 'timeoutMs') ?? baseConfig.claudeAgent.timeoutMs,
        customHeaders: customHeaders ?? baseConfig.claudeAgent.customHeaders,
      },
    };
  }

  return {
    ...config,
    targetProviders: ['codex'],
    testTarget: undefined,
    codex: {
      ...baseConfig.codex,
      apiKey: optionalString(body, 'apiKey') ?? baseConfig.codex.apiKey,
      apiBaseUrl: optionalString(body, 'apiBaseUrl') ?? baseConfig.codex.apiBaseUrl,
      model: optionalModel(body, 'model') ?? baseConfig.codex.model,
      workingDirectory: optionalString(body, 'workingDirectory') ?? baseConfig.codex.workingDirectory,
      skipGitRepoCheck: optionalBoolean(body, 'skipGitRepoCheck') ?? baseConfig.codex.skipGitRepoCheck,
      testImagePath: optionalString(body, 'testImagePath') ?? baseConfig.codex.testImagePath,
      timeoutMs: optionalPositiveNumber(body, 'timeoutMs') ?? baseConfig.codex.timeoutMs,
    },
  };
}

function buildRuntimeConfig(body: JsonRecord): RuntimeConfig {
  const kind = optionalString(body, 'kind') ?? 'standard';
  if (kind === 'standard') {
    return buildStandardRuntimeConfig(body);
  }
  if (kind === 'agent') {
    return buildAgentRuntimeConfig(body);
  }
  throw new Error('kind must be standard or agent');
}

function normalizeJobTarget(value: unknown, index: number): BackendRunJobTarget | undefined {
  if (!isJsonRecord(value)) {
    return undefined;
  }

  const kind = optionalString(value, 'kind') ?? 'standard';
  const enabled = optionalBoolean(value, 'enabled') ?? true;
  if (kind === 'standard') {
    const apiType = normalizeTargetApiType(optionalString(value, 'apiType'));
    return {
      id: optionalString(value, 'id') ?? `standard-${index + 1}`,
      kind,
      enabled,
      apiType,
      model: optionalString(value, 'model'),
      targetCases: optionalString(value, 'targetCases'),
    };
  }

  if (kind === 'agent') {
    const agentProvider = normalizeAgentProvider(optionalString(value, 'agentProvider') ?? optionalString(value, 'provider'));
    return {
      id: optionalString(value, 'id') ?? `agent-${index + 1}`,
      kind,
      enabled,
      agentProvider,
      model: optionalModel(value, 'model'),
      targetCases: optionalString(value, 'targetCases'),
    };
  }

  throw new Error('job target kind must be standard or agent');
}

function normalizeBackendRunJobRequest(body: JsonRecord): BackendRunJobRequest {
  const rawTargets = Array.isArray(body.targets) ? body.targets : [];
  const targets = rawTargets
    .map(normalizeJobTarget)
    .filter((target): target is BackendRunJobTarget => Boolean(target))
    .filter((target) => target.enabled);

  if (targets.length === 0) {
    throw new Error('job requires at least one enabled target');
  }

  const standardExecution = optionalString(body, 'standardExecution') === 'browser' ? 'browser' : 'backend';
  return {
    apiKey: optionalString(body, 'apiKey'),
    apiBaseUrl: optionalString(body, 'apiBaseUrl'),
    backendUrl: optionalString(body, 'backendUrl'),
    standardExecution,
    timeoutMs: optionalPositiveNumber(body, 'timeoutMs') ?? 45_000,
    concurrency: optionalPositiveNumber(body, 'concurrency') ?? 1,
    customHeaders: optionalCustomHeaders(body),
    apiVersion: optionalString(body, 'apiVersion'),
    workingDirectory: optionalString(body, 'workingDirectory'),
    skipGitRepoCheck: optionalBoolean(body, 'skipGitRepoCheck') ?? false,
    testImagePath: optionalString(body, 'testImagePath'),
    persistResult: optionalBoolean(body, 'persistResult') ?? true,
    runSnapshot: optionalRunSnapshot(body),
    targets,
  };
}

function standardTargetLabel(apiType: string | undefined): string {
  if (apiType === 'openai.responses') {
    return 'OpenAI Responses';
  }
  if (apiType === 'anthropic.messages') {
    return 'Anthropic Messages';
  }
  if (apiType === 'gemini.generateContent') {
    return 'Gemini generateContent';
  }
  return 'OpenAI Chat Completions';
}

function agentTargetLabel(agentProvider: AgentProvider | undefined): string {
  return agentProvider === 'codex' ? 'Codex' : 'Claude Agent';
}

function jobTargetLabel(target: BackendRunJobTarget): string {
  return target.kind === 'agent' ? agentTargetLabel(target.agentProvider) : standardTargetLabel(target.apiType);
}

function jobTargetModelLabel(target: BackendRunJobTarget): string {
  if (target.model) {
    return target.model;
  }
  if (target.kind === 'standard') {
    return defaultModelForApiType(normalizeTargetApiType(target.apiType));
  }
  return 'Default';
}

function createJobTargetProgress(target: BackendRunJobTarget): BackendRunTargetProgress {
  return {
    id: target.id,
    label: jobTargetLabel(target),
    status: 'pending',
    completed: 0,
    total: 1,
    passed: 0,
    failed: 0,
    skipped: 0,
  };
}

function summarizeJobProgress(job: BackendRunJob): BackendRunJobProgress {
  const targets = job.progressTargets;
  if (targets.length === 0) {
    return {
      completed: 0,
      total: 0,
      percent: 0,
      statusText: job.status === 'queued' ? 'Queued' : 'Ready',
      detailText: 'No test run started',
      passed: 0,
      failed: 0,
      skipped: 0,
      targets: [],
    };
  }

  const total = targets.reduce((sum, target) => sum + Math.max(target.total, 1), 0);
  const completed = targets.reduce((sum, target) => sum + Math.min(target.completed, Math.max(target.total, 1)), 0);
  const passed = targets.reduce((sum, target) => sum + target.passed, 0);
  const failed = targets.reduce((sum, target) => sum + target.failed, 0);
  const skipped = targets.reduce((sum, target) => sum + target.skipped, 0);
  const runningTarget = targets.find((target) => target.status === 'running');
  const pendingTarget = targets.find((target) => target.status === 'pending');
  const activeTarget = runningTarget ?? pendingTarget ?? targets[targets.length - 1];
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;
  const statusText = job.status === 'failed'
    ? 'Run failed'
    : runningTarget
      ? `Running ${runningTarget.label}`
      : pendingTarget
        ? `Queued ${pendingTarget.label}`
        : 'Run complete';
  const caseDetail = activeTarget?.currentCase ? ` - ${activeTarget.currentCase}` : '';

  return {
    completed,
    total,
    percent,
    statusText,
    detailText: `${completed}/${total} cases${caseDetail}`,
    passed,
    failed,
    skipped,
    targets: targets.map((target) => ({ ...target })),
  };
}

function buildJobTargetBody(request: BackendRunJobRequest, target: BackendRunJobTarget): JsonRecord {
  const base: JsonRecord = {
    kind: target.kind,
    apiKey: request.apiKey,
    apiBaseUrl: request.apiBaseUrl,
    model: target.model,
    timeoutMs: request.timeoutMs,
    targetCases: target.targetCases,
    customHeaders: request.customHeaders,
    apiVersion: request.apiVersion,
    failFast: false,
    concurrency: request.concurrency,
    persistResult: false,
    runSnapshot: request.runSnapshot,
  };

  if (target.kind === 'standard') {
    return {
      ...base,
      apiType: target.apiType,
    };
  }

  return {
    ...base,
    agentProvider: target.agentProvider,
    workingDirectory: request.workingDirectory,
    skipGitRepoCheck: request.skipGitRepoCheck,
    testImagePath: request.testImagePath,
  };
}

function mergeRunSummaries(summaries: RunSummary[]): RunSummary {
  if (summaries.length === 0) {
    const now = new Date().toISOString();
    return { startedAt: now, finishedAt: now, providers: [], totalPassed: 0, totalFailed: 0, totalSkipped: 0 };
  }

  return {
    startedAt: summaries[0]!.startedAt,
    finishedAt: summaries[summaries.length - 1]!.finishedAt,
    providers: summaries.flatMap((summary) => summary.providers),
    totalPassed: summaries.reduce((sum, summary) => sum + summary.totalPassed, 0),
    totalFailed: summaries.reduce((sum, summary) => sum + summary.totalFailed, 0),
    totalSkipped: summaries.reduce((sum, summary) => sum + summary.totalSkipped, 0),
  };
}

function failedRunSummary(provider: string, model: string, error: unknown): RunSummary {
  const now = new Date().toISOString();
  return {
    startedAt: now,
    finishedAt: now,
    providers: [{
      provider,
      model,
      startedAt: now,
      finishedAt: now,
      passed: 0,
      failed: 1,
      skipped: 0,
      caseResults: [{
        id: 'run_error',
        description: `Failed to run ${provider}`,
        status: 'failed',
        durationMs: 0,
        coveredParams: [],
        error: formatError(error),
      }],
      allParams: [],
      coveredParams: [],
      untestedParams: [],
    }],
    totalPassed: 0,
    totalFailed: 1,
    totalSkipped: 0,
  };
}

function findJobProgress(job: BackendRunJob, target: BackendRunJobTarget): BackendRunTargetProgress | undefined {
  return job.progressTargets.find((progress) => progress.id === target.id);
}

function completeJobTarget(job: BackendRunJob, target: BackendRunJobTarget): void {
  const progress = findJobProgress(job, target);
  if (!progress) {
    return;
  }
  progress.status = 'complete';
  progress.total = Math.max(progress.total, 1);
  progress.completed = progress.total;
}

function failJobTarget(job: BackendRunJob, target: BackendRunJobTarget, error: unknown): void {
  const progress = findJobProgress(job, target);
  if (!progress) {
    return;
  }
  progress.status = 'complete';
  progress.total = Math.max(progress.total, 1);
  progress.completed = progress.total;
  progress.failed += 1;
  progress.currentCase = formatError(error);
}

function applyJobProgressEvent(job: BackendRunJob, target: BackendRunJobTarget, event: RunProgressEvent): void {
  const progress = findJobProgress(job, target);
  if (!progress) {
    return;
  }
  progress.status = event.phase === 'provider-complete' ? 'complete' : 'running';
  progress.total = Math.max(event.total, 1);
  progress.completed = event.phase === 'provider-complete'
    ? progress.total
    : Math.min(event.completed, progress.total);
  if (event.phase === 'case-start') {
    progress.currentCase = event.caseId ?? event.description;
  }
  if (event.phase === 'case-complete') {
    progress.currentCase = event.caseId ?? event.description;
    if (event.status === 'passed') {
      progress.passed += 1;
    } else if (event.status === 'failed') {
      progress.failed += 1;
    } else if (event.status === 'skipped') {
      progress.skipped += 1;
    }
  }
  if (event.phase === 'provider-complete') {
    progress.currentCase = `${event.provider} complete`;
  }
}

function isRunSummary(value: unknown): value is RunSummary {
  if (!isJsonRecord(value)) {
    return false;
  }

  return (
    typeof value.startedAt === 'string' &&
    typeof value.finishedAt === 'string' &&
    Array.isArray(value.providers) &&
    typeof value.totalPassed === 'number' &&
    typeof value.totalFailed === 'number' &&
    typeof value.totalSkipped === 'number'
  );
}

function parseRunSummary(value: unknown): RunSummary {
  if (!isRunSummary(value)) {
    throw new Error('run summary must include startedAt, finishedAt, providers, and totals');
  }
  return value;
}

function getHistoryFilePath(id: string): string {
  if (!RUN_HISTORY_ID_PATTERN.test(id)) {
    throw new Error('invalid history id');
  }
  return resolvePath(RUN_HISTORY_DIR, `${id}.json`);
}

function createHistoryId(summary: RunSummary): string {
  const timestamp = (summary.finishedAt || new Date().toISOString())
    .replace(/[^0-9]/g, '')
    .slice(0, 14) || 'run';
  return `${timestamp}-${randomUUID()}`;
}

function createHistoryEntry(id: string, fileName: string, summary: RunSummary): RunHistoryEntry {
  const providers = summary.providers.map((provider) => provider.provider);
  const models = summary.providers
    .map((provider) => provider.model)
    .filter((model): model is string => Boolean(model));
  const firstApiBaseUrl = summary.providers.find((provider) => provider.apiBaseUrl)?.apiBaseUrl;

  return {
    id,
    fileName,
    createdAt: summary.finishedAt,
    startedAt: summary.startedAt,
    finishedAt: summary.finishedAt,
    providerCount: summary.providers.length,
    providers,
    models,
    totalPassed: summary.totalPassed,
    totalFailed: summary.totalFailed,
    totalSkipped: summary.totalSkipped,
    siteName: summary.runSnapshot?.siteName,
    apiBaseUrl: summary.runSnapshot?.apiBaseUrl ?? firstApiBaseUrl,
    backendUrl: summary.runSnapshot?.backendUrl,
  };
}

async function persistRunSummary(summary: RunSummary): Promise<RunHistoryEntry> {
  await mkdir(RUN_HISTORY_DIR, { recursive: true });
  const id = createHistoryId(summary);
  const fileName = `${id}.json`;
  const filePath = getHistoryFilePath(id);
  await writeFile(filePath, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');
  return createHistoryEntry(id, fileName, summary);
}

async function readHistorySummary(id: string): Promise<RunSummary> {
  const raw = await readFile(getHistoryFilePath(id), 'utf8');
  return parseRunSummary(JSON.parse(raw) as unknown);
}

async function listRunHistory(): Promise<RunHistoryEntry[]> {
  let fileNames: string[];
  try {
    fileNames = await readdir(RUN_HISTORY_DIR);
  } catch (error: unknown) {
    if (
      error &&
      typeof error === 'object' &&
      'code' in error &&
      (error as { code?: unknown }).code === 'ENOENT'
    ) {
      return [];
    }
    throw error;
  }

  const entries = await Promise.all(fileNames
    .filter((fileName) => fileName.endsWith('.json'))
    .map(async (fileName): Promise<RunHistoryEntry | undefined> => {
      const id = basename(fileName, '.json');
      if (!RUN_HISTORY_ID_PATTERN.test(id)) {
        return undefined;
      }

      try {
        const summary = await readHistorySummary(id);
        return createHistoryEntry(id, fileName, summary);
      } catch {
        return undefined;
      }
    }));

  return entries
    .filter((entry): entry is RunHistoryEntry => Boolean(entry))
    .sort((left, right) => right.finishedAt.localeCompare(left.finishedAt))
    .slice(0, RUN_HISTORY_LIST_LIMIT);
}

function serializeRunJob(job: BackendRunJob, includeSummary = true): JsonRecord {
  return {
    id: job.id,
    status: job.status,
    createdAt: job.createdAt,
    startedAt: job.startedAt,
    finishedAt: job.finishedAt,
    error: job.error,
    progress: summarizeJobProgress(job),
    summary: includeSummary ? job.summary : undefined,
    historyEntry: job.historyEntry,
  };
}

function pruneRunJobs(): void {
  const now = Date.now();
  const jobs = Array.from(runJobs.values())
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt));

  for (const job of jobs) {
    const isTerminal = job.status === 'completed' || job.status === 'failed';
    const timestamp = Date.parse(job.finishedAt ?? job.createdAt);
    const expired = isTerminal && Number.isFinite(timestamp) && now - timestamp > RUN_JOB_RETENTION_MS;
    const overLimit = jobs.indexOf(job) >= RUN_JOB_LIST_LIMIT;
    if (expired || overLimit) {
      runJobs.delete(job.id);
    }
  }
}

function createBackendRunJob(request: BackendRunJobRequest): BackendRunJob {
  pruneRunJobs();
  const id = randomUUID();
  const job: BackendRunJob = {
    id,
    status: 'queued',
    createdAt: new Date().toISOString(),
    request,
    progressTargets: request.targets.map(createJobTargetProgress),
  };
  runJobs.set(id, job);
  void runBackendRunJob(job);
  return job;
}

async function runBackendRunJob(job: BackendRunJob): Promise<void> {
  try {
    await withRunLock(async () => {
      const summaries: RunSummary[] = [];

      for (const target of job.request.targets) {
        try {
          const body = buildJobTargetBody(job.request, target);
          const config = buildRuntimeConfig(body);
          const summary = await withCaseFilterEnv(config.targetCases, () => runRuntimeConfig(config, {
            onProgress: (event) => { applyJobProgressEvent(job, target, event); },
          }));
          summaries.push(summary);
          completeJobTarget(job, target);
        } catch (targetError: unknown) {
          failJobTarget(job, target, targetError);
          summaries.push(failedRunSummary(jobTargetLabel(target), jobTargetModelLabel(target), targetError));
        }
      }

      const merged = mergeRunSummaries(summaries);
      if (job.request.runSnapshot) {
        merged.runSnapshot = job.request.runSnapshot;
      }
      job.summary = merged;

      if (job.request.persistResult) {
        try {
          job.historyEntry = await persistRunSummary(merged);
        } catch (historyError: unknown) {
          job.error = `Failed to save backend run history: ${formatError(historyError)}`;
          console.error(job.error);
        }
      }

      job.status = 'completed';
      job.finishedAt = new Date().toISOString();
    }, () => {
      job.status = 'running';
      job.startedAt = new Date().toISOString();
    });
  } catch (error: unknown) {
    job.status = 'failed';
    job.error = formatError(error);
    job.finishedAt = new Date().toISOString();
  }
}

function applyRequestRunSnapshot(summary: RunSummary, rawBody: JsonRecord): void {
  const runSnapshot = optionalRunSnapshot(rawBody);
  if (runSnapshot) {
    summary.runSnapshot = runSnapshot;
  }
}

function shouldPersistRunResult(rawBody: JsonRecord): boolean {
  return optionalBoolean(rawBody, 'persistResult') ?? true;
}

async function withRunLock<T>(action: () => Promise<T>, onAcquired?: () => void): Promise<T> {
  const previous = runQueue.catch(() => undefined);
  let release!: () => void;
  runQueue = new Promise<void>((resolve) => {
    release = resolve;
  });

  await previous;
  onAcquired?.();
  try {
    return await action();
  } finally {
    release();
  }
}

async function withCaseFilterEnv<T>(targetCases: string | undefined, action: () => Promise<T>): Promise<T> {
  const previousValues = new Map<string, string | undefined>();
  for (const key of CASE_FILTER_ENV_KEYS) {
    previousValues.set(key, process.env[key]);
    delete process.env[key];
  }

  if (targetCases) {
    process.env.TARGET_CASES = targetCases;
  }

  try {
    return await action();
  } finally {
    for (const key of CASE_FILTER_ENV_KEYS) {
      const previousValue = previousValues.get(key);
      if (previousValue === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = previousValue;
      }
    }
  }
}

async function handleRun(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const rawBody = await readJsonBody(request);
  if (!isJsonRecord(rawBody)) {
    throw new Error('request body must be a JSON object');
  }

  const summary = await withRunLock(async () => {
    const config = buildRuntimeConfig(rawBody);
    return withCaseFilterEnv(config.targetCases, () => runRuntimeConfig(config));
  });
  applyRequestRunSnapshot(summary, rawBody);
  if (shouldPersistRunResult(rawBody)) {
    await persistRunSummary(summary);
  }

  sendJson(response, 200, summary);
}

async function handleRunStream(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const rawBody = await readJsonBody(request);
  if (!isJsonRecord(rawBody)) {
    throw new Error('request body must be a JSON object');
  }

  startNdjson(response);

  try {
    const summary = await withRunLock(async () => {
      const config = buildRuntimeConfig(rawBody);
      return withCaseFilterEnv(config.targetCases, () => runRuntimeConfig(config, {
        onProgress: (event) => {
          writeNdjson(response, { type: 'progress', event });
        },
      }));
    });
    applyRequestRunSnapshot(summary, rawBody);
    if (shouldPersistRunResult(rawBody)) {
      await persistRunSummary(summary);
    }
    writeNdjson(response, { type: 'complete', summary });
  } catch (error: unknown) {
    writeNdjson(response, { type: 'error', error: formatError(error) });
  } finally {
    response.end();
  }
}

async function handleCreateJob(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const rawBody = await readJsonBody(request);
  if (!isJsonRecord(rawBody)) {
    throw new Error('request body must be a JSON object');
  }

  const job = createBackendRunJob(normalizeBackendRunJobRequest(rawBody));
  sendJson(response, 202, serializeRunJob(job, false));
}

async function handleListJobs(response: ServerResponse): Promise<void> {
  pruneRunJobs();
  const items = Array.from(runJobs.values())
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
    .slice(0, RUN_JOB_LIST_LIMIT)
    .map((job) => serializeRunJob(job, false));
  sendJson(response, 200, { items });
}

async function handleReadJob(response: ServerResponse, id: string): Promise<void> {
  const job = runJobs.get(id);
  if (!job) {
    sendJson(response, 404, { error: 'job not found' });
    return;
  }
  sendJson(response, 200, serializeRunJob(job));
}

async function handlePersistHistory(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const rawBody = await readJsonBody(request);
  const summary = parseRunSummary(rawBody);
  const entry = await persistRunSummary(summary);
  sendJson(response, 201, { entry });
}

async function handleReadHistory(response: ServerResponse, id: string): Promise<void> {
  const summary = await readHistorySummary(id);
  sendJson(response, 200, summary);
}

async function handleRequest(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const url = new URL(request.url ?? '/', `http://${request.headers.host ?? 'localhost'}`);

  if (request.method === 'OPTIONS') {
    sendNoContent(response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/health') {
    sendJson(response, 200, {
      ok: true,
      service: 'llm-spec-backend',
      agentTests: true,
      backendRun: true,
    });
    return;
  }

  if (request.method === 'GET' && (url.pathname === '/api/history' || url.pathname === '/api/history/')) {
    sendJson(response, 200, { items: await listRunHistory() });
    return;
  }

  if (request.method === 'GET' && (url.pathname === '/api/jobs' || url.pathname === '/api/jobs/')) {
    await handleListJobs(response);
    return;
  }

  if (request.method === 'POST' && (url.pathname === '/api/jobs' || url.pathname === '/api/jobs/')) {
    await handleCreateJob(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname.startsWith('/api/jobs/')) {
    await handleReadJob(response, decodeURIComponent(url.pathname.slice('/api/jobs/'.length)));
    return;
  }

  if (request.method === 'POST' && (url.pathname === '/api/history' || url.pathname === '/api/history/')) {
    await handlePersistHistory(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname.startsWith('/api/history/')) {
    await handleReadHistory(response, decodeURIComponent(url.pathname.slice('/api/history/'.length)));
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/run') {
    await handleRun(request, response);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/run/stream') {
    await handleRunStream(request, response);
    return;
  }

  sendJson(response, 404, { error: 'not found' });
}

const server = createServer((request, response) => {
  handleRequest(request, response).catch((error: unknown) => {
    sendJson(response, 500, { error: formatError(error) });
  });
});

const port = Number(process.env.LLM_SPEC_BACKEND_PORT ?? process.env.PORT ?? DEFAULT_BACKEND_PORT);
const host = process.env.LLM_SPEC_BACKEND_HOST ?? process.env.HOST ?? '0.0.0.0';

server.on('error', (error: Error & { code?: string }) => {
  console.error(`llm-spec backend failed to start: ${error.message}`);
  process.exitCode = 1;
});

server.listen(port, host, () => {
  console.log(`llm-spec backend listening on http://${host}:${port}`);
});
