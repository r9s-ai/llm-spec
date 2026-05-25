import { defineCases } from '../define-cases';
import { createFixtureDataUri } from '../../fixtures';
import { formatError, summarizeOpenAIResponse, truncate } from '../runtime';
import type { TestCase } from '../types';
import {
  createBaseMessages,
  type OpenAICaseContext,
  isGeminiOpenAICompatibilityTarget,
  type PromptCacheRetentionValue,
  resolveChatCompletionOutputLimit,
  withPromptCacheRetentionFallback,
} from './shared';

const GEMINI_VALIDATION_ERROR_MARKERS = [
  'invalid argument',
  'invalid value',
  'invalid request',
  'unsupported parameter',
  'unsupported field',
  'bad request',
] as const;

function getErrorStatus(error: unknown): number | undefined {
  if (!(error instanceof Error)) {
    return undefined;
  }

  const errorWithStatus = error as Error & { status?: unknown };
  return typeof errorWithStatus.status === 'number' ? errorWithStatus.status : undefined;
}

function getErrorSearchText(error: unknown): string {
  if (!(error instanceof Error)) {
    return String(error).toLowerCase();
  }

  const errorLike = error as Error & {
    code?: unknown;
    type?: unknown;
    error?: {
      code?: unknown;
      type?: unknown;
      message?: unknown;
    };
  };

  return [
    error.message,
    typeof errorLike.code === 'string' ? errorLike.code : undefined,
    typeof errorLike.type === 'string' ? errorLike.type : undefined,
    typeof errorLike.error?.code === 'string' ? errorLike.error.code : undefined,
    typeof errorLike.error?.type === 'string' ? errorLike.error.type : undefined,
    typeof errorLike.error?.message === 'string' ? errorLike.error.message : undefined,
    formatError(error),
  ]
    .filter((value): value is string => Boolean(value))
    .join(' ')
    .toLowerCase();
}

function formatExpectedGeminiValidationError(
  error: unknown,
  parameterMarkers: readonly string[],
): string {
  const status = getErrorStatus(error);
  const searchText = getErrorSearchText(error);
  const isValidationStatus = status === 400 || status === 422;
  const matchedParameter = parameterMarkers.some((marker) => searchText.includes(marker));
  const matchedGenericValidation = GEMINI_VALIDATION_ERROR_MARKERS.some((marker) =>
    searchText.includes(marker),
  );

  if (isValidationStatus && (matchedParameter || matchedGenericValidation)) {
    return truncate(formatError(error), 160);
  }

  throw error;
}

function getToolCalls(response: unknown): unknown[] {
  const responseObj = response as {
    choices?: Array<{
      message?: {
        tool_calls?: unknown[];
      };
    }>;
  };
  const toolCalls = responseObj.choices?.[0]?.message?.tool_calls;
  return Array.isArray(toolCalls) ? toolCalls : [];
}

