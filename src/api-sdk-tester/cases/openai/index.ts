import type OpenAI from 'openai';
import {
  Codex,
  type Input as CodexInput,
  type Thread,
  type TurnOptions as CodexTurnOptions,
} from '@openai/codex-sdk';

import type { OpenAIProviderConfig, CodexProviderConfig } from '../../environment';
import {
  formatError,
  summarizeOpenAIResponse,
  summarizeOpenAIResponses,
  truncate,
} from '../runtime';
import type { TestCase } from '../types';
import { defineCases } from '../define-cases';

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

export const OPENAI_RESPONSES_PARAMS = [
  'background',
  'context_management',
  'conversation',
  'include',
  'input',
  'instructions',
  'max_output_tokens',
  'max_tool_calls',
  'metadata',
  'model',
  'parallel_tool_calls',
  'previous_response_id',
  'prompt',
  'prompt_cache_key',
  'prompt_cache_retention',
  'reasoning',
  'safety_identifier',
  'service_tier',
  'store',
  'stream',
  'stream_options',
  'temperature',
  'text',
  'tool_choice',
  'tools',
  'top_logprobs',
  'top_p',
  'truncation',
  'user',
] as const;

export const OPENAI_PARAMS = Array.from(
  new Set<string>([...OPENAI_CHAT_PARAMS, ...OPENAI_RESPONSES_PARAMS]),
);

export const CODEX_PARAMS = [
  'prompt',
  'outputSchema',
  'workingDirectory',
  'skipGitRepoCheck',
  'config',
  'env',
  'streaming',
] as const;

export interface OpenAICaseContext {
  client: OpenAI;
  config: OpenAIProviderConfig;
}

export interface CodexCaseContext {
  client: Codex;
  config: CodexProviderConfig;
}

function normalizeModelName(model: string): string {
  return model.trim().toLowerCase();
}

function isOSeriesModel(model: string): boolean {
  return /^o\d/.test(normalizeModelName(model));
}

function isO3OrO4MiniModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('o3') || normalized.startsWith('o4-mini');
}

function isGpt5SeriesModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5');
}

function isGpt4oOrNewerModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  // gpt-4o, gpt-4o-mini, gpt-5, o-series are all considered "newer" models
  return (
    normalized.startsWith('gpt-4o') ||
    normalized.startsWith('gpt-5') ||
    isOSeriesModel(normalized)
  );
}

function isReasoningModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('gpt-5') || isOSeriesModel(model);
}

function isGpt5ProModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5-pro');
}

function isLikelyAudioOutputModel(model: string): boolean {
  return normalizeModelName(model).includes('audio');
}

