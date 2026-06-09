import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import type { ProviderName, R9SBillingAuditConfig } from '../../types';

export interface OpenAIProviderConfig {
  provider: 'openai' | 'xai';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  audioModel?: string;
  speechModel?: string;
  transcriptionModel?: string;
  translationModel?: string;
  embeddingModel?: string;
  imageModel?: string;
  imageEditModel?: string;
  dalleModel?: string;
  reasoningModel?: string;
  responsesPromptId?: string;
  fileSearchVectorStoreId?: string;
  customHeaders?: Record<string, string>;
  timeoutMs: number;
}

export interface AnthropicProviderConfig {
  provider: 'anthropic';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  opusModel?: string;
  haikuModel?: string;
  fastModeModel?: string;
  timeoutMs: number;
  container?: string;
  inferenceGeo?: string;
  betas?: string[];
  customHeaders?: Record<string, string>;
}

export interface GeminiProviderConfig {
  provider: 'gemini';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  timeoutMs: number;
  apiVersion?: string;
  cachedContent?: string;
  audioModel?: string;
  imageModel?: string;
  enableVertexOnlyCases: boolean;
  modelArmorPromptTemplate?: string;
  modelArmorResponseTemplate?: string;
  customHeaders?: Record<string, string>;
}

export interface ClaudeAgentProviderConfig {
  provider: 'claude-agent';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  opusModel?: string;
  sonnetModel?: string;
  haikuModel?: string;
  workingDirectory: string;
  skipGitRepoCheck: boolean;
  testImagePath?: string;
  timeoutMs: number;
  customHeaders?: Record<string, string>;
}

export interface CodexProviderConfig {
  provider: 'codex';
  apiKey?: string;
  apiBaseUrl?: string;
  model?: string;
  workingDirectory: string;
  skipGitRepoCheck: boolean;
  testImagePath?: string;
  timeoutMs: number;
}

export type TargetApiType =
  | 'openai.chat'
  | 'openai.responses'
  | 'anthropic.messages'
  | 'gemini.generateContent';

export interface TestTargetConfig {
  apiType: TargetApiType;
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  timeoutMs: number;
  customHeaders?: Record<string, string>;
  apiVersion?: string;
}

export interface RuntimeConfig {
  targetProviders: ProviderName[];
  targetCases?: string;
  failFast: boolean;
  concurrency: number;
  reportFile?: string;
  pluginPaths: string[];
  r9sBillingAudit?: R9SBillingAuditConfig;
  testTarget?: TestTargetConfig;
  openai: OpenAIProviderConfig;
  xai: OpenAIProviderConfig;
  anthropic: AnthropicProviderConfig;
  gemini: GeminiProviderConfig;
  claudeAgent: ClaudeAgentProviderConfig;
  codex: CodexProviderConfig;
}

function loadDotEnvIfPresent(path = '.env'): void {
  const fullPath = findDotEnvPath(path);
  if (!fullPath) {
    return;
  }

  const raw = readFileSync(fullPath, 'utf8');
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    const eqIndex = trimmed.indexOf('=');
    if (eqIndex <= 0) {
      continue;
    }

    const key = trimmed.slice(0, eqIndex).trim();
    if (!key || process.env[key] !== undefined) {
      continue;
    }

    let value = trimmed.slice(eqIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

function findDotEnvPath(path: string): string | undefined {
  if (path !== '.env') {
    const fullPath = resolvePath(process.cwd(), path);
    return existsSync(fullPath) ? fullPath : undefined;
  }

  let currentDir = process.cwd();
  while (true) {
    const fullPath = resolvePath(currentDir, path);
    if (existsSync(fullPath)) {
      return fullPath;
    }

    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) {
      return undefined;
    }
    currentDir = parentDir;
  }
}

function firstNonEmptyEnv(...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = process.env[key];
    if (value && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (!value) {
    return defaultValue;
  }
  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) {
    return true;
  }
  if (['0', 'false', 'no', 'off'].includes(normalized)) {
    return false;
  }
  return defaultValue;
}

function parseNumber(value: string | undefined, defaultValue: number): number {
  if (!value) {
    return defaultValue;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return defaultValue;
  }
  return parsed;
}

function parseCustomHeaders(value: string | undefined): Record<string, string> | undefined {
  if (!value) {
    return undefined;
  }
  try {
    const parsed = JSON.parse(value);
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      const headers: Record<string, string> = {};
      for (const [key, val] of Object.entries(parsed)) {
        if (typeof val === 'string') {
          headers[key] = val;
        }
      }
      return Object.keys(headers).length > 0 ? headers : undefined;
    }
  } catch {
    // invalid JSON, ignore
  }
  return undefined;
}

