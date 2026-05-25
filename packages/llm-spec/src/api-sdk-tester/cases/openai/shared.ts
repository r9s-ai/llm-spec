import type OpenAI from 'openai';

import type { OpenAIProviderConfig } from '../../environment';
import { IMAGE_INPUT_FIXTURES, createFixtureDataUri } from '../../fixtures';
import { formatError } from '../runtime';

export const OPENAI_CHAT_PARAMS = [
  'messages',
  'model',
  'audio',
  'frequency_penalty',
  'function_call',
  'functions',
  'logit_bias',
  'logprobs',
  'max_completion_tokens',
  'max_tokens',
  'metadata',
  'modalities',
  'n',
  'parallel_tool_calls',
  'prediction',
  'presence_penalty',
  'prompt_cache_key',
  'prompt_cache_retention',
  'reasoning_effort',
  'response_format',
  'safety_identifier',
  'seed',
  'service_tier',
  'stop',
  'store',
  'stream',
  'stream_options',
  'temperature',
  'tool_choice',
  'tools',
  'top_logprobs',
  'top_p',
  'user',
  'verbosity',
  'web_search_options',
] as const;

export interface OpenAICaseContext {
  client: OpenAI;
  config: OpenAIProviderConfig;
}

function normalizeModelName(model: string): string {
  return model.trim().toLowerCase();
}

export function isOSeriesModel(model: string): boolean {
  return /^o\d/.test(normalizeModelName(model));
}

export function isO3OrO4MiniModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('o3') || normalized.startsWith('o4-mini');
}

export function isGpt5SeriesModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5');
}

export function isGpt5NanoModel(model: string): boolean {
  return /^gpt-5(?:\.\d+)?-nano(?:-|$)/.test(normalizeModelName(model));
}

export function isGpt4oOrNewerModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return (
    normalized.startsWith('gpt-4o') ||
    normalized.startsWith('gpt-5') ||
    isOSeriesModel(normalized)
  );
}

export function isReasoningModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('gpt-5') || isOSeriesModel(model);
}

export function resolveChatCompletionOutputLimit(_model: string, requested: number): number {
  // Keep chat.completions budgets high enough that visible output survives internal reasoning/planning token spend.
  return Math.max(requested, 1024);
}

export function resolveOpenAIChatSamplingParams(model: string) {
  return isGpt5NanoModel(model)
    ? {
        temperature: 1,
        top_p: 1,
        presence_penalty: 0,
        frequency_penalty: 0,
      }
    : {
        temperature: 0.2,
        top_p: 0.9,
        presence_penalty: 0.1,
        frequency_penalty: 0.1,
      };
}

export function resolveOpenAIResponsesSamplingParams(model: string) {
  return isGpt5NanoModel(model)
    ? {
        temperature: 1,
        top_p: 1,
      }
    : {
        temperature: 0.2,
        top_p: 0.9,
      };
}

export function resolveOpenAINChoices(model: string, requested: number): number {
  return isGpt5NanoModel(model) ? 1 : requested;
}

export function skipGpt5NanoNChoiceFanout(model: string, feature: string): string | undefined {
  return isGpt5NanoModel(model)
    ? `model ${model} has fixed beta sampling limits with n=1; skip ${feature}`
    : undefined;
}

function isGpt5ProModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5-pro');
}

export function isLikelyAudioOutputModel(model: string): boolean {
  return normalizeModelName(model).includes('audio');
}

export function isOpenAICompatibilityGateway(apiBaseUrl: string | undefined): boolean {
  if (!apiBaseUrl) {
    return false;
  }

  try {
    const hostname = new URL(apiBaseUrl).hostname.toLowerCase();
    return !(hostname === 'api.openai.com' || hostname.endsWith('.openai.com'));
  } catch {
    return false;
  }
}

function isGeminiModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gemini-');
}

export function isGeminiOpenAICompatibilityTarget(model: string): boolean {
  return isGeminiModel(model);
}

export type PromptCacheRetentionValue = 'in-memory' | 'in_memory';

export const OPENAI_IMAGE_DATA_URI_FIXTURES = IMAGE_INPUT_FIXTURES.map((fixture) => ({
  ...fixture,
  get dataUri() {
    return createFixtureDataUri(fixture.mimeType, fixture.fileName);
  },
}));

function isPromptCacheRetentionValueError(error: unknown): boolean {
  const message = formatError(error).toLowerCase();
  const mentionsLegacyValue = message.includes('in-memory');
  const mentionsSnakeValue = message.includes('in_memory');
  return (
    (message.includes('prompt_cache_retention') || message.includes('invalid value')) &&
    mentionsLegacyValue &&
    mentionsSnakeValue
  );
}

export function resolveReasoningEffort(model: string): 'none' | 'low' | 'high' {
  const normalized = normalizeModelName(model);
  if (isGpt5ProModel(normalized)) {
    return 'high';
  }
  if (normalized.startsWith('gpt-5.1')) {
    return 'none';
  }
  return 'low';
}

export function createBaseMessages(model: string) {
  const instructionRole = isReasoningModel(model) ? 'developer' : 'system';
  return [
    {
      role: instructionRole as 'developer' | 'system',
      content: 'You are a compatibility tester. Keep output short.',
    },
    { role: 'user' as const, content: 'Reply with exactly: ok' },
  ];
}

export async function withPromptCacheRetentionFallback<T>(
  runWithRetention: (retention: PromptCacheRetentionValue) => Promise<T>,
  preferredRetention: PromptCacheRetentionValue = 'in-memory',
): Promise<T> {
  const fallbackRetention: PromptCacheRetentionValue =
    preferredRetention === 'in-memory' ? 'in_memory' : 'in-memory';
  try {
    return await runWithRetention(preferredRetention);
  } catch (error) {
    if (!isPromptCacheRetentionValueError(error)) {
      throw error;
    }
    return runWithRetention(fallbackRetention);
  }
}

export function createOpenAIChatSharedState({ config }: OpenAICaseContext) {
  const chatReasoningModel = config.reasoningModel ?? config.model;
  const audioOutputModel = config.audioModel ?? config.model;
  const compatibilityGateway = isOpenAICompatibilityGateway(config.apiBaseUrl);
  const geminiCompatibilityTarget = isGeminiOpenAICompatibilityTarget(config.model);

  const baseMessages = createBaseMessages(config.model);
  const chatReasoningMessages = createBaseMessages(chatReasoningModel);
  const chatStreamOptions = compatibilityGateway
    ? { include_usage: true }
    : { include_usage: true, include_obfuscation: false };

  const jsonPrompt = [
    {
      role: 'user',
      content: 'Return a JSON object only: {"ok": true, "source": "openai"}',
    },
  ] as const;

  const functionSchema = {
    type: 'object',
    properties: {
      text: { type: 'string' },
    },
    required: ['text'],
    additionalProperties: false,
  };

  const functionTool = {
    type: 'function',
    function: {
      name: 'echo',
      description: 'Echo back input',
      parameters: functionSchema,
    },
  } as const;

  function skipOpenAIOnlyCaseOnGemini(feature: string): string | undefined {
    return geminiCompatibilityTarget
      ? `Gemini OpenAI compatibility docs do not promise ${feature}; skip generic OpenAI-only coverage`
      : undefined;
  }

  return {
    audioOutputModel,
    baseMessages,
    chatReasoningMessages,
    chatReasoningModel,
    chatStreamOptions,
    compatibilityGateway,
    functionSchema,
    functionTool,
    geminiCompatibilityTarget,
    jsonPrompt,
    skipOpenAIOnlyCaseOnGemini,
  };
}
