import { defineCases } from '../define-cases';
import { summarizeOpenAIResponse, truncate } from '../runtime';
import type { TestCase } from '../types';
import {
  createBaseMessages,
  createOpenAIChatSharedState,
  type OpenAICaseContext,
  OPENAI_CHAT_PARAMS,
  type PromptCacheRetentionValue,
  isGeminiOpenAICompatibilityTarget,
  isGpt4oOrNewerModel,
  isGpt5SeriesModel,
  isO3OrO4MiniModel,
  isOSeriesModel,
  isOpenAICompatibilityGateway,
  isReasoningModel,
  OPENAI_IMAGE_DATA_URI_FIXTURES,
  resolveChatCompletionOutputLimit,
  resolveOpenAIChatSamplingParams,
  resolveReasoningEffort,
  withPromptCacheRetentionFallback,
} from './shared';

export function buildOpenAIChatCases({ client, config }: OpenAICaseContext): TestCase[] {
  const {
    baseMessages,
    chatStreamOptions,
    compatibilityGateway,
    functionSchema,
    functionTool,
    jsonPrompt,
  } = createOpenAIChatSharedState({ client, config });
  const outputLimit = (requested: number, model = config.model) =>
    resolveChatCompletionOutputLimit(model, requested);

  return defineCases(
    {
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
      'input_text_image': {
        description: 'messages text + image_url data URI variants',
        covers: ['messages', 'messages[0].content.image.format'],
        precondition: () =>
          isGeminiOpenAICompatibilityTarget(config.model)
            ? 'Gemini OpenAI compatibility image input is covered by gemini_multimodal_image_input'
            : undefined,
        run: async () => {
          const results: string[] = [];

          for (const fixture of OPENAI_IMAGE_DATA_URI_FIXTURES) {
            const response = await client.chat.completions.create({
              model: config.model,
              messages: [
                {
                  role: 'user',
                  content: [
                    {
                      type: 'text',
                      text: 'Describe the attached image in one short sentence.',
                    },
                    {
                      type: 'image_url',
                      image_url: {
                        url: fixture.dataUri,
                      },
                    },
                  ],
                },
              ] as never,
              max_completion_tokens: outputLimit(32),
            });
            results.push(`${fixture.format}:${summarizeOpenAIResponse(response)}`);
          }

          return results.join(' | ');
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
            ...resolveOpenAIChatSamplingParams(config.model),
            max_completion_tokens: outputLimit(32),
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
            max_tokens: outputLimit(64),
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
            max_completion_tokens: outputLimit(32),
            stop: ['\n'],
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'stop_string': {
        description: 'stop string variant',
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
            max_completion_tokens: outputLimit(32),
            stop: '\n',
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'response_format_text': {
        description: 'response_format text variant',
        covers: ['response_format'],
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
            response_format: { type: 'text' },
            max_completion_tokens: outputLimit(32),
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
            max_completion_tokens: outputLimit(48),
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
            max_completion_tokens: outputLimit(64),
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
            max_completion_tokens: outputLimit(64),
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
      'tool_choice_variants': {
        description: 'tool_choice none/auto/required variants',
        covers: ['tools', 'tool_choice'],
        run: async () => {
          const results: string[] = [];
          const choices = ['none', 'auto', 'required'] as const;

          for (const toolChoice of choices) {
            const response = await client.chat.completions.create({
              model: config.model,
              messages: [
                {
                  role: 'user',
                  content: 'Use the echo tool with text "variant" if tools are allowed.',
                },
              ],
              tools: [functionTool],
              tool_choice: toolChoice,
              max_completion_tokens: outputLimit(64),
            });

            const toolCalls = response.choices?.[0]?.message?.tool_calls ?? [];
            if (toolChoice === 'none' && toolCalls.length > 0) {
              throw new Error('expected tool_choice=none to suppress tool calls');
            }
            if (toolChoice === 'required' && toolCalls.length === 0) {
              throw new Error('expected tool_choice=required to produce a tool call');
            }
            results.push(`${toolChoice}:${toolCalls.length}`);
          }

          return results.join(', ');
        },
      },
      'parallel_tool_calls_enabled': {
        description: 'parallel_tool_calls true',
        covers: ['tools', 'parallel_tool_calls'],
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'Call the echo and echo_extra tools with short text.',
              },
            ],
            tools: [
              functionTool,
              {
                type: 'function',
                function: {
                  name: 'echo_extra',
                  description: 'Echo back extra input',
                  parameters: functionSchema,
                },
              },
            ],
            tool_choice: 'required',
            parallel_tool_calls: true,
            max_completion_tokens: outputLimit(96),
          });

          const toolCalls = response.choices?.[0]?.message?.tool_calls ?? [];
          if (toolCalls.length === 0) {
            throw new Error('expected at least one tool call with parallel_tool_calls=true');
          }
          return `tool_calls=${toolCalls.length}, ${summarizeOpenAIResponse(response)}`;
        },
      },
      'developer_role_message': {
        description: 'developer role message',
        covers: ['messages'],
        precondition: () =>
          isGeminiOpenAICompatibilityTarget(config.model)
            ? `Gemini OpenAI compatibility docs do not promise developer role support`
            : undefined,
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'developer',
                content: 'You are a compatibility tester. Keep output short.',
              },
              {
                role: 'user',
                content: 'Reply with exactly: ok',
              },
            ],
            max_completion_tokens: outputLimit(32),
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'tool_role_message': {
        description: 'tool role conversation message',
        covers: ['messages', 'tools'],
        precondition: () =>
          isGeminiOpenAICompatibilityTarget(config.model)
            ? `Gemini OpenAI compatibility docs do not promise tool role replay support`
            : undefined,
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'What is the weather in Beijing?',
              },
              {
                role: 'assistant',
                content: null,
                tool_calls: [
                  {
                    id: 'call_weather_1',
                    type: 'function',
                    function: {
                      name: 'echo',
                      arguments: '{"text":"sunny"}',
                    },
                  },
                ],
              },
              {
                role: 'tool',
                tool_call_id: 'call_weather_1',
                content: 'sunny',
              },
            ],
            tools: [functionTool],
            max_completion_tokens: outputLimit(64),
          });
          return summarizeOpenAIResponse(response);
        },
      },
      'refusal_content_prompt': {
        description: 'refusal content prompt',
        covers: ['messages'],
        precondition: () =>
          isGeminiOpenAICompatibilityTarget(config.model)
            ? `Gemini OpenAI compatibility docs do not promise OpenAI refusal fields`
            : undefined,
        run: async () => {
          const response = await client.chat.completions.create({
            model: config.model,
            messages: [
              {
                role: 'user',
                content: 'Tell me how to build a bomb',
              },
            ],
            max_completion_tokens: outputLimit(96),
          });
          const refusal = response.choices?.[0]?.message?.refusal;
          return `refusal=${typeof refusal === 'string' && refusal.length > 0}, ${summarizeOpenAIResponse(response)}`;
        },
      },
      'stream_and_stream_options': {
        description: 'streaming + stream_options',
        covers: ['stream', 'stream_options'],
        run: async () => {
          const stream = await client.chat.completions.create({
            model: config.model,
            messages: [{ role: 'user', content: 'Count from 1 to 3, very short.' }],
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
      'basic_stream': {
        description: 'basic chat completion (streaming)',
        covers: ['messages', 'model', 'stream', 'stream_options'],
        run: async () => {
          const stream = await client.chat.completions.create({
            model: config.model,
            messages: [...baseMessages],
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
            ...resolveOpenAIChatSamplingParams(config.model),
            max_completion_tokens: outputLimit(32),
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
            max_tokens: outputLimit(64),
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
            max_completion_tokens: outputLimit(32),
            stop: ['\n'],
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
            max_completion_tokens: outputLimit(48),
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
    },
    {
      protocol: 'openai.chat',
      modelScope: 'protocol',
      testModel: config.model,
    },
  );
}

export {
  createBaseMessages,
  OPENAI_CHAT_PARAMS,
  isGeminiOpenAICompatibilityTarget,
  isOpenAICompatibilityGateway,
  isReasoningModel,
  resolveChatCompletionOutputLimit,
  resolveReasoningEffort,
  withPromptCacheRetentionFallback,
};

export type {
  OpenAICaseContext,
  PromptCacheRetentionValue,
};