function parseStringList(value: string | undefined): string[] {
  if (!value) {
    return [];
  }

  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeOptionalModel(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }

  const normalized = value.trim();
  if (!normalized || normalized.toLowerCase() === 'default') {
    return undefined;
  }
  return normalized;
}

function normalizeProviderName(raw: string): ProviderName | undefined {
  const normalized = raw.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  if (normalized === 'openai') {
    return 'openai';
  }
  if (normalized === 'anthropic' || normalized === 'claude') {
    return 'anthropic';
  }
  if (normalized === 'gemini' || normalized === 'google' || normalized === 'genai') {
    return 'gemini';
  }
  if (normalized === 'xai' || normalized === 'grok') {
    return 'xai';
  }
  if (normalized === 'claude-agent' || normalized === 'claudeagent') {
    return 'claude-agent';
  }
  if (normalized === 'codex') {
    return 'codex';
  }
  return undefined;
}

function normalizeTargetApiType(raw: string | undefined): TargetApiType | undefined {
  if (!raw) {
    return undefined;
  }

  const normalized = raw.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }

  if (
    normalized === 'openai.chat' ||
    normalized === 'openai.chatcompletions' ||
    normalized === 'openai.chat_completions' ||
    normalized === 'openai(chatcompletions)' ||
    normalized === 'chat' ||
    normalized === 'chatcompletions'
  ) {
    return 'openai.chat';
  }

  if (
    normalized === 'openai.responses' ||
    normalized === 'openai(responses)' ||
    normalized === 'responses'
  ) {
    return 'openai.responses';
  }

  if (
    normalized === 'anthropic.messages' ||
    normalized === 'anthropic.message' ||
    normalized === 'messages' ||
    normalized === 'claude.messages' ||
    normalized === 'claude.message'
  ) {
    return 'anthropic.messages';
  }

  if (
    normalized === 'gemini.generatecontent' ||
    normalized === 'gemini.generate_content' ||
    normalized === 'gemini' ||
    normalized === 'google.generatecontent' ||
    normalized === 'genai.generatecontent'
  ) {
    return 'gemini.generateContent';
  }

  return undefined;
}

function resolveTargetProviders(raw: string | undefined): ProviderName[] {
  const fallback: ProviderName[] = ['openai', 'anthropic', 'gemini'];
  if (!raw) {
    return fallback;
  }

  const set = new Set<ProviderName>();
  for (const item of raw.split(',')) {
    const provider = normalizeProviderName(item);
    if (provider) {
      set.add(provider);
    }
  }

  if (set.size === 0) {
    return fallback;
  }
  return Array.from(set);
}

function resolveWorkingDirectory(envKey: string): string {
  const dir = firstNonEmptyEnv(envKey);
  if (dir) {
    return dir;
  }
  return process.cwd();
}

