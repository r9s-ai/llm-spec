import { randomUUID } from 'node:crypto';
import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { basename, resolve as resolvePath } from 'node:path';

import { formatError, resolveRuntimeConfig } from './api-sdk-tester';
import type { RuntimeConfig, TargetApiType } from './api-sdk-tester';
import { runRuntimeConfig } from './runner';
import type { RunSummary, RunSnapshot } from './types';

type JsonRecord = Record<string, unknown>;
type AgentProvider = 'claude-agent' | 'codex';

const BODY_LIMIT_BYTES = 64 * 1024 * 1024;
const DEFAULT_BACKEND_PORT = 8788;
const RUN_HISTORY_DIR = resolvePath(process.cwd(), process.env.LLM_SPEC_HISTORY_DIR ?? '.llm-spec-history');
const RUN_HISTORY_ID_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_-]*$/;
const RUN_HISTORY_LIST_LIMIT = 200;

const CASE_FILTER_ENV_KEYS = ['TARGET_CASES', 'TEST_CASES', 'CASE_IDS'] as const;

let runQueue: Promise<void> = Promise.resolve();

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

function applyRequestRunSnapshot(summary: RunSummary, rawBody: JsonRecord): void {
  const runSnapshot = optionalRunSnapshot(rawBody);
  if (runSnapshot) {
    summary.runSnapshot = runSnapshot;
  }
}

function shouldPersistRunResult(rawBody: JsonRecord): boolean {
  return optionalBoolean(rawBody, 'persistResult') ?? true;
}

async function withRunLock<T>(action: () => Promise<T>): Promise<T> {
  const previous = runQueue.catch(() => undefined);
  let release!: () => void;
  runQueue = new Promise<void>((resolve) => {
    release = resolve;
  });

  await previous;
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
