import type OpenAI from 'openai';

import type { OpenAIProviderConfig } from '../../runtime-config';
import {
  summarizeOpenAIResponse,
  summarizeOpenAIResponses,
  truncate,
  type TestCase,
} from '../../shared';
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

export function buildOpenAICases({ client, config }: OpenAICaseContext): TestCase[] {
  const chatReasoningModel = config.reasoningModel ?? config.model;
  const responsesReasoningModel = config.reasoningModel ?? config.model;
  const audioOutputModel = config.audioModel ?? config.model;

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
      precondition: () =>
        isO3OrO4MiniModel(config.model)
          ? `model ${config.model}; docs mark stop as unsupported for o3/o4-mini`
          : undefined,
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
        const response = await client.chat.completions.create({
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
          prompt_cache_retention: 'in-memory',
          seed: 7,
          service_tier: 'auto',
          store: true,
          n: 2,
        });
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
          if (chunkCount >= 200) {
            break;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'web_search_options': {
      description: 'web_search_options',
      covers: ['web_search_options'],
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
        const response = await client.responses.create({
          model: config.model,
          input: 'Reply with exactly: ok',
          max_output_tokens: 24,
          metadata: {
            suite: 'llm-spec',
            case: 'responses_identity_and_cache',
          },
          prompt_cache_key: 'llm-spec-responses-cache-key',
          prompt_cache_retention: 'in-memory',
          safety_identifier: 'llm-spec-responses-safety-id',
          service_tier: 'auto',
          store: true,
          user: 'llm-spec-user',
        });
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
              compact_threshold: 512,
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
          if (eventCount >= 250) {
            break;
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

  return cases;
}
