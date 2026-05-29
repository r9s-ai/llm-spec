import { defineCases } from '../define-cases';
import { summarizeOpenAIResponse, truncate } from '../runtime';
import type { TestCase } from '../types';
import {
  createOpenAIChatSharedState,
  type OpenAICaseContext,
  type PromptCacheRetentionValue,
  isLikelyAudioOutputModel,
  isReasoningModel,
  resolveChatCompletionOutputLimit,
  resolveOpenAINChoices,
  resolveReasoningEffort,
  skipGpt5NanoNChoiceFanout,
  withPromptCacheRetentionFallback,
} from './shared';
import { buildOpenAIChatServedModelCases } from './models';

export function buildOfficialOpenAIChatCases({ client, config }: OpenAICaseContext): TestCase[] {
  const {
    audioOutputModel,
    baseMessages,
    chatReasoningMessages,
    chatReasoningModel,
    chatStreamOptions,
    compatibilityGateway,
    functionSchema,
    skipOpenAIOnlyCaseOnGemini,
  } = createOpenAIChatSharedState({ client, config });
  const outputLimit = (requested: number, model = config.model) =>
    resolveChatCompletionOutputLimit(model, requested);
  const reasoningEffortVariants = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const;
  const promptCacheMessages = [
    {
      role: (isReasoningModel(config.model) ? 'developer' : 'system') as 'developer' | 'system',
      content: `${'llm-spec cache prefix. '.repeat(384)}Keep this shared prefix stable across identical requests.`,
    },
    { role: 'user' as const, content: 'Reply with exactly: cache-ok' },
  ];

  const officialCases = defineCases(
    {
      'n_choices': {
        description: 'n parameter for multiple choices',
        covers: ['n'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('n>1 fan-out generation on chat.completions') ??
          skipGpt5NanoNChoiceFanout(config.model, 'n>1 fan-out generation on chat.completions'),
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            n: 2,
            max_completion_tokens: outputLimit(16),
          });
          const choicesCount = response.choices?.length ?? 0;
          return `choices=${choicesCount}`;
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
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini(
            'metadata/user/prompt cache/service tier/store extensions on chat.completions',
          ),
        run: async () => {
          const preferredRetention: PromptCacheRetentionValue = 'in_memory';
          const response = await withPromptCacheRetentionFallback((retention) =>
            client.chat.completions.create(
              {
                model: config.model,
                messages: [...baseMessages],
                max_completion_tokens: outputLimit(24),
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
                n: resolveOpenAINChoices(config.model, 2),
              } as never,
            ),
            preferredRetention,
          );
          return summarizeOpenAIResponse(response);
        },
      },
      'prompt_cache_round_trip': {
        description: 'prompt_cache_key + prompt_cache_retention round trip',
        covers: ['prompt_cache_key', 'prompt_cache_retention'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('prompt cache extensions on chat.completions'),
        run: async () => {
          let appliedRetention: PromptCacheRetentionValue = 'in_memory';

          const runCacheRequest = () =>
            withPromptCacheRetentionFallback(
              (retention) => {
                appliedRetention = retention;
                return client.chat.completions.create(
                  {
                    model: config.model,
                    messages: promptCacheMessages,
                    prompt_cache_key: 'llm-spec-chat-cache-round-trip',
                    prompt_cache_retention: retention,
                    max_completion_tokens: outputLimit(64),
                  } as never,
                );
              },
              appliedRetention,
            );

          const first = await runCacheRequest();
          const second = await runCacheRequest();
          const firstUsage = (first as {
            usage?: {
              prompt_tokens_details?: {
                cached_tokens?: number;
              };
            };
          }).usage;
          const secondUsage = (second as {
            usage?: {
              prompt_tokens_details?: {
                cached_tokens?: number;
              };
            };
          }).usage;

          return `retention=${appliedRetention}, first_cached=${firstUsage?.prompt_tokens_details?.cached_tokens ?? 'n/a'}, second_cached=${secondUsage?.prompt_tokens_details?.cached_tokens ?? 'n/a'}, ${summarizeOpenAIResponse(second)}`;
        },
      },
      'prompt_cache_retention_24h': {
        description: 'prompt_cache_retention 24h',
        covers: ['prompt_cache_key', 'prompt_cache_retention'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('24h prompt cache retention on chat.completions') ??
          (compatibilityGateway
            ? `24h prompt cache retention targets native OpenAI; current gateway=${config.apiBaseUrl ?? '(unknown)'}`
            : undefined),
        run: async () => {
          const response = await client.chat.completions.create(
            {
              model: config.model,
              messages: promptCacheMessages,
              prompt_cache_key: 'llm-spec-chat-cache-retention-24h',
              prompt_cache_retention: '24h',
              max_completion_tokens: outputLimit(64),
            } as never,
          );
          return summarizeOpenAIResponse(response);
        },
      },
      'logprobs': {
        description: 'logprobs + top_logprobs',
        covers: ['logprobs', 'top_logprobs'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('logprobs/top_logprobs on chat.completions'),
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            max_completion_tokens: outputLimit(16),
            logprobs: true,
            top_logprobs: 3,
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'top_logprobs_variants': {
        description: 'top_logprobs 1/5/10 variants',
        covers: ['logprobs', 'top_logprobs'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('top_logprobs variants on chat.completions'),
        run: async () => {
          const results: string[] = [];
          const variants = [1, 5, 10] as const;

          for (const topLogprobs of variants) {
            const response = await client.chat.completions.create({
              model: config.model,
              messages: [...baseMessages],
              max_completion_tokens: outputLimit(16),
              logprobs: true,
              top_logprobs: topLogprobs,
            });
            results.push(`${topLogprobs}:${response.choices?.[0]?.logprobs ? 'ok' : 'missing'}`);
          }

          return results.join(', ');
        },
      },
      'logit_bias': {
        description: 'logit_bias',
        covers: ['logit_bias'],
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'strict logit_bias success checks; Gemini documents tokenizer compatibility as limited',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return compatibilityGateway && isReasoningModel(config.model)
            ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects logit_bias for ${config.model}`
            : undefined;
        },
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            max_completion_tokens: outputLimit(16),
            logit_bias: {
              '198': -1,
            },
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'legacy_functions': {
        description: 'functions + function_call (deprecated path)',
        covers: ['functions', 'function_call'],
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'legacy functions/function_call on chat.completions',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return isReasoningModel(config.model)
            ? `model ${config.model} is a newer reasoning model; docs mark functions/function_call as deprecated in favor of tools/tool_choice`
            : undefined;
        },
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
            max_completion_tokens: outputLimit(64),
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
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'prediction/verbosity OpenAI-native extensions on chat.completions',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return compatibilityGateway && isReasoningModel(config.model)
            ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects prediction for ${config.model}`
            : undefined;
        },
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
            max_completion_tokens: outputLimit(128, chatReasoningModel),
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'reasoning_effort_variants': {
        description: 'reasoning_effort all documented variants',
        covers: ['reasoning_effort'],
        precondition: () =>
          isReasoningModel(chatReasoningModel)
            ? undefined
            : `reasoning_effort is documented for gpt-5/o-series models; current=${chatReasoningModel}`,
        run: async () => {
          const results: string[] = [];

          for (const effort of reasoningEffortVariants) {
            const response = await client.chat.completions.create({
              model: chatReasoningModel,
              messages: [...chatReasoningMessages],
              reasoning_effort: effort,
              max_completion_tokens: outputLimit(128, chatReasoningModel),
            });
            results.push(`${effort}:${response.choices?.length ?? 0}`);
          }

          return results.join(', ');
        },
      },
      'n_choices_stream': {
        description: 'n parameter for multiple choices (streaming)',
        covers: ['n', 'stream', 'stream_options'],
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('n>1 fan-out generation on streamed chat.completions') ??
          skipGpt5NanoNChoiceFanout(
            config.model,
            'n>1 fan-out generation on streamed chat.completions',
          ),
        run: async () => {
          const stream = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            n: 2,
            max_completion_tokens: outputLimit(16),
            stream: true,
            stream_options: chatStreamOptions,
          });

          let chunkCount = 0;
          const choiceTexts: string[] = [];
          for await (const chunk of stream) {
            chunkCount += 1;
            for (let i = 0; i < chunk.choices.length; i += 1) {
              const delta = chunk.choices[i]?.delta?.content;
              if (typeof delta === 'string') {
                if (!choiceTexts[i]) {
                  choiceTexts[i] = '';
                }
                choiceTexts[i] += delta;
              }
            }
          }
          return `chunks=${chunkCount}, choices=${choiceTexts.length}`;
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
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini(
            'metadata/user/prompt cache/service tier/store extensions on streamed chat.completions',
          ),
        run: async () => {
          const preferredRetention: PromptCacheRetentionValue = 'in_memory';
          const stream = await withPromptCacheRetentionFallback(
            (retention) =>
              client.chat.completions.create(
                {
                  model: config.model,
                  messages: [...baseMessages],
                  max_completion_tokens: outputLimit(24),
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
                  n: resolveOpenAINChoices(config.model, 2),
                  stream: true,
                  stream_options: chatStreamOptions,
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
        precondition: () =>
          skipOpenAIOnlyCaseOnGemini('logprobs/top_logprobs on streamed chat.completions'),
        run: async () => {
          const stream = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            max_completion_tokens: outputLimit(16),
            logprobs: true,
            top_logprobs: 3,
            stream: true,
            stream_options: chatStreamOptions,
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
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'strict streamed logit_bias success checks; Gemini documents tokenizer compatibility as limited',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return compatibilityGateway && isReasoningModel(config.model)
            ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects logit_bias for ${config.model}`
            : undefined;
        },
        run: async () => {
          const stream = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            max_completion_tokens: outputLimit(16),
            logit_bias: {
              '198': -1,
            },
            stream: true,
            stream_options: chatStreamOptions,
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
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'legacy functions/function_call on streamed chat.completions',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return isReasoningModel(config.model)
            ? `model ${config.model} is a newer reasoning model; docs mark functions/function_call as deprecated in favor of tools/tool_choice`
            : undefined;
        },
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
            max_completion_tokens: outputLimit(64),
            stream: true,
            stream_options: chatStreamOptions,
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
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'prediction/verbosity OpenAI-native extensions on streamed chat.completions',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return compatibilityGateway && isReasoningModel(config.model)
            ? `gateway ${config.apiBaseUrl ?? '(unknown)'} rejects prediction for ${config.model}`
            : undefined;
        },
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
            stream_options: chatStreamOptions,
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
            max_completion_tokens: outputLimit(128, chatReasoningModel),
            stream: true,
            stream_options: chatStreamOptions,
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
            max_completion_tokens: outputLimit(96),
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
            stream_options: chatStreamOptions,
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
            max_completion_tokens: outputLimit(96),
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
        precondition: () => {
          const geminiSkip = skipOpenAIOnlyCaseOnGemini(
            'audio output modalities on chat.completions',
          );
          if (geminiSkip) {
            return geminiSkip;
          }
          return isLikelyAudioOutputModel(audioOutputModel)
            ? undefined
            : `audio output needs an audio-capable model (for example gpt-4o-audio-preview); current=${audioOutputModel}`;
        },
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
            max_completion_tokens: outputLimit(64, audioOutputModel),
          });
          return summarizeOpenAIResponse(response);
        },
      },
    },
    {
      protocol: 'openai.chat',
      modelScope: 'openai',
      testModel: config.model,
    },
  );

  const casesWithSelectedModels = officialCases.map((testCase) => {
    if (testCase.id.startsWith('reasoning_effort')) {
      return { ...testCase, testModel: chatReasoningModel };
    }
    if (testCase.id === 'audio_modalities') {
      return { ...testCase, testModel: audioOutputModel };
    }
    return testCase;
  });

  return [
    ...casesWithSelectedModels,
    ...buildOpenAIChatServedModelCases({ client, config }),
  ];
}

export type { OpenAICaseContext };
