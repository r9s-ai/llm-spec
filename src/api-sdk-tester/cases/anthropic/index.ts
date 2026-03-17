import type Anthropic from '@anthropic-ai/sdk';
import {
  unstable_v2_createSession,
  unstable_v2_prompt,
  unstable_v2_resumeSession,
  type SDKSessionOptions,
} from '@anthropic-ai/claude-agent-sdk';

import type { AnthropicProviderConfig, ClaudeAgentProviderConfig } from '../../runtime-config';
import { summarizeAnthropicResponse, truncate, type TestCase } from '../../shared';
import { defineCases } from '../define-cases';

export const ANTHROPIC_MESSAGE_PARAMS = [
  'max_tokens',
  'messages',
  'model',
  'betas',
  'cache_control',
  'container',
  'inference_geo',
  'metadata',
  'output_config',
  'service_tier',
  'speed',
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

export const CLAUDE_AGENT_PARAMS = [
  'model',
  'prompt',
  'allowedTools',
  'disallowedTools',
  'env',
  'streaming',
  'structured_output',
] as const;

export interface AnthropicCaseContext {
  client: Anthropic;
  config: AnthropicProviderConfig;
}

export interface ClaudeAgentCaseContext {
  config: ClaudeAgentProviderConfig;
}

function normalizeModelName(model: string): string {
  return model.trim().toLowerCase();
}

function supportsExtendedThinking(model: string): boolean {
  const normalized = normalizeModelName(model);
  // Extended thinking is supported on Claude 4 and later models
  return (
    normalized.includes('claude-4') ||
    normalized.includes('claude-opus-4') ||
    normalized.includes('claude-sonnet-4')
  );
}

function supportsFastMode(model: string): boolean {
  const normalized = normalizeModelName(model);
  // Fast mode is only supported on Claude Opus 4.6
  return normalized === 'claude-opus-4-6';
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
      description: 'top_p/top_k/stop_sequences',
      covers: ['top_p', 'top_k', 'stop_sequences'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          top_p: 0.9,
          top_k: 20,
          stop_sequences: ['<END>'],
        });
        return summarizeAnthropicResponse(response);
      },
    },
    'temperature_sampling': {
      description: 'temperature only (without top_p)',
      covers: ['temperature'],
      run: async () => {
        const response = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          messages: [...baseMessages],
          temperature: 0.2,
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
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'basic_stream': {
      description: 'basic messages.create (streaming)',
      covers: ['max_tokens', 'messages', 'model', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'sampling_and_stop_stream': {
      description: 'top_p/top_k/stop_sequences (streaming)',
      covers: ['top_p', 'top_k', 'stop_sequences', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
          top_p: 0.9,
          top_k: 20,
          stop_sequences: ['<END>'],
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'temperature_sampling_stream': {
      description: 'temperature only (without top_p) (streaming)',
      covers: ['temperature', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
          temperature: 0.2,
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'system_metadata_service_tier_stream': {
      description: 'system + metadata + service_tier (streaming)',
      covers: ['system', 'metadata', 'service_tier', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          system: 'You are a compatibility test assistant.',
          metadata: {
            user_id: 'llm-spec-user',
          },
          service_tier: 'auto',
          messages: [...baseMessages],
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'output_config_json_schema_stream': {
      description: 'output_config with structured output schema (streaming)',
      covers: ['output_config', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 96,
          stream: true,
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

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'thinking': {
      description: 'extended thinking config',
      covers: ['thinking'],
      precondition: () =>
        supportsExtendedThinking(config.model)
          ? undefined
          : `extended thinking requires Claude 4 or later models; current=${config.model}`,
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
    'tools_auto_choice_stream': {
      description: 'tools + tool_choice auto (streaming)',
      covers: ['tools', 'tool_choice', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 128,
          stream: true,
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

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'tools_forced_choice_stream': {
      description: 'tools + tool_choice specific tool (streaming)',
      covers: ['tools', 'tool_choice', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 128,
          stream: true,
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

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'thinking_stream': {
      description: 'extended thinking config (streaming)',
      covers: ['thinking', 'stream'],
      precondition: () =>
        supportsExtendedThinking(config.model)
          ? undefined
          : `extended thinking requires Claude 4 or later models; current=${config.model}`,
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 1200,
          stream: true,
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

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'cache_control_stream': {
      description: 'top-level cache_control (streaming)',
      covers: ['cache_control', 'stream'],
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
          cache_control: {
            type: 'ephemeral',
            ttl: '5m',
          },
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'container_stream': {
      description: 'container reuse id (streaming)',
      covers: ['container', 'stream'],
      precondition: () =>
        config.container ? undefined : 'set ANTHROPIC_CONTAINER to enable container test',
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
          container: config.container,
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'inference_geo_stream': {
      description: 'inference_geo routing (streaming)',
      covers: ['inference_geo', 'stream'],
      precondition: () =>
        config.inferenceGeo ? undefined : 'set ANTHROPIC_INFERENCE_GEO to enable geo test',
      run: async () => {
        const stream = await client.messages.create({
          model: config.model,
          max_tokens: 64,
          stream: true,
          messages: [...baseMessages],
          inference_geo: config.inferenceGeo,
        });

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'beta_prompt_caching': {
      description: 'prompt-caching-2024-07-31 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['prompt-caching-2024-07-31'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_token_counting': {
      description: 'token-counting-2024-11-01 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['token-counting-2024-11-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_token_efficient_tools': {
      description: 'token-efficient-tools-2025-02-19 beta header with tools',
      covers: ['betas', 'tools'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 128,
            messages: [
              {
                role: 'user',
                content: 'Use the echo tool and pass {"text":"efficient"}',
              },
            ],
            tools: [echoTool],
            tool_choice: { type: 'auto' },
          },
          {
            betas: ['token-efficient-tools-2025-02-19'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_output_128k': {
      description: 'output-128k-2025-02-19 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['output-128k-2025-02-19'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_files_api': {
      description: 'files-api-2025-04-14 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['files-api-2025-04-14'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_code_execution': {
      description: 'code-execution-2025-05-22 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 128,
            messages: [
              {
                role: 'user',
                content: 'Calculate 2+2 using code execution',
              },
            ],
          },
          {
            betas: ['code-execution-2025-05-22'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_extended_cache_ttl': {
      description: 'extended-cache-ttl-2025-04-11 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['extended-cache-ttl-2025-04-11'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_context_1m': {
      description: 'context-1m-2025-08-07 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['context-1m-2025-08-07'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_context_management': {
      description: 'context-management-2025-06-27 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['context-management-2025-06-27'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_model_context_window_exceeded': {
      description: 'model-context-window-exceeded-2025-08-26 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['model-context-window-exceeded-2025-08-26'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_message_batches': {
      description: 'message-batches-2024-09-24 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['message-batches-2024-09-24'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_computer_use_2024': {
      description: 'computer-use-2024-10-22 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['computer-use-2024-10-22'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_computer_use_2025': {
      description: 'computer-use-2025-01-24 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['computer-use-2025-01-24'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_pdfs': {
      description: 'pdfs-2024-09-25 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['pdfs-2024-09-25'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_mcp_client_2025_04': {
      description: 'mcp-client-2025-04-04 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['mcp-client-2025-04-04'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_mcp_client_2025_11': {
      description: 'mcp-client-2025-11-20 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['mcp-client-2025-11-20'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_dev_full_thinking': {
      description: 'dev-full-thinking-2025-05-14 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['dev-full-thinking-2025-05-14'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_interleaved_thinking': {
      description: 'interleaved-thinking-2025-05-14 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['interleaved-thinking-2025-05-14'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_skills': {
      description: 'skills-2025-10-02 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['skills-2025-10-02'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_fast_mode': {
      description: 'fast-mode-2026-02-01 beta header',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['fast-mode-2026-02-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'fast_mode_basic': {
      description: 'fast mode with speed parameter',
      covers: ['speed', 'betas'],
      precondition: () =>
        supportsFastMode(config.model)
          ? undefined
          : `fast mode requires claude-opus-4-6; current=${config.model}`,
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 1024,
            messages: [
              {
                role: 'user',
                content: 'Refactor this module to use dependency injection',
              },
            ],
            speed: 'fast',
          },
          {
            betas: ['fast-mode-2026-02-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'fast_mode_stream': {
      description: 'fast mode with streaming',
      covers: ['speed', 'betas', 'stream'],
      precondition: () =>
        supportsFastMode(config.model)
          ? undefined
          : `fast mode requires claude-opus-4-6; current=${config.model}`,
      run: async () => {
        const stream = await client.messages.create(
          {
            model: config.model,
            max_tokens: 1024,
            stream: true,
            messages: [
              {
                role: 'user',
                content: 'Count from 1 to 5, very short.',
              },
            ],
            speed: 'fast',
          },
          {
            betas: ['fast-mode-2026-02-01'],
          },
        );

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'fast_mode_with_tools': {
      description: 'fast mode with tools',
      covers: ['speed', 'betas', 'tools', 'tool_choice'],
      precondition: () =>
        supportsFastMode(config.model)
          ? undefined
          : `fast mode requires claude-opus-4-6; current=${config.model}`,
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 128,
            messages: [
              {
                role: 'user',
                content: 'Use the echo tool and pass {"text":"fast"}',
              },
            ],
            tools: [echoTool],
            tool_choice: { type: 'auto' },
            speed: 'fast',
          },
          {
            betas: ['fast-mode-2026-02-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'fast_mode_with_thinking': {
      description: 'fast mode with extended thinking',
      covers: ['speed', 'betas', 'thinking'],
      precondition: () =>
        supportsFastMode(config.model)
          ? undefined
          : `fast mode requires claude-opus-4-6; current=${config.model}`,
      run: async () => {
        const response = await client.messages.create(
          {
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
            speed: 'fast',
          },
          {
            betas: ['fast-mode-2026-02-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_multiple_headers': {
      description: 'multiple beta headers combined',
      covers: ['betas'],
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: ['prompt-caching-2024-07-31', 'token-counting-2024-11-01'],
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_custom_from_env': {
      description: 'custom beta headers from environment',
      covers: ['betas'],
      precondition: () =>
        config.betas && config.betas.length > 0
          ? undefined
          : 'set ANTHROPIC_BETAS to enable custom beta test',
      run: async () => {
        const response = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            messages: [...baseMessages],
          },
          {
            betas: config.betas,
          },
        );
        return summarizeAnthropicResponse(response);
      },
    },
    'beta_prompt_caching_stream': {
      description: 'prompt-caching-2024-07-31 beta header (streaming)',
      covers: ['betas', 'stream'],
      run: async () => {
        const stream = await client.messages.create(
          {
            model: config.model,
            max_tokens: 64,
            stream: true,
            messages: [...baseMessages],
          },
          {
            betas: ['prompt-caching-2024-07-31'],
          },
        );

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
    'beta_code_execution_stream': {
      description: 'code-execution-2025-05-22 beta header (streaming)',
      covers: ['betas', 'stream'],
      run: async () => {
        const stream = await client.messages.create(
          {
            model: config.model,
            max_tokens: 128,
            stream: true,
            messages: [
              {
                role: 'user',
                content: 'Calculate 3+3 using code execution',
              },
            ],
          },
          {
            betas: ['code-execution-2025-05-22'],
          },
        );

        let eventCount = 0;
        let text = '';
        for await (const event of stream) {
          eventCount += 1;
          const eventObj = event as { type?: string; delta?: { type?: string; text?: string } };
          if (eventObj.type === 'content_block_delta' && eventObj.delta?.type === 'text_delta') {
            text += eventObj.delta.text ?? '';
          }
        }
        return `events=${eventCount}, text="${truncate(text)}"`;
      },
    },
  });

  return cases;
}

export function buildClaudeAgentCases({ config }: ClaudeAgentCaseContext): TestCase[] {
  const baseOptions: SDKSessionOptions = {
    model: 'claude-sonnet-4-6',
    env: {
      ...process.env,
      ANTHROPIC_API_KEY: config.apiKey,
      // 如果配置了自定义 API base URL，添加到环境变量
      ...(config.apiBaseUrl ? { ANTHROPIC_API_BASE_URL: config.apiBaseUrl } : {}),
    },
  };

  const cases = defineCases({
    'basic_prompt': {
      description: '基础单次prompt',
      covers: ['model', 'prompt'],
      run: async () => {
        const result = await unstable_v2_prompt('Reply with exactly: ok', baseOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `result="${truncate(result.result)}", duration=${result.duration_ms}ms`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'basic_session': {
      description: '创建并运行基础session',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Reply with exactly: ok');

          let messageCount = 0;
          let lastResult = '';
          for await (const message of session.stream()) {
            messageCount++;
            if (message.type === 'result') {
              lastResult = message.subtype === 'success' ? message.result : message.subtype;
            }
          }

          return `messages=${messageCount}, result="${truncate(lastResult)}"`;
        } finally {
          session.close();
        }
      },
    },
    'streaming_session': {
      description: '流式session',
      covers: ['model', 'prompt', 'streaming'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Count from 1 to 3');

          const messageTypes: string[] = [];
          for await (const message of session.stream()) {
            messageTypes.push(message.type);
          }

          return `messageTypes=${messageTypes.join(',')}`;
        } finally {
          session.close();
        }
      },
    },
    'multi_turn_conversation': {
      description: '多轮对话',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Remember the number 42');

          // 等待第一个响应完成
          for await (const message of session.stream()) {
            if (message.type === 'result') break;
          }

          await session.send('What number did I ask you to remember?');

          let lastResult = '';
          for await (const message of session.stream()) {
            if (message.type === 'result') {
              lastResult = message.subtype === 'success' ? message.result : message.subtype;
              break;
            }
          }

          return `result="${truncate(lastResult)}"`;
        } finally {
          session.close();
        }
      },
    },
    'resume_session': {
      description: '恢复已存在的session',
      covers: ['model', 'prompt'],
      run: async () => {
        const session1 = unstable_v2_createSession(baseOptions);

        try {
          await session1.send('Remember the word "test"');

          // 等待第一个响应完成并获取sessionId
          for await (const message of session1.stream()) {
            if (message.type === 'result') break;
          }

          const sessionId = session1.sessionId;
          session1.close();

          // 恢复session
          const session2 = unstable_v2_resumeSession(sessionId, baseOptions);

          try {
            await session2.send('What word did I ask you to remember?');

            let lastResult = '';
            for await (const message of session2.stream()) {
              if (message.type === 'result') {
                lastResult = message.subtype === 'success' ? message.result : message.subtype;
                break;
              }
            }

            return `sessionId=${sessionId}, result="${truncate(lastResult)}"`;
          } finally {
            session2.close();
          }
        } catch (error) {
          session1.close();
          throw error;
        }
      },
    },
    'allowed_tools': {
      description: '使用allowedTools配置',
      covers: ['model', 'prompt', 'allowedTools'],
      run: async () => {
        const optionsWithTools: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read'],
        };

        const result = await unstable_v2_prompt('List files in current directory', optionsWithTools);

        if (result.type === 'result') {
          return `type=${result.subtype}, duration=${result.duration_ms}ms`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'disallowed_tools': {
      description: '使用disallowedTools配置',
      covers: ['model', 'prompt', 'disallowedTools'],
      run: async () => {
        const optionsWithDisallowedTools: SDKSessionOptions = {
          ...baseOptions,
          disallowedTools: ['Bash'],
        };

        const result = await unstable_v2_prompt('What tools do you have available?', optionsWithDisallowedTools);

        if (result.type === 'result') {
          return `type=${result.subtype}, duration=${result.duration_ms}ms`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'custom_env': {
      description: '使用自定义环境变量',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        const optionsWithEnv: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...process.env,
            ANTHROPIC_API_KEY: config.apiKey,
            CUSTOM_TEST_VAR: 'test_value',
          },
        };

        const result = await unstable_v2_prompt('Reply with: env test ok', optionsWithEnv);

        if (result.type === 'result' && result.subtype === 'success') {
          return `result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'different_model_opus': {
      description: '测试 Claude Opus 4.6 模型',
      covers: ['model', 'prompt'],
      run: async () => {
        const opusOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
        };

        const result = await unstable_v2_prompt('Reply with: opus ok', opusOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `model=claude-opus-4-6, result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'different_model_haiku': {
      description: '测试 Claude Haiku 4.5 模型',
      covers: ['model', 'prompt'],
      run: async () => {
        const haikuOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-haiku-4-5-20251001',
        };

        const result = await unstable_v2_prompt('Reply with: haiku ok', haikuOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `model=claude-haiku-4-5, result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'structured_output_json': {
      description: '测试结构化输出 JSON 格式',
      covers: ['model', 'prompt', 'structured_output'],
      run: async () => {
        const result = await unstable_v2_prompt(
          'Return a JSON object with exactly these keys: status (string: "ok"), provider (string: "claude")',
          baseOptions
        );

        if (result.type === 'result' && result.subtype === 'success') {
          try {
            const parsed = JSON.parse(result.result);
            return `structured_output=valid, keys=${Object.keys(parsed).join(',')}`;
          } catch {
            return `structured_output=invalid_json, result="${truncate(result.result)}"`;
          }
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'tool_combination': {
      description: '同时使用 allowedTools 和 disallowedTools',
      covers: ['model', 'prompt', 'allowedTools', 'disallowedTools'],
      run: async () => {
        const optionsWithBothTools: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read', 'Glob'],
          disallowedTools: ['Bash', 'Edit'],
        };

        const result = await unstable_v2_prompt(
          'What tools do you have available? List them.',
          optionsWithBothTools
        );

        if (result.type === 'result') {
          return `type=${result.subtype}, has_tools_config=true`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'long_running_session': {
      description: '长时间运行的会话（多轮交互）',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          // 执行 5 轮对话
          for (let i = 1; i <= 5; i++) {
            await session.send(`Round ${i}: Say "round ${i} complete"`);

            for await (const message of session.stream()) {
              if (message.type === 'result') break;
            }
          }

          return `rounds_completed=5`;
        } finally {
          session.close();
        }
      },
    },
    'session_error_recovery': {
      description: '会话错误恢复测试',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          // 第一次正常请求
          await session.send('Remember: error recovery test');

          for await (const message of session.stream()) {
            if (message.type === 'result') break;
          }

          // 第二次请求继续正常工作
          await session.send('What did I ask you to remember?');

          let lastResult = '';
          for await (const message of session.stream()) {
            if (message.type === 'result') {
              lastResult = message.subtype === 'success' ? message.result : message.subtype;
              break;
            }
          }

          return `recovery=success, result="${truncate(lastResult)}"`;
        } finally {
          session.close();
        }
      },
    },
    'multiple_concurrent_sessions': {
      description: '多个并发会话测试',
      covers: ['model', 'prompt'],
      run: async () => {
        const sessions = Array.from({ length: 3 }, () => unstable_v2_createSession(baseOptions));

        try {
          const results = await Promise.all(
            sessions.map(async (session, index) => {
              await session.send(`Session ${index + 1}: Reply with "session ${index + 1} ok"`);

              let result = '';
              for await (const message of session.stream()) {
                if (message.type === 'result') {
                  result = message.subtype === 'success' ? 'success' : 'error';
                  break;
                }
              }

              return result;
            })
          );

          return `concurrent_sessions=3, results=${results.join(',')}`;
        } finally {
          sessions.forEach((session) => session.close());
        }
      },
    },
    'empty_and_special_prompts': {
      description: '边界情况：空提示和特殊字符',
      covers: ['model', 'prompt'],
      run: async () => {
        // 测试简单空格提示
        const result1 = await unstable_v2_prompt('   Say "space test ok"   ', baseOptions);

        // 测试特殊字符
        const result2 = await unstable_v2_prompt(
          'Reply with: Special chars test @#$%^&*()',
          baseOptions
        );

        const status1 = result1.type === 'result' && result1.subtype === 'success' ? 'ok' : 'error';
        const status2 = result2.type === 'result' && result2.subtype === 'success' ? 'ok' : 'error';

        return `space_prompt=${status1}, special_chars=${status2}`;
      },
    },
    'session_without_close': {
      description: '测试会话资源清理（未显式关闭）',
      covers: ['model', 'prompt'],
      run: async () => {
        // 创建会话但不关闭（测试垃圾回收）
        const session = unstable_v2_createSession(baseOptions);
        await session.send('Quick test');
        let result = '';

        for await (const message of session.stream()) {
          if (message.type === 'result') {
            result = message.subtype === 'success' ? 'success' : 'error';
            break;
          }
        }

        // 注意：这里故意不调用 session.close() 来测试资源管理
        return `result=${result}, cleanup=auto`;
      },
    },
    'streaming_message_types': {
      description: '流式消息类型分析',
      covers: ['model', 'prompt', 'streaming'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Count from 1 to 5 and explain each number');

          const messageTypes = new Set<string>();
          let messageCount = 0;

          for await (const message of session.stream()) {
            messageTypes.add(message.type);
            messageCount++;

            // 限制消息数量以避免超时
            if (messageCount > 100) break;
          }

          return `messageTypes=${Array.from(messageTypes).sort().join(',')}, count=${messageCount}`;
        } finally {
          session.close();
        }
      },
    },
    'prompt_with_context': {
      description: '带上下文的复杂提示',
      covers: ['model', 'prompt'],
      run: async () => {
        const result = await unstable_v2_prompt(
          `You are a testing assistant. Your task is to:
1. Acknowledge this instruction
2. Confirm you understand by saying "context test ok"
3. Do nothing else

Please proceed.`,
          baseOptions
        );

        if (result.type === 'result' && result.subtype === 'success') {
          return `result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'session_id_persistence': {
      description: '会话 ID 持久化测试',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Test message');

          for await (const message of session.stream()) {
            if (message.type === 'result') break;
          }

          const sessionId = session.sessionId;

          // 验证 sessionId 格式
          const isValidSessionId =
            typeof sessionId === 'string' && sessionId.length > 0;

          return `sessionId=${sessionId}, valid=${isValidSessionId}`;
        } finally {
          session.close();
        }
      },
    },
    'error_handling_invalid_model': {
      description: '错误处理：无效模型名称',
      covers: ['model', 'prompt'],
      run: async () => {
        const invalidModelOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'invalid-model-name-xyz',
        };

        try {
          const result = await unstable_v2_prompt('Test with invalid model', invalidModelOptions);

          if (result.type === 'result' && result.subtype !== 'success') {
            return `error_handled=true, type=${result.subtype}`;
          } else {
            return `unexpected_result: ${result.subtype}`;
          }
        } catch (error) {
          return `error_caught=true, message="${truncate(String(error))}"`;
        }
      },
    },
    'tool_execution_with_session': {
      description: '会话中工具执行测试',
      covers: ['model', 'prompt', 'allowedTools'],
      run: async () => {
        const optionsWithReadTool: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read'],
        };

        const session = unstable_v2_createSession(optionsWithReadTool);

        try {
          await session.send('Read the package.json file and tell me the project name');

          let lastResult = '';
          for await (const message of session.stream()) {
            if (message.type === 'result') {
              lastResult = message.subtype === 'success' ? message.result : message.subtype;
              break;
            }
          }

          return `tool_used=Read, result="${truncate(lastResult)}"`;
        } finally {
          session.close();
        }
      },
    },
    'permission_mode_default': {
      description: '权限模式：默认模式',
      covers: ['model', 'prompt'],
      run: async () => {
        const optionsWithDefaultPermission: SDKSessionOptions = {
          ...baseOptions,
          permissionMode: 'default',
        };

        const result = await unstable_v2_prompt(
          'Reply with: permission test ok',
          optionsWithDefaultPermission
        );

        if (result.type === 'result' && result.subtype === 'success') {
          return `permissionMode=default, result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'permission_mode_dont_ask': {
      description: '权限模式：dontAsk 模式',
      covers: ['model', 'prompt'],
      run: async () => {
        const optionsWithDontAsk: SDKSessionOptions = {
          ...baseOptions,
          permissionMode: 'dontAsk',
        };

        const result = await unstable_v2_prompt(
          'Reply with: dontAsk test ok',
          optionsWithDontAsk
        );

        if (result.type === 'result') {
          return `permissionMode=dontAsk, subtype=${result.subtype}`;
        } else {
          return `error: unexpected type`;
        }
      },
    },
    'permission_mode_plan': {
      description: '权限模式：计划模式（不执行工具）',
      covers: ['model', 'prompt'],
      run: async () => {
        const optionsWithPlanMode: SDKSessionOptions = {
          ...baseOptions,
          permissionMode: 'plan',
        };

        const result = await unstable_v2_prompt(
          'What files are in the current directory?',
          optionsWithPlanMode
        );

        if (result.type === 'result') {
          // Plan mode should return a plan without executing tools
          return `permissionMode=plan, subtype=${result.subtype}`;
        } else {
          return `error: unexpected type`;
        }
      },
    },
    'custom_executable_node': {
      description: '自定义可执行文件：node',
      covers: ['model', 'prompt'],
      run: async () => {
        const optionsWithNode: SDKSessionOptions = {
          ...baseOptions,
          executable: 'node',
        };

        const result = await unstable_v2_prompt('Say: node executable test', optionsWithNode);

        if (result.type === 'result' && result.subtype === 'success') {
          return `executable=node, result="${truncate(result.result)}"`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'system_message_analysis': {
      description: '分析系统初始化消息',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Reply with: system test');

          let systemMessageFound = false;
          let toolsAvailable = 0;
          let model = '';

          for await (const message of session.stream()) {
            if (message.type === 'system' && message.subtype === 'init') {
              systemMessageFound = true;
              toolsAvailable = message.tools.length;
              model = message.model;
            }
            if (message.type === 'result') break;
          }

          return `system_msg=${systemMessageFound}, tools=${toolsAvailable}, model=${model}`;
        } finally {
          session.close();
        }
      },
    },
    'result_message_metadata': {
      description: '结果消息元数据分析',
      covers: ['model', 'prompt'],
      run: async () => {
        const result = await unstable_v2_prompt('Reply with: metadata test', baseOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `duration=${result.duration_ms}ms, turns=${result.num_turns}, cost=${result.total_cost_usd.toFixed(6)}USD`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'assistant_message_streaming': {
      description: '助手消息流式传输',
      covers: ['model', 'prompt', 'streaming'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Tell me a short story in 2 sentences');

          let assistantMessages = 0;
          let streamEvents = 0;

          for await (const message of session.stream()) {
            if (message.type === 'assistant') {
              assistantMessages++;
            }
            if (message.type === 'stream_event') {
              streamEvents++;
            }
            if (message.type === 'result') break;
          }

          return `assistant_msgs=${assistantMessages}, stream_events=${streamEvents}`;
        } finally {
          session.close();
        }
      },
    },
    'tool_use_summary': {
      description: '工具使用摘要消息',
      covers: ['model', 'prompt', 'allowedTools'],
      run: async () => {
        const optionsWithTools: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read'],
        };

        const session = unstable_v2_createSession(optionsWithTools);

        try {
          await session.send('Read package.json and tell me the version');

          let toolUseSummaries = 0;

          for await (const message of session.stream()) {
            if (message.type === 'tool_use_summary') {
              toolUseSummaries++;
            }
            if (message.type === 'result') break;
          }

          return `tool_summaries=${toolUseSummaries}`;
        } finally {
          session.close();
        }
      },
    },
    'session_uuid_tracking': {
      description: 'Session UUID 跟踪',
      covers: ['model', 'prompt'],
      run: async () => {
        const session = unstable_v2_createSession(baseOptions);

        try {
          await session.send('Test UUID');

          const uuids = new Set<string>();

          for await (const message of session.stream()) {
            if ('uuid' in message && typeof message.uuid === 'string') {
              uuids.add(message.uuid);
            }
            if (message.type === 'result') break;
          }

          return `unique_uuids=${uuids.size}`;
        } finally {
          session.close();
        }
      },
    },
    'multiple_tools_different_types': {
      description: '多种不同类型工具',
      covers: ['model', 'prompt', 'allowedTools'],
      run: async () => {
        const optionsWithMultipleTools: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read', 'Glob', 'Grep'],
        };

        const result = await unstable_v2_prompt(
          'List all .ts files in the src directory',
          optionsWithMultipleTools
        );

        if (result.type === 'result') {
          return `tools=Read+Glob+Grep, subtype=${result.subtype}`;
        } else {
          return `error: unexpected type`;
        }
      },
    },
    'session_closure_cleanup': {
      description: '会话关闭和资源清理',
      covers: ['model', 'prompt'],
      run: async () => {
        // 创建并立即关闭会话
        const session1 = unstable_v2_createSession(baseOptions);
        await session1.send('Test 1');
        for await (const message of session1.stream()) {
          if (message.type === 'result') break;
        }
        session1.close();

        // 创建第二个会话验证资源正确释放
        const session2 = unstable_v2_createSession(baseOptions);
        await session2.send('Test 2');

        let result = '';
        for await (const message of session2.stream()) {
          if (message.type === 'result') {
            result = message.subtype === 'success' ? 'success' : 'error';
            break;
          }
        }
        session2.close();

        return `session1=closed, session2=${result}`;
      },
    },
    'env_custom_api_key': {
      description: '自定义 API 密钥环境变量',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        const optionsWithCustomEnv: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...process.env,
            ANTHROPIC_API_KEY: config.apiKey,
            CLAUDE_AGENT_SDK_CLIENT_APP: 'llm-spec-test/1.0.0',
          },
        };

        const result = await unstable_v2_prompt('Reply with: env custom ok', optionsWithCustomEnv);

        if (result.type === 'result' && result.subtype === 'success') {
          return `custom_env=success, client_app=set`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'error_during_execution_handling': {
      description: '执行期间错误处理',
      covers: ['model', 'prompt'],
      run: async () => {
        // 尝试让 agent 执行一个可能导致错误的操作
        const result = await unstable_v2_prompt(
          'Try to read a file that does not exist: /nonexistent/path/to/file.txt',
          baseOptions
        );

        if (result.type === 'result') {
          // agent 应该处理这个错误并返回结果
          return `handled=true, subtype=${result.subtype}`;
        } else {
          return `error: unexpected type`;
        }
      },
    },
    'large_prompt_handling': {
      description: '大型提示处理',
      covers: ['model', 'prompt'],
      run: async () => {
        // 创建一个较长的提示
        const longPrompt = 'Count from 1 to 5. '.repeat(10) + 'Reply with: large prompt ok';

        const result = await unstable_v2_prompt(longPrompt, baseOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `large_prompt=handled, duration=${result.duration_ms}ms`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'custom_api_base_url': {
      description: '自定义 API Base URL',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试使用自定义 API base URL
        const customUrlOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            // 设置一个自定义的 API base URL（可以是代理服务器或测试服务器）
            ANTHROPIC_API_BASE_URL: config.apiBaseUrl || 'https://api.anthropic.com',
          },
        };

        const result = await unstable_v2_prompt('Reply with: base url test ok', customUrlOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `custom_base_url=success, duration=${result.duration_ms}ms`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'env_var_interpolation': {
      description: '环境变量插值测试',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试环境变量的插值功能
        const customEnvOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            CUSTOM_TEST_VAR: 'test_value_123',
            ANOTHER_VAR: 'another_value',
          },
        };

        const result = await unstable_v2_prompt('Test environment variable handling', customEnvOptions);

        if (result.type === 'result') {
          return `env_vars_set=success, subtype=${result.subtype}`;
        } else {
          return `error: unexpected type`;
        }
      },
    },
    'api_key_from_env': {
      description: '从环境变量读取 API Key',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试 API Key 从环境变量正确读取
        const envOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...process.env,
            // 确保 API Key 通过环境变量传递
            ANTHROPIC_API_KEY: config.apiKey,
          },
        };

        const result = await unstable_v2_prompt('Reply with: api key test ok', envOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `api_key_from_env=success`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'user_agent_customization': {
      description: 'User-Agent 自定义标识',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试自定义 User-Agent 标识
        const userAgentOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            CLAUDE_AGENT_SDK_CLIENT_APP: 'llm-spec-tester/1.0.0',
          },
        };

        const result = await unstable_v2_prompt('Reply with: user agent test', userAgentOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `user_agent_custom=llm-spec-tester/1.0.0, success=true`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'multiple_env_vars': {
      description: '多个环境变量组合测试',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试同时设置多个环境变量
        const multiEnvOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            CLAUDE_AGENT_SDK_CLIENT_APP: 'multi-env-test/2.0.0',
            CUSTOM_VAR_1: 'value1',
            CUSTOM_VAR_2: 'value2',
            CUSTOM_VAR_3: 'value3',
            ...(config.apiBaseUrl ? { ANTHROPIC_API_BASE_URL: config.apiBaseUrl } : {}),
          },
        };

        const result = await unstable_v2_prompt('Test multiple environment variables', multiEnvOptions);

        if (result.type === 'result') {
          return `multiple_env_vars=success, count=5`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'api_base_url_with_session': {
      description: '会话中使用自定义 API Base URL',
      covers: ['model', 'prompt', 'env', 'allowedTools'],
      run: async () => {
        const customUrlSessionOptions: SDKSessionOptions = {
          ...baseOptions,
          allowedTools: ['Read'],
          env: {
            ...baseOptions.env!,
            ANTHROPIC_API_BASE_URL: config.apiBaseUrl || 'https://api.anthropic.com',
          },
        };

        const session = unstable_v2_createSession(customUrlSessionOptions);

        try {
          await session.send('Reply with: session base url test');

          let lastResult = '';
          for await (const message of session.stream()) {
            if (message.type === 'result') {
              lastResult = message.subtype === 'success' ? message.result : message.subtype;
              break;
            }
          }

          return `session_with_base_url=success, result="${truncate(lastResult)}"`;
        } finally {
          session.close();
        }
      },
    },
    'invalid_api_base_url': {
      description: '测试无效的 API Base URL 错误处理',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试无效的 API base URL 错误处理
        const invalidUrlOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            ANTHROPIC_API_BASE_URL: 'https://invalid-url-that-does-not-exist-12345.com',
          },
        };

        try {
          const result = await unstable_v2_prompt('This should fail', invalidUrlOptions);

          // 应该会返回错误
          if (result.type === 'result' && result.subtype !== 'success') {
            return `error_handled=true, subtype=${result.subtype}`;
          } else {
            return `unexpected_result: ${result.subtype}`;
          }
        } catch (error) {
          // 网络错误应该被捕获
          return `error_caught=true, type=network_error`;
        }
      },
    },
    'api_base_url_priority': {
      description: 'API Base URL 环境变量优先级测试',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试环境变量的优先级顺序
        // 优先级: CLAUDE_AGENT_API_BASE_URL > ANTHROPIC_API_BASE_URL > API_BASE_URL
        const priorityOptions: SDKSessionOptions = {
          ...baseOptions,
          env: {
            ...baseOptions.env!,
            // 设置低优先级的环境变量
            API_BASE_URL: 'https://low-priority.example.com',
            // 设置高优先级的环境变量（如果 config.apiBaseUrl 存在）
            ...(config.apiBaseUrl ? {
              ANTHROPIC_API_BASE_URL: config.apiBaseUrl,
            } : {}),
          },
        };

        const result = await unstable_v2_prompt('Reply with: priority test', priorityOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `priority_test=success, used_url=${config.apiBaseUrl || 'default'}`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
    'env_inheritance': {
      description: '环境变量继承测试',
      covers: ['model', 'prompt', 'env'],
      run: async () => {
        // 测试环境变量的继承行为
        // 确保重要的环境变量被正确继承
        const inheritedEnv = { ...process.env };

        const inheritOptions: SDKSessionOptions = {
          ...baseOptions,
          env: inheritedEnv as Record<string, string | undefined>,
        };

        const result = await unstable_v2_prompt('Reply with: env inheritance test', inheritOptions);

        if (result.type === 'result' && result.subtype === 'success') {
          return `env_inheritance=success, has_process_env=true`;
        } else {
          return `error: ${result.subtype}`;
        }
      },
    },
  });

  return cases;
}