function resolveTestTarget(
  rawApiType: string | undefined,
  openai: OpenAIProviderConfig,
  anthropic: AnthropicProviderConfig,
  gemini: GeminiProviderConfig,
  defaultTimeoutMs: number,
): TestTargetConfig | undefined {
  const apiType = normalizeTargetApiType(rawApiType);
  if (!apiType) {
    return undefined;
  }

  if (apiType === 'openai.chat' || apiType === 'openai.responses') {
    return {
      apiType,
      apiKey: firstNonEmptyEnv('TEST_API_KEY', 'TEST_KEY', 'OPENAI_API_KEY', 'API_KEY') ?? openai.apiKey,
      apiBaseUrl:
        firstNonEmptyEnv('TEST_API_BASE_URL', 'TEST_BASE_URL', 'OPENAI_API_BASE_URL', 'OPENAI_BASE_URL', 'BASE_URL', 'API_BASE_URL')
        ?? openai.apiBaseUrl,
      model: firstNonEmptyEnv('TEST_MODEL', 'MODEL', 'OPENAI_MODEL') ?? openai.model,
      timeoutMs: parseNumber(
        firstNonEmptyEnv('TEST_TIMEOUT_MS', 'OPENAI_TIMEOUT_MS', 'TIMEOUT_MS'),
        openai.timeoutMs || defaultTimeoutMs,
      ),
      customHeaders:
        parseCustomHeaders(firstNonEmptyEnv('TEST_CUSTOM_HEADERS', 'CUSTOM_HEADERS', 'OPENAI_CUSTOM_HEADERS'))
        ?? openai.customHeaders,
    };
  }

  if (apiType === 'anthropic.messages') {
    return {
      apiType,
      apiKey:
        firstNonEmptyEnv('TEST_API_KEY', 'TEST_KEY', 'ANTHROPIC_API_KEY', 'API_KEY')
        ?? anthropic.apiKey,
      apiBaseUrl:
        firstNonEmptyEnv(
          'TEST_API_BASE_URL',
          'TEST_BASE_URL',
          'ANTHROPIC_API_BASE_URL',
          'ANTHROPIC_BASE_URL',
          'BASE_URL',
          'API_BASE_URL',
        )
        ?? anthropic.apiBaseUrl,
      model: firstNonEmptyEnv('TEST_MODEL', 'MODEL', 'ANTHROPIC_MODEL') ?? anthropic.model,
      timeoutMs: parseNumber(
        firstNonEmptyEnv('TEST_TIMEOUT_MS', 'ANTHROPIC_TIMEOUT_MS', 'TIMEOUT_MS'),
        anthropic.timeoutMs || defaultTimeoutMs,
      ),
      customHeaders:
        parseCustomHeaders(firstNonEmptyEnv('TEST_CUSTOM_HEADERS', 'CUSTOM_HEADERS', 'ANTHROPIC_CUSTOM_HEADERS'))
        ?? anthropic.customHeaders,
    };
  }

  return {
    apiType,
    apiKey:
      firstNonEmptyEnv(
        'TEST_API_KEY',
        'TEST_KEY',
        'GEMINI_API_KEY',
        'GOOGLE_API_KEY',
        'GOOGLE_AI_API_KEY',
        'API_KEY',
      )
      ?? gemini.apiKey,
    apiBaseUrl:
      firstNonEmptyEnv(
        'TEST_API_BASE_URL',
        'TEST_BASE_URL',
        'GEMINI_API_BASE_URL',
        'GOOGLE_API_BASE_URL',
        'BASE_URL',
        'API_BASE_URL',
      )
      ?? gemini.apiBaseUrl,
    model: firstNonEmptyEnv('TEST_MODEL', 'MODEL', 'GEMINI_MODEL') ?? gemini.model,
    timeoutMs: parseNumber(
      firstNonEmptyEnv('TEST_TIMEOUT_MS', 'GEMINI_TIMEOUT_MS', 'TIMEOUT_MS'),
      gemini.timeoutMs || defaultTimeoutMs,
    ),
    apiVersion: firstNonEmptyEnv('TEST_API_VERSION', 'GEMINI_API_VERSION', 'GOOGLE_API_VERSION', 'API_VERSION')
      ?? gemini.apiVersion,
    customHeaders:
      parseCustomHeaders(firstNonEmptyEnv('TEST_CUSTOM_HEADERS', 'CUSTOM_HEADERS', 'GEMINI_CUSTOM_HEADERS', 'GOOGLE_CUSTOM_HEADERS'))
      ?? gemini.customHeaders,
  };
}

