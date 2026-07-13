import type OpenAI from 'openai';

import type { OpenAIProviderConfig } from '../../environment';
import { IMAGE_INPUT_FIXTURES, createFixtureDataUri } from '../../fixtures';
import {
  isGeminiOpenAICompatibilityTarget,
  isGpt5NanoModel,
  isOpenAICompatibilityGateway,
  isReasoningModel,
} from '../model-capabilities';
import { formatError } from '../runtime';

export {
  isGeminiOpenAICompatibilityTarget,
  isGpt5NanoModel,
  isGpt5SeriesModel,
  isGpt4oOrNewerModel,
  isLikelyAudioOutputModel,
  isO3OrO4MiniModel,
  isOpenAICompatibilityGateway,
  isOSeriesModel,
  isReasoningModel,
  resolveReasoningEffort,
} from '../model-capabilities';

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
  'prompt_cache_breakpoint',
  'prompt_cache_key',
  'prompt_cache_options',
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

export type PromptCacheRetentionValue = 'in_memory' | '24h' | 'in-memory';

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
  preferredRetention: PromptCacheRetentionValue = 'in_memory',
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