export function buildGeminiOpenAIChatCases({ client, config }: OpenAICaseContext): TestCase[] {
  const geminiCompatibilityTarget = isGeminiOpenAICompatibilityTarget(config.model);
  const chatReasoningModel = config.reasoningModel ?? config.model;
  const baseMessages = createBaseMessages(config.model);
  const outputLimit = (requested: number, model = config.model) =>
    resolveChatCompletionOutputLimit(model, requested);
  const promptCacheMessages = [
    {
      role: 'system' as const,
      content: `${'llm-spec gemini cache prefix. '.repeat(384)}Keep this shared prefix stable across identical requests.`,
    },
    { role: 'user' as const, content: 'Reply with exactly: cache-ok' },
  ];
  const geminiTinyImageDataUri = createFixtureDataUri('image/png', 'images/image-input.png');

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

  function requireGeminiCompatibilityTarget(caseId: string): string | undefined {
    return geminiCompatibilityTarget
      ? undefined
      : `${caseId} only applies when OPENAI_MODEL targets a Gemini model`;
  }

  async function createGeminiCompatibilityChatCompletion(
    body: Record<string, unknown>,
    extraBody?: Record<string, unknown>,
  ) {
    return client.chat.completions.create(
      body as never,
      extraBody ? { body: { ...body, ...extraBody } } : undefined,
    );
  }

  const cases = defineCases(
    {
      'gemini_message_roles_and_name': {
        description: 'Gemini compatibility: system/user/assistant/tool roles + name',
        covers: ['messages'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_message_roles_and_name'),
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'system',
                name: 'policy',
                content: 'You are a compatibility tester. Keep output short.',
              },
              {
                role: 'user',
                name: 'alice',
                content: 'Use the tool result from history and answer with exactly one word.',
              },
              {
                role: 'assistant',
                name: 'planner',
                tool_calls: [
                  {
                    id: 'call_weather_1',
                    type: 'function',
                    function: {
                      name: 'echo_weather',
                      arguments: '{"forecast":"sunny"}',
                    },
                  },
                ],
              },
              {
                role: 'tool',
                tool_call_id: 'call_weather_1',
                content: '{"forecast":"sunny"}',
              },
              {
                role: 'user',
                content: 'Using the tool result, reply with exactly: sunny',
              },
            ] as never,
            max_completion_tokens: outputLimit(32),
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'gemini_multimodal_image_input': {
        description: 'Gemini compatibility: multimodal messages content with image_url',
        covers: ['messages'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_multimodal_image_input'),
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'system',
                content: 'You are a compatibility tester. Obey the user exactly.',
              },
              {
                role: 'user',
                name: 'vision-user',
                content: [
                  {
                    type: 'text',
                    text: 'Ignore the image content and reply exactly: image-ok',
                  },
                  {
                    type: 'image_url',
                    image_url: {
                      url: geminiTinyImageDataUri,
                    },
                  },
                ],
              },
            ] as never,
            max_completion_tokens: outputLimit(24),
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'gemini_reasoning_effort_variants': {
        description: 'Gemini compatibility: reasoning_effort low/medium/high/none',
        covers: ['reasoning_effort'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_reasoning_effort_variants'),
        run: async () => {
          const efforts = ['low', 'medium', 'high', 'none'] as const;
          const results: string[] = [];

          for (const effort of efforts) {
            const response = await client.chat.completions.create({
              model: chatReasoningModel,
              messages: [
                {
                  role: 'system',
                  content: 'You are a compatibility tester. Keep output short.',
                },
                {
                  role: 'user',
                  content: `Reply with exactly: ${effort}`,
                },
              ],
              reasoning_effort: effort,
              max_completion_tokens: outputLimit(32, chatReasoningModel),
            });
            const usage = (response as {
              usage?: {
                completion_tokens_details?: {
                  reasoning_tokens?: number;
                };
              };
            }).usage;
            results.push(`${effort}:${usage?.completion_tokens_details?.reasoning_tokens ?? 'n/a'}`);
          }

          return results.join(', ');
        },
      },
      'gemini_tool_choice_variants': {
        description: 'Gemini compatibility: tool_choice none/auto/forced function',
        covers: ['tools', 'tool_choice', 'parallel_tool_calls'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_tool_choice_variants'),
        run: async () => {
          const noneResponse = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'Do not call any tool. Reply with exactly: no-tool',
              },
            ],
            tools: [functionTool],
            tool_choice: 'none',
            max_completion_tokens: outputLimit(24),
          });
          if (getToolCalls(noneResponse).length > 0) {
            throw new Error('expected tool_choice=none to suppress tool calls');
          }

          const autoResponse = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'Call the echo tool with text "auto-tool". Do not answer directly.',
              },
            ],
            tools: [functionTool],
            tool_choice: 'auto',
            parallel_tool_calls: true,
            max_completion_tokens: outputLimit(64),
          });
          const autoToolCalls = getToolCalls(autoResponse);
          if (autoToolCalls.length === 0) {
            throw new Error('expected tool_choice=auto to produce at least one tool call');
          }

          const forcedResponse = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'Call the echo tool with text "forced-tool".',
              },
            ],
            tools: [functionTool],
            tool_choice: {
              type: 'function',
              function: {
                name: 'echo',
              },
            },
            max_completion_tokens: outputLimit(64),
          });
          const forcedToolCalls = getToolCalls(forcedResponse);
          if (forcedToolCalls.length === 0) {
            throw new Error('expected forced tool_choice to produce a tool call');
          }

          const forcedToolName = (
            forcedToolCalls[0] as {
              function?: {
                name?: string;
              };
            }
          ).function?.name;
          if (forcedToolName !== 'echo') {
            throw new Error(`expected forced tool call name "echo", got ${forcedToolName ?? 'unknown'}`);
          }

          return `none=0, auto=${autoToolCalls.length}, forced=${forcedToolCalls.length}`;
        },
      },
      'gemini_stream_includes_usage': {
        description: 'Gemini compatibility: stream_options include_usage final usage chunk',
        covers: ['stream', 'stream_options'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_stream_includes_usage'),
        run: async () => {
          const stream = await client.chat.completions.create({
            model: chatReasoningModel,
            messages: [
              {
                role: 'user',
                content: 'Count from 1 to 3, very short.',
              },
            ],
            reasoning_effort: 'low',
            max_completion_tokens: outputLimit(48, chatReasoningModel),
            stream: true,
            stream_options: {
              include_usage: true,
            },
          });

          let chunkCount = 0;
          let text = '';
          let finalUsage:
            | {
                prompt_tokens?: number;
                completion_tokens?: number;
                total_tokens?: number;
              }
            | undefined;

          for await (const chunk of stream as AsyncIterable<{
            choices: Array<{ delta?: { content?: string | null } }>;
            usage?: {
              prompt_tokens?: number;
              completion_tokens?: number;
              total_tokens?: number;
            } | null;
          }>) {
            chunkCount += 1;
            const delta = chunk.choices[0]?.delta?.content;
            if (typeof delta === 'string') {
              text += delta;
            }
            if (chunk.usage) {
              finalUsage = chunk.usage;
            }
          }

          if (
            !finalUsage ||
            typeof finalUsage.prompt_tokens !== 'number' ||
            typeof finalUsage.completion_tokens !== 'number' ||
            typeof finalUsage.total_tokens !== 'number'
          ) {
            throw new Error('expected final streamed usage chunk when include_usage=true');
          }

          return `chunks=${chunkCount}, tokens=${finalUsage.prompt_tokens}+${finalUsage.completion_tokens}, text="${truncate(text)}"`;
        },
      },
      'gemini_extra_body_native_params': {
        description: 'Gemini compatibility: native thinking params via extra body',
        covers: ['extra_body'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_extra_body_native_params'),
        run: async () => {
          const response = await createGeminiCompatibilityChatCompletion(
            {
              model: chatReasoningModel,
              messages: [
                {
                  role: 'system',
                  content: 'You are a compatibility tester. Keep output short.',
                },
                {
                  role: 'user',
                  content: 'Reply with exactly: budget-ok',
                },
              ],
              max_completion_tokens: outputLimit(48, chatReasoningModel),
            },
            {
              thinking_budget: 1024,
            },
          );
          return summarizeOpenAIResponse(response);
        },
      },
      'gemini_prompt_cache_round_trip': {
        description: 'Gemini compatibility: prompt_cache_key + prompt_cache_retention round trip',
        covers: ['prompt_cache_key', 'prompt_cache_retention'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_prompt_cache_round_trip'),
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
                    prompt_cache_key: 'llm-spec-gemini-chat-cache-round-trip',
                    prompt_cache_retention: retention,
                    max_completion_tokens: outputLimit(64),
                  } as never,
                );
              },
              appliedRetention,
            );

          try {
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
          } catch (error) {
            return `rejected_as_limited="${formatExpectedGeminiValidationError(error, [
              'prompt_cache_key',
              'prompt cache key',
              'prompt_cache_retention',
              'prompt cache retention',
              'cached_content',
              'cached content',
            ])}"`;
          }
        },
      },
      'gemini_n_is_limited': {
        description: 'Gemini compatibility: n>1 is rejected or clamped to 1',
        covers: ['n'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_n_is_limited'),
        run: async () => {
          try {
            const response = await client.chat.completions.create({
              model: config.model,
              messages: [...baseMessages],
              n: 2,
              max_completion_tokens: outputLimit(16),
            });
            const choicesCount = response.choices?.length ?? 0;
            if (choicesCount < 1) {
              throw new Error('expected at least one choice when request succeeds');
            }
            if (choicesCount > 1) {
              throw new Error(
                `expected Gemini compatibility layer to reject or clamp n>1, got ${choicesCount} choices`,
              );
            }
            return `clamped_choices=${choicesCount}`;
          } catch (error) {
            return `rejected_as_expected="${formatExpectedGeminiValidationError(error, [
              'parameter n',
              '"n"',
              '`n`',
              'candidate_count',
            ])}"`;
          }
        },
      },
      'gemini_logit_bias_limited': {
        description: 'Gemini compatibility: logit_bias limited tokenizer support',
        covers: ['logit_bias'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_logit_bias_limited'),
        run: async () => {
          try {
            const response = await client.chat.completions.create({
              model: config.model,
              messages: [...baseMessages],
              max_completion_tokens: outputLimit(16),
              logit_bias: {
                '198': -1,
              },
            });
            return `accepted, ${summarizeOpenAIResponse(response)}`;
          } catch (error) {
            return `rejected_as_limited="${formatExpectedGeminiValidationError(error, [
              'logit_bias',
              'logit bias',
              'tokenizer',
              'token id',
              'token ids',
            ])}"`;
          }
        },
      },
      'gemini_response_envelope_and_usage': {
        description: 'Gemini compatibility: response envelope + usage accounting fields',
        covers: ['model', 'messages'],
        precondition: () => requireGeminiCompatibilityTarget('gemini_response_envelope_and_usage'),
        run: async () => {
          const response = await client.chat.completions.create({
            model: chatReasoningModel,
            messages: [
              {
                role: 'system',
                content: 'You are a compatibility tester. Keep output short.',
              },
              {
                role: 'user',
                content: 'Reply with exactly: usage-ok',
              },
            ],
            reasoning_effort: 'low',
            max_completion_tokens: outputLimit(48, chatReasoningModel),
          });

          const responseObj = response as {
            id?: string;
            object?: string;
            created?: number;
            model?: string;
            choices?: Array<{
              index?: number;
              finish_reason?: string;
              message?: {
                role?: string;
                content?: string | null;
                tool_calls?: unknown[];
              };
            }>;
            usage?: {
              prompt_tokens?: number;
              completion_tokens?: number;
              total_tokens?: number;
              prompt_tokens_details?: {
                cached_tokens?: number;
                audio_tokens?: number;
              };
              completion_tokens_details?: {
                reasoning_tokens?: number;
              };
            };
          };

          if (typeof responseObj.id !== 'string' || !responseObj.id.startsWith('chatcmpl-')) {
            throw new Error('expected response id with chatcmpl- prefix');
          }
          if (responseObj.object !== 'chat.completion') {
            throw new Error(`expected object=chat.completion, got ${responseObj.object ?? 'missing'}`);
          }
          if (typeof responseObj.created !== 'number') {
            throw new Error('expected numeric created timestamp');
          }
          if (typeof responseObj.model !== 'string' || responseObj.model.length === 0) {
            throw new Error('expected response model name');
          }

          const choice = responseObj.choices?.[0];
          if (!choice) {
            throw new Error('expected at least one choice');
          }
          if (choice.index !== 0) {
            throw new Error(`expected first choice index=0, got ${choice.index ?? 'missing'}`);
          }
          if (choice.message?.role !== 'assistant') {
            throw new Error(`expected assistant message role, got ${choice.message?.role ?? 'missing'}`);
          }
          if (typeof choice.finish_reason !== 'string') {
            throw new Error('expected finish_reason on first choice');
          }

          const usage = responseObj.usage;
          if (
            !usage ||
            typeof usage.prompt_tokens !== 'number' ||
            typeof usage.completion_tokens !== 'number' ||
            typeof usage.total_tokens !== 'number'
          ) {
            throw new Error('expected usage prompt/completion/total token fields');
          }
          if (usage.total_tokens !== usage.prompt_tokens + usage.completion_tokens) {
            throw new Error(
              `expected total_tokens=${usage.prompt_tokens + usage.completion_tokens}, got ${usage.total_tokens}`,
            );
          }

          return `model=${responseObj.model}, finish=${choice.finish_reason}, prompt=${usage.prompt_tokens}, completion=${usage.completion_tokens}, cached=${usage.prompt_tokens_details?.cached_tokens ?? 'n/a'}, audio=${usage.prompt_tokens_details?.audio_tokens ?? 'n/a'}, reasoning=${usage.completion_tokens_details?.reasoning_tokens ?? 'n/a'}`;
        },
      },
    },
    {
      apiType: 'chatCompletions',
      protocol: 'openai.chat',
      modelScope: 'gemini',
    },
  );

  return cases;
}
