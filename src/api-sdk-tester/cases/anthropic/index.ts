import type Anthropic from '@anthropic-ai/sdk';

import type { AnthropicProviderConfig } from '../../runtime-config';
import { summarizeAnthropicResponse, truncate, type TestCase } from '../../shared';
import { defineCases } from '../define-cases';

export const ANTHROPIC_MESSAGE_PARAMS = [
  'max_tokens',
  'messages',
  'model',
  'cache_control',
  'container',
  'inference_geo',
  'metadata',
  'output_config',
  'service_tier',
  'stop_sequences',
  'stream',
  'system',
  'temperature',
  'thinking',
  'tool_choice',
  'tools',
  'top_k',
  'top_p',
] as const;

export interface AnthropicCaseContext {
  client: Anthropic;
  config: AnthropicProviderConfig;
}

export function buildAnthropicCases({ client, config }: AnthropicCaseContext): TestCase[] {
  const baseMessages = [{ role: 'user', content: 'Reply with exactly: ok' }] as const;
  const echoTool = {
    name: 'echo',
    description: 'Echoes the provided text.',
    input_schema: {
      type: 'object' as const,
      properties: {
        text: { type: 'string' as const },
      },
      required: ['text'],
      additionalProperties: false,
    },
  };

  const cases = defineCases({
    'basic': {
      description: 'basic messages.create',
      covers: ['max_tokens', 'messages', 'model'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'sampling_and_stop': {
      description: 'temperature/top_p/top_k/stop_sequences',
      covers: ['temperature', 'top_p', 'top_k', 'stop_sequences'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          temperature: 0.2,
          top_p: 0.9,
          top_k: 20,
          stop_sequences: ['<END>'],
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'system_metadata_service_tier': {
      description: 'system + metadata + service_tier',
      covers: ['system', 'metadata', 'service_tier'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          system: 'You are a compatibility test assistant.',
          metadata: {
            user_id: 'llm-spec-user',
          },
          service_tier: 'auto',
          messages: [...baseMessages],
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'output_config_json_schema': {
      description: 'output_config with structured output schema',
      covers: ['output_config'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 96,
          messages: [
            {
              role: 'user',
              content: 'Return JSON object with keys: ok(string), provider(string).',
            },
          ],
          output_config: {
            format: {
              type: 'json_schema',
              schema: {
                type: 'object',
                properties: {
                  ok: { type: 'string' },
                  provider: { type: 'string' },
                },
                required: ['ok', 'provider'],
                additionalProperties: false,
              },
            },
          },
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'tools_auto_choice': {
      description: 'tools + tool_choice auto',
      covers: ['tools', 'tool_choice'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 128,
          messages: [
            {
              role: 'user',
              content: 'Use the echo tool and pass {"text":"hello"}',
            },
          ],
          tools: [echoTool],
          tool_choice: {
            type: 'auto',
          },
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'tools_forced_choice': {
      description: 'tools + tool_choice specific tool',
      covers: ['tools', 'tool_choice'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 128,
          messages: [
            {
              role: 'user',
              content: 'Force call tool echo with text "force".',
            },
          ],
          tools: [echoTool],
          tool_choice: {
            type: 'tool',
            name: 'echo',
            disable_parallel_tool_use: true,
          },
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'stream': {
      description: 'stream=true SSE flow',
      covers: ['stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 96,
          stream: true,
          messages: [
            {
              role: 'user',
              content: 'Count from 1 to 3, very short.',
            },
          ],
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
          if (eventCount >= 200) {
            break;
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'thinking': {
      description: 'extended thinking config',
      covers: ['thinking'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 1200,
          messages: [
            {
              role: 'user',
              content: 'Solve 19*23 quickly, then output only the number.',
            },
          ],
          thinking: {
            type: 'enabled',
            budget_tokens: 1024,
          },
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'cache_control': {
      description: 'top-level cache_control',
      covers: ['cache_control'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          cache_control: {
            type: 'ephemeral',
            ttl: '5m',
          },
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'container': {
      description: 'container reuse id',
      covers: ['container'],
      precondition: () =>
        config.container ? undefined : 'set ANTHROPIC_CONTAINER to enable container test',
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          container: config.container,
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'inference_geo': {
      description: 'inference_geo routing',
      covers: ['inference_geo'],
      precondition: () =>
        config.inferenceGeo ? undefined : 'set ANTHROPIC_INFERENCE_GEO to enable geo test',
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          inference_geo: config.inferenceGeo,
        });
        return summarizeAnthropicResponse(response);
      },
    },
  });

  return cases;
}