function isOpenAICompatibilityGateway(apiBaseUrl: string | undefined): boolean {
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

type PromptCacheRetentionValue = 'in-memory' | 'in_memory';

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

function resolveReasoningEffort(model: string): 'none' | 'low' | 'high' {
  const normalized = normalizeModelName(model);
  if (isGpt5ProModel(normalized)) {
    return 'high';
  }
  if (normalized.startsWith('gpt-5.1')) {
    return 'none';
  }
  return 'low';
}

function createBaseMessages(model: string) {
  const instructionRole = isReasoningModel(model) ? 'developer' : 'system';
  return [
    {
      role: instructionRole as 'developer' | 'system',
      content: 'You are a compatibility tester. Keep output short.',
    },
    { role: 'user' as const, content: 'Reply with exactly: ok' },
  ];
}

export interface OpenAICaseContext {
  client: OpenAI;
  config: OpenAIProviderConfig;
}

export function buildOpenAICases(
  { client, config }: OpenAICaseContext,
  filter?: 'chatCompletions' | 'responses',
): TestCase[] {
  const chatReasoningModel = config.reasoningModel ?? config.model;
  const responsesReasoningModel = config.reasoningModel ?? config.model;
  const audioOutputModel = config.audioModel ?? config.model;
  const compatibilityGateway = isOpenAICompatibilityGateway(config.apiBaseUrl);

  const baseMessages = createBaseMessages(config.model);
  const chatReasoningMessages = createBaseMessages(chatReasoningModel);

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

  async function withPromptCacheRetentionFallback<T>(
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

  const cases = defineCases({
    'basic': {
      description: 'basic chat completion',
      covers: ['messages', 'model'],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'sampling_and_max_completion': {
      description: 'temperature/top_p/penalties/max_completion_tokens',
      covers: [
        'temperature',
        'top_p',
        'presence_penalty',
        'frequency_penalty',
        'max_completion_tokens',
      ],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          temperature: 0.2,
          top_p: 0.9,
          presence_penalty: 0.1,
          frequency_penalty: 0.1,
          max_completion_tokens: 32,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'n_choices': {
      description: 'n parameter for multiple choices',
      covers: ['n'],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          n: 2,
          max_completion_tokens: 16,
        });
        const choicesCount = response.choices?.length ?? 0;
        return `choices=${choicesCount}`;
      },
    },
    'max_tokens_legacy': {
      description: 'legacy max_tokens',
      covers: ['max_tokens'],
      precondition: () =>
        isGpt5SeriesModel(config.model) || isOSeriesModel(config.model)
          ? `model ${config.model} uses max_completion_tokens; skip legacy max_tokens test`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_tokens: 32,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'stop_sequences': {
      description: 'stop',
      covers: ['stop'],
      precondition: () => {
        if (isO3OrO4MiniModel(config.model)) {
          return `model ${config.model}; docs mark stop as unsupported for o3/o4-mini`;
        }
        if (compatibilityGateway && isGpt5SeriesModel(config.model)) {
          return `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects stop for ${config.model}`;
        }
        return undefined;
      },
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 32,
          stop: ['\n'],
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'identity_metadata_caching': {
      description: 'metadata/user/safety/cache/seed/service_tier/store/n',
      covers: [
        'metadata',
        'user',
        'safety_identifier',
        'prompt_cache_key',
        'prompt_cache_retention',
        'seed',
        'service_tier',
        'store',
        'n',
      ],
      run: async () => {
        const preferredRetention: PromptCacheRetentionValue = compatibilityGateway
          ? 'in_memory'
          : 'in-memory';
        const response = await withPromptCacheRetentionFallback((retention) =>
          client.chat.completions.create(
            {
              model: config.model,
              messages: [...baseMessages],
              max_completion_tokens: 24,
              metadata: {
                suite: 'llm-spec',
                case: 'identity_metadata_caching',
              },
              user: 'llm-spec-user',
              safety_identifier: 'llm-spec-safety-id',
              prompt_cache_key: 'llm-spec-cache-key',
              prompt_cache_retention: retention,
              seed: 7,
              service_tier: 'auto',
              store: true,
              n: 2,
            } as never,
          ),
          preferredRetention,
        );
        return summarizeOpenAIResponse(response);
      },
    },
    'logprobs': {
      description: 'logprobs + top_logprobs',
      covers: ['logprobs', 'top_logprobs'],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 16,
          logprobs: true,
          top_logprobs: 3,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'logit_bias': {
      description: 'logit_bias',
      covers: ['logit_bias'],
      precondition: () =>
        compatibilityGateway && isReasoningModel(config.model)
          ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects logit_bias for ${config.model}`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 16,
          logit_bias: {
            '198': -1,
          },
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'response_format_json_object': {
      description: 'response_format json_object',
      covers: ['response_format'],
      precondition: () =>
        isGpt4oOrNewerModel(config.model)
          ? `json_object mode not recommended for ${config.model}; use json_schema instead`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...jsonPrompt],
          response_format: { type: 'json_object' },
          max_completion_tokens: 48,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'response_format_json_schema': {
      description: 'response_format json_schema',
      covers: ['response_format'],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...jsonPrompt],
          response_format: {
            type: 'json_schema',
            json_schema: {
              name: 'openai_test_schema',
              strict: true,
              schema: {
                type: 'object',
                properties: {
                  ok: { type: 'boolean' },
                  source: { type: 'string' },
                },
                required: ['ok', 'source'],
                additionalProperties: false,
              },
            },
          },
          max_completion_tokens: 64,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'tools_and_tool_choice': {
      description: 'tools + tool_choice + parallel_tool_calls',
      covers: ['tools', 'tool_choice', 'parallel_tool_calls'],
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Call the echo tool with text "tool test".',
            },
          ],
          tools: [
            {
              type: 'function',
              function: {
                name: 'echo',
                description: 'Echo back input',
                parameters: functionSchema,
              },
            },
          ],
          tool_choice: 'required',
          parallel_tool_calls: false,
          max_completion_tokens: 64,
        });

        const responseObj = response as {
          choices?: Array<{
            message?: {
              tool_calls?: unknown[];
            };
          }>;
        };
        const toolCalls = responseObj.choices?.[0]?.message?.tool_calls;
        if (!Array.isArray(toolCalls) || toolCalls.length === 0) {
          throw new Error('expected at least one tool call in response');
        }

        return summarizeOpenAIResponse(response);
      },
    },
    'legacy_functions': {
      description: 'functions + function_call (deprecated path)',
      covers: ['functions', 'function_call'],
      precondition: () =>
        isReasoningModel(config.model)
          ? `model ${config.model} is a newer reasoning model; docs mark functions/function_call as deprecated in favor of tools/tool_choice`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Use the legacy function to echo this.',
            },
          ],
          functions: [
            {
              name: 'echo',
              description: 'Echo back input',
              parameters: functionSchema,
            },
          ],
          function_call: { name: 'echo' },
          max_completion_tokens: 64,
        });

        const responseObj = response as {
          choices?: Array<{
            message?: {
              function_call?: unknown;
              tool_calls?: unknown[];
            };
          }>;
        };
        const message = responseObj.choices?.[0]?.message;
        const hasLegacyFunctionCall = Boolean(message?.function_call);
        const hasToolCalls = Array.isArray(message?.tool_calls) && message.tool_calls.length > 0;
        if (!hasLegacyFunctionCall && !hasToolCalls) {
          throw new Error('expected function_call/tool_calls in response');
        }

        return summarizeOpenAIResponse(response);
      },
    },
    'prediction_and_verbosity': {
      description: 'prediction + verbosity',
      covers: ['prediction', 'verbosity'],
      precondition: () =>
        compatibilityGateway && isReasoningModel(config.model)
          ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects prediction for ${config.model}`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          prediction: {
            type: 'content',
            content: 'ok',
          },
          verbosity: 'low',
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'reasoning_effort': {
      description: 'reasoning_effort',
      covers: ['reasoning_effort'],
      precondition: () =>
        isReasoningModel(chatReasoningModel)
          ? undefined
          : `reasoning_effort is documented for gpt-5/o-series models; current=${chatReasoningModel}`,
      run: async () => {
        const response = await client.chat.completions.create({
          model: chatReasoningModel,
          messages: [...chatReasoningMessages],
          reasoning_effort: resolveReasoningEffort(chatReasoningModel),
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'stream_and_stream_options': {
      description: 'streaming + stream_options',
      covers: ['stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [{ role: 'user', content: 'Count from 1 to 3, very short.' }],
          max_completion_tokens: 64,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'basic_stream': {
      description: 'basic chat completion (streaming)',
      covers: ['messages', 'model', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'sampling_and_max_completion_stream': {
      description: 'temperature/top_p/penalties/max_completion_tokens (streaming)',
      covers: [
        'temperature',
        'top_p',
        'presence_penalty',
        'frequency_penalty',
        'max_completion_tokens',
        'stream',
        'stream_options',
      ],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          temperature: 0.2,
          top_p: 0.9,
          presence_penalty: 0.1,
          frequency_penalty: 0.1,
          max_completion_tokens: 32,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'n_choices_stream': {
      description: 'n parameter for multiple choices (streaming)',
      covers: ['n', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          n: 2,
          max_completion_tokens: 16,
          stream: true,
          stream_options: {
            include_usage: true,
          },
        });

        let chunkCount = 0;
        const choiceTexts: string[] = [];
        for await (const chunk of stream) {
          chunkCount += 1;
          for (let i = 0; i < chunk.choices.length; i++) {
            const delta = chunk.choices[i]?.delta?.content;
            if (typeof delta === 'string') {
              if (!choiceTexts[i]) choiceTexts[i] = '';
              choiceTexts[i] += delta;
            }
          }
        }
        return `chunks=${chunkCount}, choices=${choiceTexts.length}`;
      },
    },
    'max_tokens_legacy_stream': {
      description: 'legacy max_tokens (streaming)',
      covers: ['max_tokens', 'stream', 'stream_options'],
      precondition: () =>
        isGpt5SeriesModel(config.model) || isOSeriesModel(config.model)
          ? `model ${config.model} uses max_completion_tokens; skip legacy max_tokens test`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_tokens: 32,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'stop_sequences_stream': {
      description: 'stop (streaming)',
      covers: ['stop', 'stream', 'stream_options'],
      precondition: () => {
        if (isO3OrO4MiniModel(config.model)) {
          return `model ${config.model}; docs mark stop as unsupported for o3/o4-mini`;
        }
        if (compatibilityGateway && isGpt5SeriesModel(config.model)) {
          return `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects stop for ${config.model}`;
        }
        return undefined;
      },
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 32,
          stop: ['\n'],
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'identity_metadata_caching_stream': {
      description: 'metadata/user/safety/cache/seed/service_tier/store/n (streaming)',
      covers: [
        'metadata',
        'user',
        'safety_identifier',
        'prompt_cache_key',
        'prompt_cache_retention',
        'seed',
        'service_tier',
        'store',
        'n',
        'stream',
        'stream_options',
      ],
      run: async () => {
        const preferredRetention: PromptCacheRetentionValue = compatibilityGateway
          ? 'in_memory'
          : 'in-memory';
        const stream = await withPromptCacheRetentionFallback(
          (retention) =>
            client.chat.completions.create(
              {
                model: config.model,
                messages: [...baseMessages],
                max_completion_tokens: 24,
                metadata: {
                  suite: 'llm-spec',
                  case: 'identity_metadata_caching_stream',
                },
                user: 'llm-spec-user',
                safety_identifier: 'llm-spec-safety-id',
                prompt_cache_key: 'llm-spec-cache-key',
                prompt_cache_retention: retention,
                seed: 7,
                service_tier: 'auto',
                store: true,
                n: 2,
                stream: true,
                stream_options: {
                  include_usage: true,
                  include_obfuscation: false,
                },
              } as never,
            ),
          preferredRetention,
        );

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream as unknown as AsyncIterable<{ choices?: Array<{ delta?: { content?: string } }> }>) {
          chunkCount += 1;
          const delta = chunk.choices?.[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'logprobs_stream': {
      description: 'logprobs + top_logprobs (streaming)',
      covers: ['logprobs', 'top_logprobs', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 16,
          logprobs: true,
          top_logprobs: 3,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'logit_bias_stream': {
      description: 'logit_bias (streaming)',
      covers: ['logit_bias', 'stream', 'stream_options'],
      precondition: () =>
        compatibilityGateway && isReasoningModel(config.model)
          ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects logit_bias for ${config.model}`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          max_completion_tokens: 16,
          logit_bias: {
            '198': -1,
          },
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'response_format_json_object_stream': {
      description: 'response_format json_object (streaming)',
      covers: ['response_format', 'stream', 'stream_options'],
      precondition: () =>
        isGpt4oOrNewerModel(config.model)
          ? `json_object mode not recommended for ${config.model}; use json_schema instead`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...jsonPrompt],
          response_format: { type: 'json_object' },
          max_completion_tokens: 48,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'response_format_json_schema_stream': {
      description: 'response_format json_schema (streaming)',
      covers: ['response_format', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...jsonPrompt],
          response_format: {
            type: 'json_schema',
            json_schema: {
              name: 'openai_test_schema',
              strict: true,
              schema: {
                type: 'object',
                properties: {
                  ok: { type: 'boolean' },
                  source: { type: 'string' },
                },
                required: ['ok', 'source'],
                additionalProperties: false,
              },
            },
          },
          max_completion_tokens: 64,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'tools_and_tool_choice_stream': {
      description: 'tools + tool_choice + parallel_tool_calls (streaming)',
      covers: ['tools', 'tool_choice', 'parallel_tool_calls', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Call the echo tool with text "tool test".',
            },
          ],
          tools: [
            {
              type: 'function',
              function: {
                name: 'echo',
                description: 'Echo back input',
                parameters: functionSchema,
              },
            },
          ],
          tool_choice: 'required',
          parallel_tool_calls: false,
          max_completion_tokens: 64,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'legacy_functions_stream': {
      description: 'functions + function_call (deprecated path) (streaming)',
      covers: ['functions', 'function_call', 'stream', 'stream_options'],
      precondition: () =>
        isReasoningModel(config.model)
          ? `model ${config.model} is a newer reasoning model; docs mark functions/function_call as deprecated in favor of tools/tool_choice`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Use the legacy function to echo this.',
            },
          ],
          functions: [
            {
              name: 'echo',
              description: 'Echo back input',
              parameters: functionSchema,
            },
          ],
          function_call: { name: 'echo' },
          max_completion_tokens: 64,
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'prediction_and_verbosity_stream': {
      description: 'prediction + verbosity (streaming)',
      covers: ['prediction', 'verbosity', 'stream', 'stream_options'],
      precondition: () =>
        compatibilityGateway && isReasoningModel(config.model)
          ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects prediction for ${config.model}`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [...baseMessages],
          prediction: {
            type: 'content',
            content: 'ok',
          },
          verbosity: 'low',
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'reasoning_effort_stream': {
      description: 'reasoning_effort (streaming)',
      covers: ['reasoning_effort', 'stream', 'stream_options'],
      precondition: () =>
        isReasoningModel(chatReasoningModel)
          ? undefined
          : `reasoning_effort is documented for gpt-5/o-series models; current=${chatReasoningModel}`,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: chatReasoningModel,
          messages: [...chatReasoningMessages],
          reasoning_effort: resolveReasoningEffort(chatReasoningModel),
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'web_search_options_stream': {
      description: 'web_search_options (streaming)',
      covers: ['web_search_options', 'stream', 'stream_options'],
      precondition: () =>
        compatibilityGateway
          ? `web_search_options is not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
          : undefined,
      run: async () => {
        const stream = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Please answer briefly and cite one web source if possible.',
            },
          ],
          max_completion_tokens: 96,
          web_search_options: {
            search_context_size: 'low',
            user_location: {
              type: 'approximate',
              approximate: {
                city: 'San Francisco',
                country: 'US',
                timezone: 'America/Los_Angeles',
              },
            },
          },
          stream: true,
          stream_options: {
            include_usage: true,
            include_obfuscation: false,
          },
        });

        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const delta = chunk.choices[0]?.delta?.content;
          if (typeof delta === 'string') {
            text += delta;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'web_search_options': {
      description: 'web_search_options',
      covers: ['web_search_options'],
      precondition: () =>
        compatibilityGateway
          ? `web_search_options is not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
          : undefined,
      run: async () => {
        const response = await client.chat.completions.create({
          model: config.model,
          messages: [
            {
              role: 'user',
              content: 'Please answer briefly and cite one web source if possible.',
            },
          ],
          max_completion_tokens: 96,
          web_search_options: {
            search_context_size: 'low',
            user_location: {
              type: 'approximate',
              approximate: {
                city: 'San Francisco',
                country: 'US',
                timezone: 'America/Los_Angeles',
              },
            },
          },
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'audio_modalities': {
      description: 'modalities + audio',
      covers: ['modalities', 'audio'],
      precondition: () =>
        isLikelyAudioOutputModel(audioOutputModel)
          ? undefined
          : `audio output needs an audio-capable model (for example gpt-4o-audio-preview); current=${audioOutputModel}`,
      run: async () => {
        const response = await client.chat.completions.create({
          model: audioOutputModel,
          messages: [
            {
              role: 'user',
              content: 'Say hello in one short sentence.',
            },
          ],
          modalities: ['text', 'audio'],
          audio: {
            format: 'mp3',
            voice: 'alloy',
          },
          max_completion_tokens: 64,
        });
        return summarizeOpenAIResponse(response);
      },
    },
    'responses_basic': {
      description: 'responses.create with input + model',
      covers: ['input', 'model'],
      run: async () => {
        const response = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
        });
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_sampling_and_limits': {
      description: 'responses temperature/top_p/max_output_tokens',
      covers: ['temperature', 'top_p', 'max_output_tokens'],
      run: async () => {
        const response = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly one short word.',
          temperature: 0.2,
          top_p: 0.9,
          max_output_tokens: 32,
        });
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_background_and_instructions': {
      description: 'responses background + instructions',
      covers: ['background', 'instructions'],
      run: async () => {
        const response = await client.responses.create({
          model: config.model,
          background: false,
          instructions: 'You are a compatibility tester. Keep output short.',
          input: 'Reply with exactly: ok',
          max_output_tokens: 32,
        });
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_identity_and_cache': {
      description: 'responses metadata/cache/safety/service/store/user',
      covers: [
        'metadata',
        'prompt_cache_key',
        'prompt_cache_retention',
        'safety_identifier',
        'service_tier',
        'store',
        'user',
      ],
      run: async () => {
        const preferredRetention: PromptCacheRetentionValue = compatibilityGateway
          ? 'in_memory'
          : 'in-memory';
        const response = await withPromptCacheRetentionFallback((retention) =>
          client.responses.create(
            {
              model: config.model,
              input: 'Reply with exactly: ok',
              max_output_tokens: 24,
              metadata: {
                suite: 'llm-spec',
                case: 'responses_identity_and_cache',
              },
              prompt_cache_key: 'llm-spec-responses-cache-key',
              prompt_cache_retention: retention,
              safety_identifier: 'llm-spec-responses-safety-id',
              service_tier: 'auto',
              store: true,
              user: 'llm-spec-user',
            } as never,
          ),
          preferredRetention,
        );
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_context_include_truncation': {
      description: 'responses context_management/include/top_logprobs/truncation',
      covers: ['context_management', 'include', 'top_logprobs', 'truncation'],
      run: async () => {
        // docs include `top_logprobs`, but some SDK type releases may lag this field.
        const request: Record<string, unknown> = {
          model: config.model,
          input: 'Reply with exactly: ok',
          context_management: [
            {
              type: 'compaction',
              compact_threshold: 1000,
            },
          ],
          include: ['message.output_text.logprobs'],
          top_logprobs: 2,
          truncation: 'auto',
          max_output_tokens: 32,
        };
        const response = await client.responses.create(request as never);
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_text_json_schema': {
      description: 'responses text.format json_schema + verbosity',
      covers: ['text'],
      run: async () => {
        const response = await client.responses.create({
          model: config.model,
          input: 'Return JSON object with keys: ok(boolean), source(string).',
          text: {
            verbosity: 'low',
            format: {
              type: 'json_schema',
              name: 'openai_responses_schema',
              strict: true,
              schema: {
                type: 'object',
                properties: {
                  ok: { type: 'boolean' },
                  source: { type: 'string' },
                },
                required: ['ok', 'source'],
                additionalProperties: false,
              },
            },
          },
          max_output_tokens: 96,
        });
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_tools': {
      description: 'responses tools + tool_choice + parallel + max_tool_calls',
      covers: ['tools', 'tool_choice', 'parallel_tool_calls', 'max_tool_calls'],
      run: async () => {
        // docs include `max_tool_calls`, but some SDK type releases may lag this field.
        const request: Record<string, unknown> = {
          model: config.model,
          input: 'Call the echo tool with text "tool test".',
          tools: [
            {
              type: 'function',
              name: 'echo',
              description: 'Echo back input',
              parameters: functionSchema,
              strict: true,
            },
          ],
          tool_choice: {
            type: 'function',
            name: 'echo',
          },
          parallel_tool_calls: false,
          max_tool_calls: 1,
          max_output_tokens: 128,
        };
        const response = await client.responses.create(request as never);

        const responseObj = response as {
          output?: Array<{
            type?: string;
          }>;
        };
        const functionCallCount =
          responseObj.output?.filter((item) => item.type === 'function_call').length ?? 0;
        if (functionCallCount === 0) {
          throw new Error('expected at least one function_call in responses output');
        }

        return summarizeOpenAIResponses(response);
      },
    },
    'responses_previous_response_id': {
      description: 'responses previous_response_id follow-up',
      covers: ['previous_response_id'],
      run: async () => {
        const seed = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: seed',
          max_output_tokens: 24,
          store: true,
        });

        const response = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          previous_response_id: seed.id,
          max_output_tokens: 24,
        });
        return `seed=${seed.id}, ${summarizeOpenAIResponses(response)}`;
      },
    },
    'responses_conversation': {
      description: 'responses conversation id reuse',
      covers: ['conversation'],
      precondition: () =>
        compatibilityGateway
          ? `conversation state is not reliably exposed on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
          : undefined,
      run: async () => {
        const seed = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: conversation-seed',
          max_output_tokens: 24,
          store: true,
        });
        const seedObj = seed as { conversation?: { id?: string } | null };
        const conversationId = seedObj.conversation?.id;
        if (!conversationId) {
          throw new Error('response does not include conversation id');
        }

        const response = await client.responses.create({
          model: config.model,
          conversation: conversationId,
          input: 'Reply with exactly: ok',
          max_output_tokens: 24,
        });
        return `conversation=${conversationId}, ${summarizeOpenAIResponses(response)}`;
      },
    },
    'responses_stream_and_options': {
      description: 'responses stream + stream_options',
      covers: ['stream', 'stream_options'],
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          input: 'Count from 1 to 3, very short.',
          max_output_tokens: 64,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_basic_stream': {
      description: 'responses.create with input + model (streaming)',
      covers: ['input', 'model', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_sampling_and_limits_stream': {
      description: 'responses temperature/top_p/max_output_tokens (streaming)',
      covers: ['temperature', 'top_p', 'max_output_tokens', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly one short word.',
          temperature: 0.2,
          top_p: 0.9,
          max_output_tokens: 32,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_background_and_instructions_stream': {
      description: 'responses background + instructions (streaming)',
      covers: ['background', 'instructions', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          background: false,
          instructions: 'You are a compatibility tester. Keep output short.',
          input: 'Reply with exactly: ok',
          max_output_tokens: 32,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_identity_and_cache_stream': {
      description: 'responses metadata/cache/safety/service/store/user (streaming)',
      covers: [
        'metadata',
        'prompt_cache_key',
        'prompt_cache_retention',
        'safety_identifier',
        'service_tier',
        'store',
        'user',
        'stream',
        'stream_options',
      ],
      run: async () => {
        const preferredRetention: PromptCacheRetentionValue = compatibilityGateway
          ? 'in_memory'
          : 'in-memory';
        const stream = await withPromptCacheRetentionFallback(
          (retention) =>
            client.responses.create(
              {
                model: config.model,
                input: 'Reply with exactly: ok',
                max_output_tokens: 24,
                metadata: {
                  suite: 'llm-spec',
                  case: 'responses_identity_and_cache_stream',
                },
                prompt_cache_key: 'llm-spec-responses-cache-key',
                prompt_cache_retention: retention,
                safety_identifier: 'llm-spec-responses-safety-id',
                service_tier: 'auto',
                store: true,
                user: 'llm-spec-user',
                stream: true,
                stream_options: {
                  include_obfuscation: false,
                },
              } as never,
            ),
          preferredRetention,
        );

        let eventCount = 0;
        let text = '';
        for await (const event of stream as unknown as AsyncIterable<{ type?: string; delta?: string }>) {
          eventCount += 1;
          if (event.type === 'response.output_text.delta' && typeof event.delta === 'string') {
            text += event.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_context_include_truncation_stream': {
      description: 'responses context_management/include/top_logprobs/truncation (streaming)',
      covers: ['context_management', 'include', 'top_logprobs', 'truncation', 'stream', 'stream_options'],
      run: async () => {
        const request: Record<string, unknown> = {
          model: config.model,
          input: 'Reply with exactly: ok',
          context_management: [
            {
              type: 'compaction',
              compact_threshold: 1000,
            },
          ],
          include: ['message.output_text.logprobs'],
          top_logprobs: 2,
          truncation: 'auto',
          max_output_tokens: 32,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        };
        const stream = await client.responses.create(request as never);

        let eventCount = 0;
        let text = '';
        for await (const event of stream as unknown as AsyncIterable<{ type?: string; delta?: string }>) {
          eventCount += 1;
          if (event.type === 'response.output_text.delta' && typeof event.delta === 'string') {
            text += event.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_text_json_schema_stream': {
      description: 'responses text.format json_schema + verbosity (streaming)',
      covers: ['text', 'stream', 'stream_options'],
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          input: 'Return JSON object with keys: ok(boolean), source(string).',
          text: {
            verbosity: 'low',
            format: {
              type: 'json_schema',
              name: 'openai_responses_schema',
              strict: true,
              schema: {
                type: 'object',
                properties: {
                  ok: { type: 'boolean' },
                  source: { type: 'string' },
                },
                required: ['ok', 'source'],
                additionalProperties: false,
              },
            },
          },
          max_output_tokens: 96,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_tools_stream': {
      description: 'responses tools + tool_choice + parallel + max_tool_calls (streaming)',
      covers: ['tools', 'tool_choice', 'parallel_tool_calls', 'max_tool_calls', 'stream', 'stream_options'],
      run: async () => {
        const request: Record<string, unknown> = {
          model: config.model,
          input: 'Call the echo tool with text "tool test".',
          tools: [
            {
              type: 'function',
              name: 'echo',
              description: 'Echo back input',
              parameters: functionSchema,
              strict: true,
            },
          ],
          tool_choice: {
            type: 'function',
            name: 'echo',
          },
          parallel_tool_calls: false,
          max_tool_calls: 1,
          max_output_tokens: 128,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        };
        const stream = await client.responses.create(request as never);

        let eventCount = 0;
        let text = '';
        for await (const event of stream as unknown as AsyncIterable<{ type?: string; delta?: string }>) {
          eventCount += 1;
          if (event.type === 'response.output_text.delta' && typeof event.delta === 'string') {
            text += event.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_previous_response_id_stream': {
      description: 'responses previous_response_id follow-up (streaming)',
      covers: ['previous_response_id', 'stream', 'stream_options'],
      run: async () => {
        const seed = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: seed',
          max_output_tokens: 24,
          store: true,
        });

        const stream = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          previous_response_id: seed.id,
          max_output_tokens: 24,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `seed=${seed.id}, events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_conversation_stream': {
      description: 'responses conversation id reuse (streaming)',
      covers: ['conversation', 'stream', 'stream_options'],
      precondition: () =>
        compatibilityGateway
          ? `conversation state is not reliably exposed on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
          : undefined,
      run: async () => {
        const seed = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: conversation-seed',
          max_output_tokens: 24,
          store: true,
        });
        const seedObj = seed as { conversation?: { id?: string } | null };
        const conversationId = seedObj.conversation?.id;
        if (!conversationId) {
          throw new Error('response does not include conversation id');
        }

        const stream = await client.responses.create({
          model: config.model,
          conversation: conversationId,
          input: 'Reply with exactly: ok',
          max_output_tokens: 24,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `conversation=${conversationId}, events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_reasoning_stream': {
      description: 'responses reasoning config (streaming)',
      covers: ['reasoning', 'stream', 'stream_options'],
      precondition: () =>
        isReasoningModel(responsesReasoningModel)
          ? undefined
          : `reasoning is documented for gpt-5/o-series models; current=${responsesReasoningModel}. set OPENAI_REASONING_MODEL to a supported model`,
      run: async () => {
        const stream = await client.responses.create({
          model: responsesReasoningModel,
          input: 'Solve 19*23 quickly, then output only the number.',
          reasoning: {
            effort: resolveReasoningEffort(responsesReasoningModel),
            summary: 'auto',
          },
          max_output_tokens: 96,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_prompt_stream': {
      description: 'responses prompt template reference (streaming)',
      covers: ['prompt', 'stream', 'stream_options'],
      precondition: () =>
        config.responsesPromptId
          ? undefined
          : 'set OPENAI_RESPONSES_PROMPT_ID to enable responses prompt test',
      run: async () => {
        const stream = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          prompt: {
            id: config.responsesPromptId ?? '',
            variables: {
              task: 'compatibility_test',
            },
          },
          max_output_tokens: 64,
          stream: true,
          stream_options: {
            include_obfuscation: false,
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: string };
          if (eventObj.type === 'response.output_text.delta' && typeof eventObj.delta === 'string') {
            text += eventObj.delta;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'responses_reasoning': {
      description: 'responses reasoning config',
      covers: ['reasoning'],
      precondition: () =>
        isReasoningModel(responsesReasoningModel)
          ? undefined
          : `reasoning is documented for gpt-5/o-series models; current=${responsesReasoningModel}. set OPENAI_REASONING_MODEL to a supported model`,
      run: async () => {
        const response = await client.responses.create({
          model: responsesReasoningModel,
          input: 'Solve 19*23 quickly, then output only the number.',
          reasoning: {
            effort: resolveReasoningEffort(responsesReasoningModel),
            summary: 'auto',
          },
          max_output_tokens: 96,
        });
        return summarizeOpenAIResponses(response);
      },
    },
    'responses_prompt': {
      description: 'responses prompt template reference',
      covers: ['prompt'],
      precondition: () =>
        config.responsesPromptId
          ? undefined
          : 'set OPENAI_RESPONSES_PROMPT_ID to enable responses prompt test',
      run: async () => {
        const response = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          prompt: {
            id: config.responsesPromptId ?? '',
            variables: {
              task: 'compatibility_test',
            },
          },
          max_output_tokens: 64,
        });
        return summarizeOpenAIResponses(response);
      },
    },
  });

  // 根据 filter 过滤测试用例
  if (filter) {
    return cases.filter((testCase) => testCase.apiType === filter);
  }

  return cases;
}

function isAbortLikeError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.name === 'AbortError' || /\babort(?:ed|ing)?\b/i.test(error.message);
}

async function withCodexTurnTimeout<T>(
  timeoutMs: number,
  run: (signal: AbortSignal) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer =
    timeoutMs > 0
      ? setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeoutMs)
      : undefined;

  try {
    return await run(controller.signal);
  } catch (error) {
    if (timedOut && isAbortLikeError(error)) {
      throw new Error(`Codex turn timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

async function runCodexTurn(
  thread: Thread,
  input: CodexInput,
  config: CodexProviderConfig,
  turnOptions: Omit<CodexTurnOptions, 'signal'> = {},
) {
  return withCodexTurnTimeout(config.timeoutMs, (signal) =>
    thread.run(input, {
      ...turnOptions,
      signal,
    }),
  );
}

async function collectCodexStream(
  thread: Thread,
  input: CodexInput,
  config: CodexProviderConfig,
  turnOptions: Omit<CodexTurnOptions, 'signal'> = {},
): Promise<{ eventCount: number; eventTypes: string[]; text: string }> {
  return withCodexTurnTimeout(config.timeoutMs, async (signal) => {
    const { events } = await thread.runStreamed(input, {
      ...turnOptions,
      signal,
    });

    let eventCount = 0;
    const eventTypes: string[] = [];
    let text = '';
    let streamFailure: string | null = null;

    try {
      for await (const event of events) {
        eventCount += 1;
        eventTypes.push(event.type);

        if (event.type === 'item.completed' && event.item.type === 'agent_message') {
          text += event.item.text;
        }

        if (event.type === 'turn.failed') {
          streamFailure = event.error.message;
        } else if (event.type === 'error') {
          streamFailure = event.message;
        }
      }
    } catch (error) {
      if (streamFailure) {
        throw new Error(streamFailure);
      }
      throw error;
    }

    if (streamFailure) {
      throw new Error(streamFailure);
    }

    return {
      eventCount,
      eventTypes,
      text,
    };
  });
}

export function buildCodexCases({ client, config }: CodexCaseContext): TestCase[] {
  const cases = defineCases({
    'basic_thread': {
      description: '创建并运行基础thread',
      covers: ['prompt', 'workingDirectory'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn = await runCodexTurn(thread, 'Reply with exactly: ok', config);

        return `finalResponse="${truncate(turn.finalResponse)}", items=${turn.items.length}`;
      },
    },
    'basic_thread_streaming': {
      description: '创建并运行基础thread (streaming)',
      covers: ['prompt', 'workingDirectory', 'streaming'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const { eventCount, text } = await collectCodexStream(
          thread,
          'Reply with exactly: ok',
          config,
        );

        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'structured_output': {
      description: '使用structured output输出JSON',
      covers: ['prompt', 'outputSchema'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const schema = {
          type: 'object',
          properties: {
            ok: { type: 'string' },
            provider: { type: 'string' },
          },
          required: ['ok', 'provider'],
          additionalProperties: false,
        } as const;

        const turn = await runCodexTurn(
          thread,
          'Return JSON object with keys: ok(string), provider(string).',
          config,
          {
            outputSchema: schema,
          },
        );

        return `finalResponse="${truncate(turn.finalResponse)}"`;
      },
    },
    'structured_output_streaming': {
      description: '使用structured output输出JSON (streaming)',
      covers: ['prompt', 'outputSchema', 'streaming'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const schema = {
          type: 'object',
          properties: {
            status: { type: 'string' },
            count: { type: 'number' },
          },
          required: ['status', 'count'],
          additionalProperties: false,
        } as const;

        const { eventCount, text } = await collectCodexStream(
          thread,
          'Return JSON: {"status":"ok","count":42}',
          config,
          {
            outputSchema: schema,
          },
        );

        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'multi_turn_conversation': {
      description: '多轮对话',
      covers: ['prompt'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn1 = await runCodexTurn(thread, 'Remember the number 42', config);
        const turn2 = await runCodexTurn(
          thread,
          'What number did I ask you to remember?',
          config,
        );

        return `turn1="${truncate(turn1.finalResponse)}", turn2="${truncate(turn2.finalResponse)}"`;
      },
    },
    'image_input': {
      description: '图片输入测试',
      covers: ['prompt'],
      precondition: () =>
        config.testImagePath ? undefined : 'set CODEX_TEST_IMAGE_PATH to enable image test',
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn = await runCodexTurn(
          thread,
          [
            { type: 'text', text: 'What is in this image? Reply briefly.' },
            { type: 'local_image', path: config.testImagePath! },
          ],
          config,
        );

        return `finalResponse="${truncate(turn.finalResponse)}"`;
      },
    },
    'resume_thread': {
      description: '恢复已存在的thread',
      covers: ['prompt'],
      run: async () => {
        const thread1 = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        await runCodexTurn(thread1, 'Remember the word "test"', config);
        const threadId = thread1.id;

        if (!threadId) {
          return 'error: thread id is null';
        }

        // 恢复thread
        const thread2 = client.resumeThread(threadId);
        const turn = await runCodexTurn(thread2, 'What word did I ask you to remember?', config);

        return `threadId=${threadId}, finalResponse="${truncate(turn.finalResponse)}"`;
      },
    },
    'config_override': {
      description: '使用config覆盖',
      covers: ['config'],
      run: async () => {
        const customClient = new Codex({
          apiKey: config.apiKey,
          baseUrl: config.apiBaseUrl,
          config: {
            show_raw_agent_reasoning: true,
          },
        });

        const thread = customClient.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn = await runCodexTurn(thread, 'Reply with: config test ok', config);

        return `finalResponse="${truncate(turn.finalResponse)}"`;
      },
    },
    'env_control': {
      description: '控制环境变量',
      covers: ['env'],
      run: async () => {
        const customClient = new Codex({
          apiKey: config.apiKey,
          baseUrl: config.apiBaseUrl,
          env: {
            PATH: process.env.PATH || '',
            HOME: process.env.HOME || '',
            TMPDIR: process.env.TMPDIR || '',
          },
        });

        const thread = customClient.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn = await runCodexTurn(thread, 'Reply with: env test ok', config);

        return `finalResponse="${truncate(turn.finalResponse)}"`;
      },
    },
    'abort_signal': {
      description: '使用AbortSignal取消操作',
      covers: ['prompt'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const controller = new AbortController();

        // 立即取消
        controller.abort();

        try {
          await thread.run('This should be aborted', { signal: controller.signal });
          return 'error: should have been aborted';
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          return `aborted successfully: ${truncate(errorMessage)}`;
        }
      },
    },
    'thread_events': {
      description: '监听thread事件',
      covers: ['prompt', 'streaming'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const { eventTypes } = await collectCodexStream(thread, 'Count from 1 to 3', config);

        return `eventTypes=${eventTypes.join(',')}`;
      },
    },
    'usage_tracking': {
      description: '追踪token使用情况',
      covers: ['prompt'],
      run: async () => {
        const thread = client.startThread({
          workingDirectory: config.workingDirectory,
          skipGitRepoCheck: config.skipGitRepoCheck,
        });

        const turn = await runCodexTurn(thread, 'Reply with: usage test', config);

        if (turn.usage) {
          return `input_tokens=${turn.usage.input_tokens}, output_tokens=${turn.usage.output_tokens}`;
        } else {
          return 'usage=null';
        }
      },
    },
  });

  return cases;
}