export function resolveRuntimeConfig(): RuntimeConfig {
  loadDotEnvIfPresent();

  const rawTargetApiType = firstNonEmptyEnv('TEST_API_TYPE', 'API_TYPE');
  const targetCases = firstNonEmptyEnv('TARGET_CASES', 'TEST_CASES', 'CASE_IDS');
  const failFast = false;
  const concurrency = parseNumber(firstNonEmptyEnv('SDK_CONCURRENCY'), 1);
  const reportFile = firstNonEmptyEnv('REPORT_FILE');
  const pluginPaths = parseStringList(firstNonEmptyEnv('LLM_SPEC_PLUGINS', 'TEST_PLUGINS'));
  const r9sBillingAuditEnabled = parseBoolean(firstNonEmptyEnv('R9S_BILLING_AUDIT', 'R9S_BILLING_AUDIT_ENABLED'), false);
  const r9sBillingAudit: R9SBillingAuditConfig | undefined = r9sBillingAuditEnabled
    ? {
        enabled: true,
        managerBaseUrl: firstNonEmptyEnv('R9S_MANAGER_BASE_URL', 'R9S_MANAGER_API_BASE_URL'),
        managerKey: firstNonEmptyEnv('R9S_MANAGER_KEY', 'R9S_MANAGER_API_KEY'),
        apiKey: firstNonEmptyEnv('TEST_API_KEY', 'TEST_KEY', 'API_KEY'),
        tokenId: firstNonEmptyEnv('R9S_TOKEN_ID', 'R9S_API_TOKEN_ID'),
      }
    : undefined;

  const defaultTimeoutMs = parseNumber(firstNonEmptyEnv('SDK_TIMEOUT_MS'), 45_000);

  const openai: OpenAIProviderConfig = {
    provider: 'openai',
    apiKey: firstNonEmptyEnv('OPENAI_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv('OPENAI_API_BASE_URL', 'OPENAI_BASE_URL', 'API_BASE_URL'),
    model: firstNonEmptyEnv('OPENAI_MODEL') ?? 'gpt-4o-mini',
    audioModel: firstNonEmptyEnv('OPENAI_AUDIO_MODEL'),
    speechModel: firstNonEmptyEnv('OPENAI_SPEECH_MODEL') ?? 'gpt-4o-mini-tts',
    transcriptionModel: firstNonEmptyEnv('OPENAI_TRANSCRIPTION_MODEL') ?? 'gpt-4o-mini-transcribe',
    translationModel: firstNonEmptyEnv('OPENAI_TRANSLATION_MODEL') ?? 'whisper-1',
    embeddingModel: firstNonEmptyEnv('OPENAI_EMBEDDING_MODEL') ?? 'text-embedding-3-small',
    imageModel: firstNonEmptyEnv('OPENAI_IMAGE_MODEL') ?? 'gpt-image-1.5',
    imageEditModel: firstNonEmptyEnv('OPENAI_IMAGE_EDIT_MODEL') ?? 'gpt-image-1.5',
    dalleModel: firstNonEmptyEnv('OPENAI_DALLE_MODEL') ?? 'dall-e-3',
    reasoningModel: firstNonEmptyEnv('OPENAI_REASONING_MODEL'),
    responsesPromptId: firstNonEmptyEnv('OPENAI_RESPONSES_PROMPT_ID'),
    fileSearchVectorStoreId: firstNonEmptyEnv('OPENAI_FILE_SEARCH_VECTOR_STORE_ID'),
    customHeaders: parseCustomHeaders(firstNonEmptyEnv('CUSTOM_HEADERS', 'OPENAI_CUSTOM_HEADERS')),
    timeoutMs: parseNumber(firstNonEmptyEnv('OPENAI_TIMEOUT_MS'), defaultTimeoutMs),
  };

  const xai: OpenAIProviderConfig = {
    provider: 'xai',
    apiKey: firstNonEmptyEnv('XAI_API_KEY', 'X_AI_API_KEY', 'API_KEY'),
    apiBaseUrl:
      firstNonEmptyEnv('XAI_API_BASE_URL', 'X_AI_API_BASE_URL') ?? 'https://api.x.ai/v1',
    model: firstNonEmptyEnv('XAI_MODEL', 'X_AI_MODEL') ?? 'grok-beta',
    customHeaders: parseCustomHeaders(firstNonEmptyEnv('CUSTOM_HEADERS', 'XAI_CUSTOM_HEADERS')),
    timeoutMs: parseNumber(firstNonEmptyEnv('XAI_TIMEOUT_MS'), defaultTimeoutMs),
  };

  const anthropic: AnthropicProviderConfig = {
    provider: 'anthropic',
    apiKey: firstNonEmptyEnv('ANTHROPIC_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv('ANTHROPIC_API_BASE_URL', 'ANTHROPIC_BASE_URL', 'API_BASE_URL'),
    model: firstNonEmptyEnv('ANTHROPIC_MODEL') ?? 'claude-3-5-haiku-latest',
    opusModel: firstNonEmptyEnv('ANTHROPIC_OPUS_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL'),
    haikuModel: firstNonEmptyEnv('ANTHROPIC_HAIKU_MODEL'),
    fastModeModel: firstNonEmptyEnv('ANTHROPIC_FAST_MODE_MODEL', 'ANTHROPIC_OPUS_MODEL'),
    timeoutMs: parseNumber(firstNonEmptyEnv('ANTHROPIC_TIMEOUT_MS'), defaultTimeoutMs),
    container: firstNonEmptyEnv('ANTHROPIC_CONTAINER'),
    inferenceGeo: firstNonEmptyEnv('ANTHROPIC_INFERENCE_GEO'),
    betas: firstNonEmptyEnv('ANTHROPIC_BETAS')?.split(',').map((beta) => beta.trim()).filter(Boolean),
    customHeaders: parseCustomHeaders(firstNonEmptyEnv('CUSTOM_HEADERS', 'ANTHROPIC_CUSTOM_HEADERS')),
  };

  const gemini: GeminiProviderConfig = {
    provider: 'gemini',
    apiKey: firstNonEmptyEnv('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'GOOGLE_AI_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv('GEMINI_API_BASE_URL', 'GOOGLE_API_BASE_URL', 'API_BASE_URL'),
    model: firstNonEmptyEnv('GEMINI_MODEL') ?? 'gemini-2.5-flash',
    timeoutMs: parseNumber(firstNonEmptyEnv('GEMINI_TIMEOUT_MS'), defaultTimeoutMs),
    apiVersion: firstNonEmptyEnv('GEMINI_API_VERSION', 'GOOGLE_API_VERSION'),
    cachedContent: firstNonEmptyEnv('GEMINI_CACHED_CONTENT'),
    audioModel: firstNonEmptyEnv('GEMINI_AUDIO_MODEL'),
    imageModel: firstNonEmptyEnv('GEMINI_IMAGE_MODEL'),
    enableVertexOnlyCases: parseBoolean(firstNonEmptyEnv('GEMINI_ENABLE_VERTEX_ONLY_CASES'), false),
    modelArmorPromptTemplate: firstNonEmptyEnv('GEMINI_MODEL_ARMOR_PROMPT_TEMPLATE'),
    modelArmorResponseTemplate: firstNonEmptyEnv('GEMINI_MODEL_ARMOR_RESPONSE_TEMPLATE'),
    customHeaders: parseCustomHeaders(firstNonEmptyEnv('CUSTOM_HEADERS', 'GEMINI_CUSTOM_HEADERS', 'GOOGLE_CUSTOM_HEADERS')),
  };

  const claudeAgent: ClaudeAgentProviderConfig = {
    provider: 'claude-agent',
    apiKey: firstNonEmptyEnv('CLAUDE_AGENT_API_KEY', 'ANTHROPIC_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv(
      'CLAUDE_AGENT_API_BASE_URL',
      'ANTHROPIC_API_BASE_URL',
      'ANTHROPIC_BASE_URL',
      'API_BASE_URL',
    ),
    model: firstNonEmptyEnv('CLAUDE_AGENT_MODEL', 'ANTHROPIC_MODEL') ?? '',
    opusModel: firstNonEmptyEnv('CLAUDE_AGENT_OPUS_MODEL', 'ANTHROPIC_OPUS_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL'),
    sonnetModel: firstNonEmptyEnv('CLAUDE_AGENT_SONNET_MODEL', 'ANTHROPIC_SONNET_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL'),
    haikuModel: firstNonEmptyEnv('CLAUDE_AGENT_HAIKU_MODEL', 'ANTHROPIC_HAIKU_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'),
    workingDirectory: resolveWorkingDirectory('CLAUDE_AGENT_WORKING_DIRECTORY'),
    skipGitRepoCheck: parseBoolean(firstNonEmptyEnv('CLAUDE_AGENT_SKIP_GIT_REPO_CHECK'), true),
    testImagePath: firstNonEmptyEnv('CLAUDE_AGENT_TEST_IMAGE_PATH'),
    timeoutMs: parseNumber(firstNonEmptyEnv('CLAUDE_AGENT_TIMEOUT_MS'), defaultTimeoutMs),
    customHeaders: parseCustomHeaders(
      firstNonEmptyEnv('CUSTOM_HEADERS', 'CLAUDE_AGENT_CUSTOM_HEADERS', 'ANTHROPIC_CUSTOM_HEADERS'),
    ),
  };

  const codex: CodexProviderConfig = {
    provider: 'codex',
    apiKey: firstNonEmptyEnv('CODEX_API_KEY', 'OPENAI_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv(
      'CODEX_API_BASE_URL',
      'OPENAI_API_BASE_URL',
      'OPENAI_BASE_URL',
      'API_BASE_URL',
    ),
    model: normalizeOptionalModel(firstNonEmptyEnv('CODEX_MODEL')),
    workingDirectory: resolveWorkingDirectory('CODEX_WORKING_DIRECTORY'),
    skipGitRepoCheck: parseBoolean(firstNonEmptyEnv('CODEX_SKIP_GIT_REPO_CHECK'), true),
    testImagePath: firstNonEmptyEnv('CODEX_TEST_IMAGE_PATH'),
    timeoutMs: parseNumber(firstNonEmptyEnv('CODEX_TIMEOUT_MS'), defaultTimeoutMs),
  };

  const testTarget = resolveTestTarget(
    rawTargetApiType,
    openai,
    anthropic,
    gemini,
    defaultTimeoutMs,
  );
  const targetProviders = testTarget
    ? []
    : resolveTargetProviders(firstNonEmptyEnv('TARGET_PROVIDERS', 'PROVIDERS', 'PROVIDER'));

  return {
    targetProviders,
    targetCases,
    failFast,
    concurrency,
    reportFile,
    pluginPaths,
    r9sBillingAudit,
    testTarget,
    openai,
    xai,
    anthropic,
    gemini,
    claudeAgent,
    codex,
  };
}
