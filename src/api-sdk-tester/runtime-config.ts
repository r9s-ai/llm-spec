import { existsSync, readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';

import type { ProviderName } from '../types';

export interface OpenAIProviderConfig {
  provider: 'openai';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  audioModel?: string;
  reasoningModel?: string;
  responsesPromptId?: string;
  timeoutMs: number;
}

export interface AnthropicProviderConfig {
  provider: 'anthropic';
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  timeoutMs: number;
  container?: string;
  inferenceGeo?: string;
  betas?: string[];
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
}

export interface ClaudeAgentProviderConfig {
  provider: 'claude-agent';
  apiKey?: string;
  apiBaseUrl?: string;
  workingDirectory: string;
  skipGitRepoCheck: boolean;
  testImagePath?: string;
  timeoutMs: number;
}

export interface CodexProviderConfig {
  provider: 'codex';
  apiKey?: string;
  apiBaseUrl?: string;
  workingDirectory: string;
  skipGitRepoCheck: boolean;
  testImagePath?: string;
  timeoutMs: number;
}

export interface RuntimeConfig {
  targetProviders: ProviderName[];
  failFast: boolean;
  reportFile?: string;
  openai: OpenAIProviderConfig;
  anthropic: AnthropicProviderConfig;
  gemini: GeminiProviderConfig;
  claudeAgent: ClaudeAgentProviderConfig;
  codex: CodexProviderConfig;
}

function loadDotEnvIfPresent(path = '.env'): void {
  const fullPath = resolvePath(process.cwd(), path);
  if (!existsSync(fullPath)) {
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
  if (normalized === 'claude-agent' || normalized === 'claudeagent') {
    return 'claude-agent';
  }
  if (normalized === 'codex') {
    return 'codex';
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
  // 默认使用当前工作目录
  return process.cwd();
}

export function resolveRuntimeConfig(): RuntimeConfig {
  loadDotEnvIfPresent();

  const targetProviders = resolveTargetProviders(
    firstNonEmptyEnv('TARGET_PROVIDERS', 'PROVIDERS', 'PROVIDER'),
  );
  const failFast = parseBoolean(firstNonEmptyEnv('FAIL_FAST'), false);
  const reportFile = firstNonEmptyEnv('REPORT_FILE');

  const defaultTimeoutMs = parseNumber(firstNonEmptyEnv('SDK_TIMEOUT_MS'), 45_000);

  const openai: OpenAIProviderConfig = {
    provider: 'openai',
    apiKey: firstNonEmptyEnv('OPENAI_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv('OPENAI_API_BASE_URL', 'OPENAI_BASE_URL', 'API_BASE_URL'),
    model: firstNonEmptyEnv('OPENAI_MODEL') ?? 'gpt-4o-mini',
    audioModel: firstNonEmptyEnv('OPENAI_AUDIO_MODEL'),
    reasoningModel: firstNonEmptyEnv('OPENAI_REASONING_MODEL'),
    responsesPromptId: firstNonEmptyEnv('OPENAI_RESPONSES_PROMPT_ID'),
    timeoutMs: parseNumber(firstNonEmptyEnv('OPENAI_TIMEOUT_MS'), defaultTimeoutMs),
  };

  const anthropic: AnthropicProviderConfig = {
    provider: 'anthropic',
    apiKey: firstNonEmptyEnv('ANTHROPIC_API_KEY', 'API_KEY'),
    apiBaseUrl: firstNonEmptyEnv('ANTHROPIC_API_BASE_URL', 'ANTHROPIC_BASE_URL', 'API_BASE_URL'),
    model: firstNonEmptyEnv('ANTHROPIC_MODEL') ?? 'claude-3-5-haiku-latest',
    timeoutMs: parseNumber(firstNonEmptyEnv('ANTHROPIC_TIMEOUT_MS'), defaultTimeoutMs),
    container: firstNonEmptyEnv('ANTHROPIC_CONTAINER'),
    inferenceGeo: firstNonEmptyEnv('ANTHROPIC_INFERENCE_GEO'),
    betas: firstNonEmptyEnv('ANTHROPIC_BETAS')?.split(',').map((b) => b.trim()).filter(Boolean),
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
    workingDirectory: resolveWorkingDirectory('CLAUDE_AGENT_WORKING_DIRECTORY'),
    skipGitRepoCheck: parseBoolean(firstNonEmptyEnv('CLAUDE_AGENT_SKIP_GIT_REPO_CHECK'), true),
    testImagePath: firstNonEmptyEnv('CLAUDE_AGENT_TEST_IMAGE_PATH'),
    timeoutMs: parseNumber(firstNonEmptyEnv('CLAUDE_AGENT_TIMEOUT_MS'), defaultTimeoutMs),
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
    workingDirectory: resolveWorkingDirectory('CODEX_WORKING_DIRECTORY'),
    skipGitRepoCheck: parseBoolean(firstNonEmptyEnv('CODEX_SKIP_GIT_REPO_CHECK'), true),
    testImagePath: firstNonEmptyEnv('CODEX_TEST_IMAGE_PATH'),
    timeoutMs: parseNumber(firstNonEmptyEnv('CODEX_TIMEOUT_MS'), defaultTimeoutMs),
  };

  return {
    targetProviders,
    failFast,
    reportFile,
    openai,
    anthropic,
    gemini,
    claudeAgent,
    codex,
  };
}
