import { defineCases } from '../define-cases';
import { summarizeOpenAIResponses, truncate } from '../runtime';
import type { TestCase } from '../types';
import {
  type OpenAICaseContext,
  type PromptCacheRetentionValue,
  isOpenAICompatibilityGateway,
  isReasoningModel,
  OPENAI_IMAGE_DATA_URI_FIXTURES,
  resolveOpenAIResponsesSamplingParams,
  resolveReasoningEffort,
  withPromptCacheRetentionFallback,
} from '../openai/shared';
import { buildOpenAIResponsesServedModelCases } from '../openai/models';

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

function resolveOpenAIResponsesModelScope(caseId: string): string {
  if (
    caseId === 'responses_reasoning' ||
    caseId === 'responses_reasoning_stream' ||
    caseId === 'responses_reasoning_effort_variants'
  ) {
    return 'reasoning';
  }
  if (caseId === 'responses_prompt' || caseId === 'responses_prompt_stream') {
    return 'prompt-template';
  }
  return 'protocol';
}

export function buildOpenAIResponsesCases({ client, config }: OpenAICaseContext): TestCase[] {
  const compatibilityGateway = isOpenAICompatibilityGateway(config.apiBaseUrl);
  const responsesReasoningModel = config.reasoningModel ?? config.model;
  const reasoningEffortVariants = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh'] as const;
  const promptCacheInput = `${'llm-spec responses cache prefix. '.repeat(384)}Reply with exactly: cache-ok`;

  const functionSchema = {
    type: 'object',
    properties: {
      text: { type: 'string' },
    },
    required: ['text'],
    additionalProperties: false,
  };

  const cases = defineCases(
    {
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
      'responses_input_array_text': {
        description: 'responses input array text variant',
        covers: ['input'],
        run: async () => {
          const response = await client.responses.create({
            model: config.model,
            input: [
              {
                role: 'user',
                content: 'Reply with exactly: ok',
              },
            ],
            max_output_tokens: 32,
          });
          return summarizeOpenAIResponses(response);
        },
      },
      'responses_input_text_image': {
        description: 'responses input text + input_image data URI variants',
        covers: ['input', 'input_image.format'],
        run: async () => {
          const results: string[] = [];

          for (const fixture of OPENAI_IMAGE_DATA_URI_FIXTURES) {
            const response = await client.responses.create(
              {
                model: config.model,
                input: [
                  {
                    role: 'user',
                    content: [
                      {
                        type: 'input_text',
                        text: 'Describe the attached image in one short sentence.',
                      },
                      {
                        type: 'input_image',
                        image_url: fixture.dataUri,
                      },
                    ],
                  },
                ],
                max_output_tokens: 64,
              } as never,
            );
            results.push(`${fixture.format}:${summarizeOpenAIResponses(response)}`);
          }

          return results.join(' | ');
        },
      },
      'responses_input_file_detail': {
        description: 'responses input_file detail low/high variants',
        covers: ['input', 'input_file.detail'],
        precondition: () =>
          compatibilityGateway
            ? `input_file detail targets native OpenAI responses; current gateway=${config.apiBaseUrl ?? '(unknown)'}`
            : undefined,
        run: async () => {
          const fileData = `data:text/plain;base64,${Buffer.from('status: ok\n').toString('base64')}`;
          const results: string[] = [];

          for (const detail of ['low', 'high'] as const) {
            const response = await client.responses.create(
              {
                model: config.model,
                input: [
                  {
                    role: 'user',
                    content: [
                      {
                        type: 'input_text',
                        text: 'Read the attached text file and reply with the status value only.',
                      },
                      {
                        type: 'input_file',
                        file_data: fileData,
                        filename: 'llm-spec-status.txt',
                        detail,
                      },
                    ],
                  },
                ],
                max_output_tokens: 64,
              } as never,
            );
            results.push(`${detail}:${summarizeOpenAIResponses(response)}`);
          }

          return results.join(' | ');
        },
      },
      'responses_assistant_phase_replay': {
        description: 'responses assistant input phase replay',
        covers: ['input', 'input.phase'],
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: [
                {
                  role: 'user',
                  content: 'Prepare a short answer.',
                },
                {
                  role: 'assistant',
                  phase: 'commentary',
                  content: 'I am preparing the concise answer.',
                },
                {
                  role: 'assistant',
                  phase: 'final_answer',
                  content: 'ok',
                },
                {
                  role: 'user',
                  content: 'Reply with exactly: ok',
                },
              ],
              max_output_tokens: 32,
            } as never,
          );
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
            ...resolveOpenAIResponsesSamplingParams(config.model),
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
          const preferredRetention: PromptCacheRetentionValue = 'in_memory';
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
      'responses_prompt_cache_round_trip': {
        description: 'responses prompt_cache_key + prompt_cache_retention round trip',
        covers: ['prompt_cache_key', 'prompt_cache_retention'],
        run: async () => {
          let appliedRetention: PromptCacheRetentionValue = 'in_memory';

          const runCacheRequest = () =>
            withPromptCacheRetentionFallback(
              (retention) => {
                appliedRetention = retention;
                return client.responses.create(
                  {
                    model: config.model,
                    input: promptCacheInput,
                    prompt_cache_key: 'llm-spec-responses-cache-round-trip',
                    prompt_cache_retention: retention,
                    max_output_tokens: 32,
                  } as never,
                );
              },
              appliedRetention,
            );

          const first = await runCacheRequest();
          const second = await runCacheRequest();
          const firstUsage = (first as {
            usage?: {
              input_tokens_details?: {
                cached_tokens?: number;
              };
            };
          }).usage;
          const secondUsage = (second as {
            usage?: {
              input_tokens_details?: {
                cached_tokens?: number;
              };
            };
          }).usage;

          return `retention=${appliedRetention}, first_cached=${firstUsage?.input_tokens_details?.cached_tokens ?? 'n/a'}, second_cached=${secondUsage?.input_tokens_details?.cached_tokens ?? 'n/a'}, ${summarizeOpenAIResponses(second)}`;
        },
      },
      'responses_prompt_cache_retention_24h': {
        description: 'responses prompt_cache_retention 24h',
        covers: ['prompt_cache_key', 'prompt_cache_retention'],
        precondition: () =>
          compatibilityGateway
            ? `24h prompt cache retention targets native OpenAI responses; current gateway=${config.apiBaseUrl ?? '(unknown)'}`
            : undefined,
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: promptCacheInput,
              prompt_cache_key: 'llm-spec-responses-cache-retention-24h',
              prompt_cache_retention: '24h',
              max_output_tokens: 32,
            } as never,
          );
          return summarizeOpenAIResponses(response);
        },
      },
      'responses_context_include_truncation': {
        description: 'responses context_management/include/top_logprobs/truncation',
        covers: ['context_management', 'include', 'top_logprobs', 'truncation'],
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
      'responses_text_format_variants': {
        description: 'responses text.format text/json_object variants',
        covers: ['text'],
        run: async () => {
          const variants = [
            {
              name: 'text',
              input: 'Say hello in one short sentence.',
              format: { type: 'text' },
            },
            {
              name: 'json_object',
              input: 'Return JSON object only: {"status":"ok"}',
              format: { type: 'json_object' },
            },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.responses.create({
              model: config.model,
              input: variant.input,
              text: {
                format: variant.format,
              },
              max_output_tokens: 64,
            });
            results.push(`${variant.name}:${summarizeOpenAIResponses(response)}`);
          }

          return results.join(' | ');
        },
      },
      'responses_tools': {
        description: 'responses tools + tool_choice + parallel + max_tool_calls',
        covers: ['tools', 'tool_choice', 'parallel_tool_calls', 'max_tool_calls'],
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
      'responses_tool_choice_variants': {
        description: 'responses tool_choice none/auto/required variants',
        covers: ['tools', 'tool_choice'],
        run: async () => {
          const results: string[] = [];
          const choices = ['none', 'auto', 'required'] as const;

          for (const toolChoice of choices) {
            const response = await client.responses.create(
              {
                model: config.model,
                input: 'Use the echo tool with text "variant" if tools are allowed.',
                tools: [
                  {
                    type: 'function',
                    name: 'echo',
                    description: 'Echo back input',
                    parameters: functionSchema,
                    strict: true,
                  },
                ],
                tool_choice: toolChoice,
                max_output_tokens: 128,
              } as never,
            );
            const output = (response as { output?: Array<{ type?: string }> }).output ?? [];
            const functionCallCount = output.filter((item) => item.type === 'function_call').length;
            if (toolChoice === 'none' && functionCallCount > 0) {
              throw new Error('expected tool_choice=none to suppress function calls');
            }
            if (toolChoice === 'required' && functionCallCount === 0) {
              throw new Error('expected tool_choice=required to produce a function call');
            }
            results.push(`${toolChoice}:${functionCallCount}`);
          }

          return results.join(', ');
        },
      },
      'responses_parallel_tool_calls_enabled': {
        description: 'responses parallel_tool_calls true',
        covers: ['tools', 'parallel_tool_calls', 'max_tool_calls'],
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: 'Call both echo and echo_extra with short text.',
              tools: [
                {
                  type: 'function',
                  name: 'echo',
                  description: 'Echo back input',
                  parameters: functionSchema,
                  strict: true,
                },
                {
                  type: 'function',
                  name: 'echo_extra',
                  description: 'Echo back extra input',
                  parameters: functionSchema,
                  strict: true,
                },
              ],
              tool_choice: 'required',
              parallel_tool_calls: true,
              max_tool_calls: 2,
              max_output_tokens: 128,
            } as never,
          );
          const output = (response as { output?: Array<{ type?: string }> }).output ?? [];
          const functionCallCount = output.filter((item) => item.type === 'function_call').length;
          if (functionCallCount === 0) {
            throw new Error('expected at least one function_call with parallel_tool_calls=true');
          }
          return `function_calls=${functionCallCount}, ${summarizeOpenAIResponses(response)}`;
        },
      },
      'responses_tool_web_search': {
        description: 'responses web_search tool variant',
        covers: ['tools'],
        precondition: () =>
          compatibilityGateway
            ? `web_search tool is not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
            : undefined,
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: 'Search the web and answer briefly: what is OpenAI?',
              tools: [
                {
                  type: 'web_search',
                  search_context_size: 'low',
                },
              ],
              max_output_tokens: 128,
            } as never,
          );
          return summarizeOpenAIResponses(response);
        },
      },
      'responses_tool_code_interpreter': {
        description: 'responses code_interpreter tool variant',
        covers: ['tools'],
        precondition: () =>
          compatibilityGateway
            ? `code_interpreter tool is not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
            : undefined,
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: 'Use code to calculate 15 * 27 and return only the number.',
              tools: [
                {
                  type: 'code_interpreter',
                },
              ],
              include: ['code_interpreter_call.outputs'],
              max_output_tokens: 128,
            } as never,
          );
          return summarizeOpenAIResponses(response);
        },
      },
      'responses_tool_file_search': {
        description: 'responses file_search tool variant',
        covers: ['tools'],
        precondition: () => {
          if (compatibilityGateway) {
            return `file_search tool is not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`;
          }
          return config.fileSearchVectorStoreId
            ? undefined
            : 'set OPENAI_FILE_SEARCH_VECTOR_STORE_ID to enable file_search tool test';
        },
        run: async () => {
          const response = await client.responses.create(
            {
              model: config.model,
              input: 'Search the provided vector store for documentation and answer briefly.',
              tools: [
                {
                  type: 'file_search',
                  vector_store_ids: [config.fileSearchVectorStoreId],
                },
              ],
              include: ['file_search_call.results'],
              max_output_tokens: 128,
            } as never,
          );
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
            ...resolveOpenAIResponsesSamplingParams(config.model),
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
          const preferredRetention: PromptCacheRetentionValue = 'in_memory';
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
      'responses_reasoning_effort_variants': {
        description: 'responses reasoning.effort all documented variants',
        covers: ['reasoning'],
        precondition: () =>
          isReasoningModel(responsesReasoningModel)
            ? undefined
            : `reasoning is documented for gpt-5/o-series models; current=${responsesReasoningModel}. set OPENAI_REASONING_MODEL to a supported model`,
        run: async () => {
          const results: string[] = [];

          for (const effort of reasoningEffortVariants) {
            const response = await client.responses.create({
              model: responsesReasoningModel,
              input: 'Solve 19*23 quickly, then output only the number.',
              reasoning: {
                effort,
                summary: 'auto',
              },
              max_output_tokens: 96,
            });
            results.push(`${effort}:${summarizeOpenAIResponses(response)}`);
          }

          return results.join(' | ');
        },
      },
      'responses_store_false': {
        description: 'responses store=false variant',
        covers: ['store'],
        run: async () => {
          const response = await client.responses.create({
            model: config.model,
            input: 'Reply with exactly: ok',
            store: false,
            max_output_tokens: 32,
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
    },
    {
      apiType: 'responses',
      protocol: 'openai.responses',
      testModel: config.model,
    },
  );

  return [
    ...cases.map((testCase) => ({
      ...testCase,
      modelScope: resolveOpenAIResponsesModelScope(testCase.id),
      testModel: resolveOpenAIResponsesModelScope(testCase.id) === 'reasoning'
        ? responsesReasoningModel
        : testCase.testModel,
    })),
    ...buildOpenAIResponsesServedModelCases({ client, config }),
  ];
}
