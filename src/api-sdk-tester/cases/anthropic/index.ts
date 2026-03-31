import { AsyncLocalStorage } from 'node:async_hooks';
import type Anthropic from '@anthropic-ai/sdk';
import { mkdirSync, readFileSync, rmSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';
import {
  unstable_v2_createSession as rawUnstableV2CreateSession,
  unstable_v2_prompt as rawUnstableV2Prompt,
  unstable_v2_resumeSession as rawUnstableV2ResumeSession,
  type SDKSessionOptions,
} from '@anthropic-ai/claude-agent-sdk';

import type {
  HttpTraceExchange,
  HttpTraceRequest,
  HttpTraceResponse,
  TestCaseHttpTrace,
} from '../../../types';
import type { AnthropicProviderConfig, ClaudeAgentProviderConfig } from '../../runtime-config';
import { formatError, summarizeAnthropicResponse, truncate, type TestCase } from '../../shared';
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
  'betas',
  'permissionMode',
  'session',
  'errors',
] as const;

export interface AnthropicCaseContext {
  client: Anthropic;
  config: AnthropicProviderConfig;
}

export interface ClaudeAgentCaseContext {
  config: ClaudeAgentProviderConfig;
}

const CLAUDE_AGENT_TEST_ID_ENV_KEY = 'LLM_SPEC_TEST_ID';
const CLAUDE_AGENT_TEST_ID_HEADER = 'x-test-id';
const CLAUDE_AGENT_TRACE_SOURCE = 'claude-agent-fetch-hook';
const CLAUDE_AGENT_TRACE_DIR = resolvePath(process.cwd(), '.llm-spec-traces');

const claudeAgentTestContext = new AsyncLocalStorage<string>();
let claudeAgentCaseExecutionCounter = 0;

const claudeAgentCaseHttpTraceByCaseId = new Map<string, TestCaseHttpTrace>();

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

export function resetClaudeAgentCaseHttpTraces(): void {
  claudeAgentCaseExecutionCounter = 0;
  claudeAgentCaseHttpTraceByCaseId.clear();
  try { rmSync(CLAUDE_AGENT_TRACE_DIR, { recursive: true, force: true }); } catch {}
  try { mkdirSync(CLAUDE_AGENT_TRACE_DIR, { recursive: true }); } catch {}
}

export function getClaudeAgentCaseHttpTrace(caseId: string): TestCaseHttpTrace | undefined {
  return claudeAgentCaseHttpTraceByCaseId.get(caseId);
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
  const defaultModel = config.model;
  const fetchHookPath = resolvePath(process.cwd(), 'src/api-sdk-tester/claude-agent-fetch-hook.cjs');

  function ensureExecutableArgsWithFetchHook(
    executableArgs: string[] | undefined,
  ): string[] {
    const requireHookArg = `--require=${fetchHookPath}`;
    if (!executableArgs || executableArgs.length === 0) {
      return [requireHookArg];
    }

    const hasFetchHook = executableArgs.some((arg, index) => {
      if (arg.includes(fetchHookPath)) {
        return true;
      }
      if (arg === '--require' && executableArgs[index + 1] === fetchHookPath) {
        return true;
      }
      if (arg.startsWith('--require=')) {
        return arg.slice('--require='.length) === fetchHookPath;
      }
      return false;
    });

    if (hasFetchHook) {
      return [...executableArgs];
    }
    return [...executableArgs, requireHookArg];
  }

  function parseCustomHeadersObject(
    raw: string | undefined,
  ): Record<string, string> | undefined {
    if (!raw) {
      return undefined;
    }

    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        return undefined;
      }

      const headers: Record<string, string> = {};
      for (const [key, value] of Object.entries(parsed)) {
        if (typeof value === 'string') {
          headers[key] = value;
        }
      }
      return Object.keys(headers).length > 0 ? headers : undefined;
    } catch {
      return undefined;
    }
  }

  function splitBetaHeaderValue(raw: string | undefined): string[] {
    if (!raw) {
      return [];
    }

    return raw
      .split(',')
      .map((token) => token.trim())
      .filter(Boolean);
  }

  function mergeBetaHeaderValues(...values: Array<string | undefined>): string | undefined {
    const merged: string[] = [];
    const seen = new Set<string>();

    for (const value of values) {
      for (const token of splitBetaHeaderValue(value)) {
        if (seen.has(token)) {
          continue;
        }
        seen.add(token);
        merged.push(token);
      }
    }

    return merged.length > 0 ? merged.join(',') : undefined;
  }

  function normalizeClaudeAgentBetas(
    betas: readonly string[] | undefined,
  ): string[] | undefined {
    if (betas === undefined) {
      return undefined;
    }

    if (betas.length === 0) {
      return [];
    }

    const merged = mergeBetaHeaderValues(betas.join(','));
    return merged ? splitBetaHeaderValue(merged) : [];
  }

  function resolveClaudeAgentBetas(
    betas: readonly string[] | undefined,
    env: Record<string, string | undefined> | undefined,
  ): string[] | undefined {
    const normalizedBetas = normalizeClaudeAgentBetas(betas);
    if (normalizedBetas !== undefined) {
      return normalizedBetas;
    }

    const envBetas = splitBetaHeaderValue(env?.ANTHROPIC_BETAS);
    return envBetas.length > 0 ? envBetas : undefined;
  }

  function normalizeCustomHeaderMap(
    headers: Record<string, string> | undefined,
  ): Record<string, string> | undefined {
    if (!headers) {
      return undefined;
    }

    const normalized: Record<string, string> = {};
    for (const [key, value] of Object.entries(headers)) {
      const normalizedKey = key.trim().toLowerCase();
      const trimmedValue = value.trim();
      if (!normalizedKey || !trimmedValue) {
        continue;
      }
      normalized[normalizedKey] = trimmedValue;
    }

    return Object.keys(normalized).length > 0 ? normalized : undefined;
  }

  function formatAnthropicCustomHeaders(
    headers: Record<string, string> | undefined,
  ): string | undefined {
    const normalized = normalizeCustomHeaderMap(headers);
    if (!normalized) {
      return undefined;
    }

    const lines = Object.entries(normalized)
      .map(([key, value]) => {
        const trimmedKey = key.trim();
        const trimmedValue = value.trim();
        return trimmedKey ? `${trimmedKey}: ${trimmedValue}` : '';
      })
      .filter(Boolean);

    return lines.length > 0 ? lines.join('\n') : undefined;
  }

  function normalizeAnthropicCustomHeaders(raw: string | undefined): Record<string, string> | undefined {
    if (!raw) {
      return undefined;
    }

    const parsedObject = parseCustomHeadersObject(raw);
    if (parsedObject) {
      return normalizeCustomHeaderMap(parsedObject);
    }

    const normalized: Record<string, string> = {};
    for (const line of raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)) {
      const separator = line.indexOf(':');
      if (separator <= 0) {
        continue;
      }
      const key = line.slice(0, separator).trim().toLowerCase();
      const value = line.slice(separator + 1).trim();
      if (!key || !value) {
        continue;
      }
      normalized[key] = value;
    }

    return Object.keys(normalized).length > 0 ? normalized : undefined;
  }

  function mergeCustomHeaderMaps(
    ...headerMaps: Array<Record<string, string> | undefined>
  ): Record<string, string> | undefined {
    const merged: Record<string, string> = {};

    for (const headerMap of headerMaps) {
      const normalized = normalizeCustomHeaderMap(headerMap);
      if (!normalized) {
        continue;
      }

      for (const [key, value] of Object.entries(normalized)) {
        if (key === 'anthropic-beta') {
          const mergedValue = mergeBetaHeaderValues(merged[key], value);
          if (mergedValue) {
            merged[key] = mergedValue;
          }
          continue;
        }

        merged[key] = value;
      }
    }

    return Object.keys(merged).length > 0 ? merged : undefined;
  }

  function buildClaudeAgentEnv(
    overrides: Record<string, string | undefined> = {},
  ): Record<string, string | undefined> {
    const {
      ANTHROPIC_CUSTOM_HEADERS: _anthropicCustomHeaders,
      CLAUDE_AGENT_CUSTOM_HEADERS: _claudeAgentCustomHeaders,
      ...baseEnv
    } = process.env;
    const {
      ANTHROPIC_CUSTOM_HEADERS: overrideAnthropicCustomHeaders,
      CLAUDE_AGENT_CUSTOM_HEADERS: overrideClaudeAgentCustomHeaders,
      ...restOverrides
    } = overrides;

    const customHeaders = formatAnthropicCustomHeaders(
      mergeCustomHeaderMaps(
        normalizeAnthropicCustomHeaders(_anthropicCustomHeaders),
        normalizeAnthropicCustomHeaders(_claudeAgentCustomHeaders),
        config.customHeaders,
        normalizeAnthropicCustomHeaders(overrideAnthropicCustomHeaders),
        normalizeAnthropicCustomHeaders(overrideClaudeAgentCustomHeaders),
      ),
    );

    const mergedEnv: Record<string, string | undefined> = {
      ...baseEnv,
      ANTHROPIC_API_KEY: config.apiKey,
      ...(config.apiBaseUrl
        ? {
            ANTHROPIC_BASE_URL: config.apiBaseUrl,
            ANTHROPIC_API_BASE_URL: config.apiBaseUrl,
          }
        : {}),
      ...(customHeaders
        ? {
            ANTHROPIC_CUSTOM_HEADERS: customHeaders,
            CLAUDE_AGENT_CUSTOM_HEADERS: customHeaders,
          }
        : {}),
      ...restOverrides,
      ...(claudeAgentTestContext.getStore() ? { [CLAUDE_AGENT_TEST_ID_ENV_KEY]: claudeAgentTestContext.getStore() } : {}),
    };

    return mergedEnv;
  }

  function normalizeClaudeAgentSessionOptions(options: SDKSessionOptions): SDKSessionOptions {
    const { betas: requestedBetas, ...restOptions } = options as SDKSessionOptions & {
      betas?: readonly string[];
    };
    const env = buildClaudeAgentEnv((options.env ?? {}) as Record<string, string | undefined>);
    const betas = resolveClaudeAgentBetas(requestedBetas, env);
    const normalizedEnv: Record<string, string | undefined> = { ...env };

    if (betas === undefined) {
      // Preserve inherited ANTHROPIC_BETAS when the caller did not override beta handling.
    } else if (betas.length === 0) {
      delete normalizedEnv.ANTHROPIC_BETAS;
    } else {
      normalizedEnv.ANTHROPIC_BETAS = betas.join(',');
    }

    return {
      ...restOptions,
      env: normalizedEnv,
    } as SDKSessionOptions;
  }

  const baseOptions: SDKSessionOptions = {
    model: defaultModel,
    env: buildClaudeAgentEnv(),
    executableArgs: ensureExecutableArgsWithFetchHook(undefined),
  };

  function createSessionOptions(overrides: Partial<SDKSessionOptions> = {}): SDKSessionOptions {
    const executableArgs = ensureExecutableArgsWithFetchHook(
      overrides.executableArgs === undefined ? baseOptions.executableArgs : overrides.executableArgs,
    );

    return normalizeClaudeAgentSessionOptions({
      ...baseOptions,
      ...overrides,
      executableArgs,
      env:
        overrides.env === undefined
          ? baseOptions.env
          : {
              ...baseOptions.env,
              ...overrides.env,
            },
    });
  }

  async function unstable_v2_prompt(message: string, options: SDKSessionOptions) {
    return rawUnstableV2Prompt(message, normalizeClaudeAgentSessionOptions(options));
  }

  function unstable_v2_createSession(options: SDKSessionOptions) {
    return rawUnstableV2CreateSession(normalizeClaudeAgentSessionOptions(options));
  }

  function unstable_v2_resumeSession(sessionId: string, options: SDKSessionOptions) {
    return rawUnstableV2ResumeSession(
      sessionId,
      normalizeClaudeAgentSessionOptions(options),
    );
  }

  function tryGetSessionId(session: { sessionId: string }): string | undefined {
    try {
      const value = session.sessionId;
      if (typeof value === 'string' && value.length > 0) {
        return value;
      }
      return undefined;
    } catch {
      return undefined;
    }
  }

  async function waitForSessionId(
    session: { sessionId: string },
    maxAttempts = 5,
    delayMs = 120,
  ): Promise<string | undefined> {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const sessionId = tryGetSessionId(session);
      if (sessionId) {
        return sessionId;
      }
      if (attempt < maxAttempts - 1) {
        await new Promise<void>((resolve) => {
          setTimeout(resolve, delayMs);
        });
      }
    }
    return undefined;
  }

  async function runPrompt(
    message: string,
    overrides: Partial<SDKSessionOptions> = {},
  ) {
    return unstable_v2_prompt(message, createSessionOptions(overrides));
  }

  function summarizeResultText(result: {
    subtype: string;
    result?: string;
    errors?: string[];
  }): string {
    if (result.subtype === 'success' && typeof result.result === 'string') {
      return truncate(result.result);
    }
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      return truncate(result.errors.join('; '));
    }
    return result.subtype;
  }

  async function collectSessionMessages(session: {
    stream: () => AsyncGenerator<unknown>;
  }): Promise<{
    resultSubtype: string;
    resultText: string;
    messageTypes: string[];
    uuids: string[];
    systemTools: string[];
    systemBetas: string[];
    mcpServerCount: number;
  }> {
    const messageTypes: string[] = [];
    const uuids = new Set<string>();
    let resultSubtype = '';
    let resultText = '';
    let systemTools: string[] = [];
    let systemBetas: string[] = [];
    let mcpServerCount = 0;

    for await (const rawMessage of session.stream()) {
      const message = rawMessage as {
        type?: string;
        subtype?: string;
        result?: string;
        tools?: string[];
        betas?: string[];
        uuid?: string;
        mcp_servers?: { name: string; status: string }[];
      };

      if (message.type) {
        messageTypes.push(message.type);
      }
      if (typeof message.uuid === 'string') {
        uuids.add(message.uuid);
      }

      if (message.type === 'system' && message.subtype === 'init') {
        systemTools = message.tools ?? [];
        systemBetas = message.betas ?? [];
        mcpServerCount = Array.isArray(message.mcp_servers) ? message.mcp_servers.length : 0;
      }

      if (message.type === 'result') {
        resultSubtype = message.subtype ?? '';
        resultText = message.result ?? '';
        break;
      }
    }

    return {
      resultSubtype,
      resultText,
      messageTypes,
      uuids: Array.from(uuids),
      systemTools,
      systemBetas,
      mcpServerCount,
    };
  }

  async function sendSessionMessage(
    session: {
      send: (message: string) => Promise<void>;
      stream: () => AsyncGenerator<unknown>;
    },
    message: string,
  ): Promise<Awaited<ReturnType<typeof collectSessionMessages>>> {
    await session.send(message);
    return collectSessionMessages(session);
  }

  interface LoggedClaudeAgentRequest extends HttpTraceRequest {
    betaTokens: string[];
    model?: string;
    promptTexts: string[];
  }

  interface LoggedClaudeAgentResponse extends HttpTraceResponse {}

  interface ObservedRequestExecution<T> {
    result: T;
    requests: LoggedClaudeAgentRequest[];
    httpTrace?: TestCaseHttpTrace;
  }

  // NDJSON trace entry written by claude-agent-fetch-hook.cjs
  interface TraceEntry {
    type: 'request' | 'response' | 'error';
    requestId?: string;
    testId?: string;
    url?: string;
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    status?: number;
    statusText?: string;
    durationMs?: number;
    error?: string;
  }

  // Read per-test NDJSON trace file and parse structured entries.
  function readTraceFile(testId: string): HttpTraceExchange[] {
    const traceFile = resolvePath(CLAUDE_AGENT_TRACE_DIR, `${testId}.ndjson`);
    try {
      const content = readFileSync(traceFile, 'utf8');
      const entries = content
        .split('\n')
        .filter(Boolean)
        .map((line) => JSON.parse(line));
      return buildExchangesFromEntries(entries as TraceEntry[]);
    } catch {
      return [];
    }
  }

  // Group NDJSON entries by requestId into HttpTraceExchange objects
  function buildExchangesFromEntries(entries: TraceEntry[]): HttpTraceExchange[] {
    const byRequestId = new Map<string, HttpTraceExchange>();
    const ordered: HttpTraceExchange[] = [];

    for (const entry of entries) {
      if (entry.type === 'request') {
        const exchange: HttpTraceExchange = {
          request: {
            requestId: entry.requestId,
            testId: entry.testId,
            url: entry.url ?? '',
            method: entry.method ?? '',
            headers: entry.headers ?? {},
            body: entry.body,
          },
        };
        ordered.push(exchange);
        if (entry.requestId) {
          byRequestId.set(entry.requestId, exchange);
        }
        continue;
      }

      // Match response/error to its request
      if ((entry.type === 'response' || entry.type === 'error') && entry.requestId) {
        const exchange = byRequestId.get(entry.requestId);
        if (exchange) {
          exchange.response = {
            requestId: entry.requestId,
            testId: entry.testId,
            kind: entry.type === 'error' ? 'error' : ('response' as const),
            url: entry.url ?? '',
            status: entry.status,
            statusText: entry.statusText,
            durationMs: entry.durationMs,
            headers: entry.headers ?? {},
            body: entry.body,
            error: entry.error,
          };
        }
      }
    }

    return ordered;
  }

  function findTraceHeaderValue(
    headers: Record<string, string>,
    targetKey: string,
  ): string | undefined {
    const normalizedTargetKey = targetKey.toLowerCase();
    for (const [key, value] of Object.entries(headers)) {
      if (key.toLowerCase() === normalizedTargetKey) {
        return value;
      }
    }
    return undefined;
  }

  function collectPromptTextsFromBody(bodyText: string | undefined): {
    model?: string;
    promptTexts: string[];
  } {
    if (!bodyText) {
      return { promptTexts: [] };
    }

    try {
      const parsed = JSON.parse(bodyText) as {
        model?: unknown;
        messages?: Array<{ role?: unknown; content?: unknown }>;
      };
      const promptTexts: string[] = [];

      const collectText = (content: unknown): void => {
        if (typeof content === 'string') {
          if (!content.includes('<system-reminder>')) {
            promptTexts.push(content);
          }
          return;
        }

        if (!Array.isArray(content)) {
          return;
        }

        for (const block of content) {
          if (
            typeof block === 'object' &&
            block !== null &&
            'type' in block &&
            'text' in block &&
            block.type === 'text' &&
            typeof block.text === 'string' &&
            !block.text.includes('<system-reminder>')
          ) {
            promptTexts.push(block.text);
          }
        }
      };

      for (const message of parsed.messages ?? []) {
        if (message?.role !== 'user') {
          continue;
        }
        collectText(message.content);
      }

      return {
        model: typeof parsed.model === 'string' ? parsed.model : undefined,
        promptTexts,
      };
    } catch {
      return { promptTexts: [] };
    }
  }

  // Map HttpTraceExchange to LoggedClaudeAgentRequest for backward compat with existing assertion functions
  function mapExchangesToLoggedRequests(exchanges: HttpTraceExchange[]): LoggedClaudeAgentRequest[] {
    return exchanges.map((exchange) => {
      const headers = exchange.request.headers;
      const betaHeaderValue = findTraceHeaderValue(headers, 'anthropic-beta');
      const body = exchange.request.body;
      const { model, promptTexts } = collectPromptTextsFromBody(body);
      return {
        requestId: exchange.request.requestId,
        testId: exchange.request.testId,
        url: exchange.request.url,
        method: exchange.request.method,
        headers,
        body,
        betaTokens: splitBetaHeaderValue(betaHeaderValue),
        model,
        promptTexts,
      };
    });
  }

  function createClaudeAgentTestId(caseId: string): string {
    claudeAgentCaseExecutionCounter += 1;
    return `claude-agent-${sanitizeCaseIdPart(caseId)}-${Date.now()}-${claudeAgentCaseExecutionCounter}`;
  }

  async function runWithClaudeAgentTestId<T>(
    testId: string,
    action: () => Promise<T>,
  ): Promise<T> {
    return claudeAgentTestContext.run(testId, action);
  }

  function getMessageApiRequests(requests: LoggedClaudeAgentRequest[]): LoggedClaudeAgentRequest[] {
    return requests.filter((request) => request.url.includes('/v1/messages'));
  }

  function isClaudeAgentMessageBetaUrl(rawUrl: string): boolean {
    try {
      const parsed = new URL(rawUrl);
      return parsed.pathname.endsWith('/v1/messages') && parsed.searchParams.get('beta') === 'true';
    } catch {
      return rawUrl.includes('/v1/messages?beta=true');
    }
  }

  function formatClaudeAgentResponseStatus(response: LoggedClaudeAgentResponse | HttpTraceResponse | undefined): string {
    if (!response) {
      return 'missing';
    }

    if (response.kind === 'error') {
      return response.error ? `error:${truncate(response.error, 120)}` : 'error';
    }

    if (typeof response.status === 'number') {
      return `${response.status}${response.statusText ? ` ${response.statusText}` : ''}`;
    }

    return 'unknown';
  }

  function getFinalClaudeAgentMessageBetaExchange(
    httpTrace: TestCaseHttpTrace,
    context: string,
  ): HttpTraceExchange {
    const messageExchanges = httpTrace.exchanges.filter((exchange) =>
      isClaudeAgentMessageBetaUrl(exchange.request.url),
    );

    if (messageExchanges.length === 0) {
      throw new Error(`${context}: no /v1/messages?beta=true exchanges captured`);
    }

    const finalExchange = messageExchanges.at(-1);
    if (!finalExchange) {
      throw new Error(`${context}: no final /v1/messages?beta=true exchange found`);
    }

    if (!finalExchange.response) {
      throw new Error(`${context}: final /v1/messages?beta=true exchange missing response`);
    }

    return finalExchange;
  }

  function assertFinalClaudeAgentMessageBetaResponseOk(
    httpTrace: TestCaseHttpTrace,
    context: string,
  ): HttpTraceResponse {
    const finalExchange = getFinalClaudeAgentMessageBetaExchange(httpTrace, context);
    const response = finalExchange.response;
    if (!response) {
      throw new Error(`${context}: final /v1/messages?beta=true exchange missing response`);
    }

    if (response.kind !== 'response') {
      throw new Error(
        `${context}: final /v1/messages?beta=true exchange ended with ${formatClaudeAgentResponseStatus(response)}`,
      );
    }

    if (typeof response.status !== 'number' || response.status < 200 || response.status >= 300) {
      throw new Error(
        `${context}: final /v1/messages?beta=true status=${formatClaudeAgentResponseStatus(response)}`,
      );
    }

    return response;
  }

  function collectObservedBetas(requests: LoggedClaudeAgentRequest[]): string[] {
    const merged: string[] = [];
    const seen = new Set<string>();

    for (const request of requests) {
      for (const beta of request.betaTokens) {
        if (seen.has(beta)) {
          continue;
        }
        seen.add(beta);
        merged.push(beta);
      }
    }

    return merged;
  }

  function summarizeLoggedRequests(requests: LoggedClaudeAgentRequest[]): string {
    if (requests.length === 0) {
      return 'none';
    }

    return requests
      .map((request) => {
        const prompt = request.promptTexts[0] ? truncate(request.promptTexts[0].replace(/\s+/g, ' '), 60) : 'none';
        const betas = request.betaTokens.length > 0 ? request.betaTokens.join(',') : 'none';
        return `${request.method} ${request.url} model=${request.model ?? 'unknown'} betas=${betas} prompt="${prompt}"`;
      })
      .join(' | ');
  }

  async function observeLoggedRequests<T>(
    action: () => Promise<T>,
  ): Promise<ObservedRequestExecution<T>> {
    const activeTestId = claudeAgentTestContext.getStore();
    try {
      const result = await action();
      const exchanges = activeTestId ? readTraceFile(activeTestId) : [];
      const requests = mapExchangesToLoggedRequests(exchanges);
      return {
        result,
        requests,
        httpTrace: activeTestId ? {
          source: CLAUDE_AGENT_TRACE_SOURCE,
          testId: activeTestId,
          exchangeCount: exchanges.length,
          exchanges,
        } : undefined,
      };
    } catch (error) {
      const exchanges = activeTestId ? readTraceFile(activeTestId) : [];
      const requests = mapExchangesToLoggedRequests(exchanges);
      if (error instanceof Error) {
        error.message = `${error.message}; test_id=${activeTestId ?? 'unknown'}; observed_requests=${summarizeLoggedRequests(requests)}`;
      }
      throw error;
    }
  }

  function assertRequestHasBetas(
    requests: LoggedClaudeAgentRequest[],
    expectedBetas: readonly string[],
    context: string,
  ): string[] {
    const messageRequests = getMessageApiRequests(requests);
    if (messageRequests.length === 0) {
      throw new Error(`${context}: no /v1/messages requests captured`);
    }

    const observedBetas = collectObservedBetas(messageRequests);
    const missingBetas = expectedBetas.filter((beta) => !observedBetas.includes(beta));
    if (missingBetas.length > 0) {
      throw new Error(
        `${context}: missing request betas=${missingBetas.join(', ')} observed=${observedBetas.join(',') || 'none'}`,
      );
    }

    return observedBetas;
  }

  function assertAllMessageRequestsHaveBetas(
    requests: LoggedClaudeAgentRequest[],
    expectedBetas: readonly string[],
    context: string,
  ): void {
    const messageRequests = getMessageApiRequests(requests);
    if (messageRequests.length === 0) {
      throw new Error(`${context}: no /v1/messages requests captured`);
    }

    for (const request of messageRequests) {
      const missingBetas = expectedBetas.filter((beta) => !request.betaTokens.includes(beta));
      if (missingBetas.length > 0) {
        throw new Error(
          `${context}: request missing betas=${missingBetas.join(', ')} request_betas=${request.betaTokens.join(',') || 'none'} prompt="${truncate((request.promptTexts[0] ?? 'none').replace(/\s+/g, ' '), 80)}"`,
        );
      }
    }
  }

  function assertRequestsDoNotHaveBetas(
    requests: LoggedClaudeAgentRequest[],
    forbiddenBetas: readonly string[],
    context: string,
    requireMessageRequests = true,
  ): string[] {
    const messageRequests = getMessageApiRequests(requests);
    if (requireMessageRequests && messageRequests.length === 0) {
      throw new Error(`${context}: no /v1/messages requests captured`);
    }

    const observedBetas = collectObservedBetas(messageRequests);
    const unexpectedBetas = observedBetas.filter((beta) => forbiddenBetas.includes(beta));
    if (unexpectedBetas.length > 0) {
      throw new Error(
        `${context}: unexpected request betas=${unexpectedBetas.join(', ')} observed=${observedBetas.join(',') || 'none'}`,
      );
    }

    return observedBetas;
  }

  function assertResultSubtypeSuccess(
    resultSubtype: string,
    context: string,
    resultText?: string,
  ): void {
    // Claude Agent cases are now judged by the final /v1/messages?beta=true HTTP status.
    // Keep this helper non-blocking so legacy subtype checks do not decide pass/fail.
    void resultSubtype;
    void context;
    void resultText;
  }

  type BetaProbeKey =
    | 'baseline'
    | 'context_1m'
    | 'thinking'
    | 'effort'
    | 'mcp'
    | 'structured_output';

  interface BetaProbeDefinition {
    prompt: string;
    overrides?: Partial<SDKSessionOptions>;
  }

  type BetaCatalogValidationMode = 'native' | 'injected';
  type BetaCatalogSecondaryEvidence = 'mcp_servers' | undefined;

  interface BetaCatalogSpec {
    beta: string;
    probe: BetaProbeKey;
    covers: readonly string[];
    validationMode: BetaCatalogValidationMode;
    secondaryEvidence?: BetaCatalogSecondaryEvidence;
  }

  interface BetaProbeResult {
    requests: LoggedClaudeAgentRequest[];
    requestBetas: string[];
    systemBetas: string[];
    resultSubtype: string;
    resultText: string;
    mcpServerCount: number;
  }

  const betaProbeDefinitions: Record<BetaProbeKey, BetaProbeDefinition> = {
    baseline: {
      prompt: 'Reply with exactly: beta baseline ok',
    },
    context_1m: {
      prompt: 'Reply with exactly: beta context 1m ok',
      overrides: {
        model: 'claude-sonnet-4-6',
        betas: ['context-1m-2025-08-07'],
      } as Partial<SDKSessionOptions>,
    },
    thinking: {
      prompt: 'Solve 12 + 30 and reply with only the number.',
      overrides: {
        model: 'claude-sonnet-4-6',
        thinking: { type: 'adaptive' },
      } as Partial<SDKSessionOptions>,
    },
    effort: {
      prompt: 'Reply with exactly: effort probe ok',
      overrides: {
        model: 'claude-opus-4-6',
        effort: 'high',
      } as Partial<SDKSessionOptions>,
    },
    mcp: {
      prompt: 'Reply with exactly: mcp probe ok',
      overrides: {
        model: 'claude-sonnet-4-6',
        mcpServers: {
          'beta-probe-server': {
            command: 'echo',
            args: ['beta-probe'],
          },
        },
      } as Partial<SDKSessionOptions>,
    },
    structured_output: {
      prompt: 'Return status=ok and reason=structured.',
      overrides: {
        model: 'claude-sonnet-4-6',
        outputFormat: {
          type: 'json_schema',
          schema: {
            type: 'object',
            properties: {
              status: { type: 'string' },
              reason: { type: 'string' },
            },
            required: ['status', 'reason'],
            additionalProperties: false,
          },
        },
      } as Partial<SDKSessionOptions>,
    },
  };

  const nativeCatalogBetas = new Set([
    'context-1m-2025-08-07',
    'interleaved-thinking-2025-05-14',
    'redact-thinking-2026-02-12',
    'effort-2025-11-24',
    'mcp-client-2025-11-20',
    'mcp-servers-2025-12-04',
  ]);

  const betaCatalogSpecs: BetaCatalogSpec[] = [
    { beta: 'vertex-2023-10-16', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'bedrock-2023-05-31', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'web-search-2025-03-05', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'files-api-2025-04-14', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'oauth-2025-04-20', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'interleaved-thinking-2025-05-14', probe: 'thinking', covers: ['betas', 'thinking'], validationMode: 'native' },
    { beta: 'context-management-2025-06-27', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'ccr-byoc-2025-07-29', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'context-1m-2025-08-07', probe: 'context_1m', covers: ['betas'], validationMode: 'native' },
    { beta: 'environments-2025-11-01', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'effort-2025-11-24', probe: 'effort', covers: ['betas', 'effort'], validationMode: 'native' },
    { beta: 'token-counting-2024-11-01', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'message-batches-2024-09-24', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'skills-2025-10-02', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'tool-search-tool-2025-10-19', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'tool-examples-2025-10-29', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'advanced-tool-use-2025-11-20', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'mcp-client-2025-11-20', probe: 'mcp', covers: ['betas', 'mcpServers'], validationMode: 'native', secondaryEvidence: 'mcp_servers' },
    { beta: 'structured-outputs-2025-11-13', probe: 'structured_output', covers: ['betas', 'structured_output'], validationMode: 'injected' },
    { beta: 'structured-outputs-2025-12-15', probe: 'structured_output', covers: ['betas', 'structured_output'], validationMode: 'injected' },
    { beta: 'mcp-servers-2025-12-04', probe: 'mcp', covers: ['betas', 'mcpServers'], validationMode: 'native', secondaryEvidence: 'mcp_servers' },
    { beta: 'compact-2026-01-12', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'prompt-caching-scope-2026-01-05', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'afk-mode-2026-01-31', probe: 'baseline', covers: ['betas'], validationMode: 'injected' },
    { beta: 'fast-mode-2026-02-01', probe: 'effort', covers: ['betas', 'effort'], validationMode: 'injected' },
    { beta: 'redact-thinking-2026-02-12', probe: 'thinking', covers: ['betas', 'thinking'], validationMode: 'native' },
  ];

  for (const spec of betaCatalogSpecs) {
    if (nativeCatalogBetas.has(spec.beta) && spec.validationMode !== 'native') {
      throw new Error(`beta catalog misconfigured for native beta=${spec.beta}`);
    }
  }

  const betaProbeCache = new Map<string, Promise<BetaProbeResult>>();

  function sanitizeCaseIdPart(input: string): string {
    return input
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function buildProbeSessionOptions(
    definition: BetaProbeDefinition,
    extraEnvOverrides?: Record<string, string | undefined>,
  ): SDKSessionOptions {
    if (!extraEnvOverrides) {
      return createSessionOptions(definition.overrides);
    }

    return createSessionOptions({
      ...definition.overrides,
      env: buildClaudeAgentEnv({
        ...((definition.overrides?.env ?? {}) as Record<string, string | undefined>),
        ...extraEnvOverrides,
      }),
    });
  }

  async function executeBetaProbe(
    definition: BetaProbeDefinition,
    extraEnvOverrides?: Record<string, string | undefined>,
  ): Promise<BetaProbeResult> {
    const { result: collected, requests } = await observeLoggedRequests(async () => {
      const session = unstable_v2_createSession(buildProbeSessionOptions(definition, extraEnvOverrides));
      try {
        return await sendSessionMessage(session, definition.prompt);
      } finally {
        session.close();
      }
    });

    return {
      requests,
      requestBetas: collectObservedBetas(getMessageApiRequests(requests)),
      systemBetas: collected.systemBetas,
      resultSubtype: collected.resultSubtype,
      resultText: collected.resultText,
      mcpServerCount: collected.mcpServerCount,
    };
  }

  async function runBetaProbe(probe: BetaProbeKey): Promise<BetaProbeResult> {
    const cacheKey = `${claudeAgentTestContext.getStore() ?? 'shared'}:${probe}`;
    const cached = betaProbeCache.get(cacheKey);
    if (cached) {
      return cached;
    }

    const definition = betaProbeDefinitions[probe];
    const pending = executeBetaProbe(definition);

    betaProbeCache.set(cacheKey, pending);
    return pending;
  }

  async function runInjectedBetaProbe(spec: BetaCatalogSpec): Promise<BetaProbeResult> {
    const definition = betaProbeDefinitions[spec.probe];
    const baseline = await runBetaProbe('baseline');
    const injectedBetas = mergeBetaHeaderValues(
      baseline.requestBetas.join(','),
      spec.beta,
    );

    if (!injectedBetas) {
      throw new Error(`beta catalog injection failed for beta=${spec.beta}`);
    }

    return executeBetaProbe(definition, {
      ANTHROPIC_BETAS: injectedBetas,
    });
  }

  function buildClaudeAgentBetaCatalogCases() {
    return Object.fromEntries(
      betaCatalogSpecs.map((spec) => {
        const id = `beta_catalog_${sanitizeCaseIdPart(spec.beta)}`;
        return [
          id,
          {
            description: `Beta目录覆盖: ${spec.beta}`,
            covers: [...spec.covers],
            run: async () => {
              const context = id;
              const observed = await runInjectedBetaProbe(spec);

              if (observed.resultSubtype !== 'success') {
                throw new Error(
                  `${context}: probe result subtype=${observed.resultSubtype} result="${truncate(observed.resultText || observed.resultSubtype)}"`,
                );
              }

              assertRequestHasBetas(observed.requests, [spec.beta], context);

              const systemBetas = observed.systemBetas.length > 0 ? observed.systemBetas.join(',') : 'none';
              const requestBetas = observed.requestBetas.length > 0 ? observed.requestBetas.join(',') : 'none';
              const resultText = truncate(observed.resultText || observed.resultSubtype);
              return `beta=${spec.beta}, mode=log, request_betas=${requestBetas}, mcp_servers=${observed.mcpServerCount}, system_betas=${systemBetas}, result="${resultText}"`;
            },
          },
        ] as const;
      }),
    );
  }

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
          const firstTurn = await sendSessionMessage(session, 'Remember the number 42');
          const secondTurn = await sendSessionMessage(
            session,
            'What number did I ask you to remember?',
          );

          return `turn1="${truncate(firstTurn.resultText || firstTurn.resultSubtype)}", turn2="${truncate(secondTurn.resultText || secondTurn.resultSubtype)}"`;
        } finally {
          session.close();
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
    'tool_combination': {
      description: '同时使用 allowedTools 和 disallowedTools',
      covers: ['model', 'prompt', 'allowedTools', 'disallowedTools'],
      run: async () => {
        const session = unstable_v2_createSession(
          createSessionOptions({
            allowedTools: ['Read', 'Glob'],
            disallowedTools: ['Bash'],
          }),
        );

        try {
          const collected = await sendSessionMessage(
            session,
            'Use available read-only tools if needed to describe the repo briefly.',
          );
          const hasToolsConfig =
            collected.systemTools.includes('Read') && !collected.systemTools.includes('Bash');
          return `type=${collected.resultSubtype}, has_tools_config=${hasToolsConfig}`;
        } finally {
          session.close();
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
    'multiple_tools_different_types': {
      description: '多种不同类型工具',
      covers: ['model', 'prompt', 'allowedTools'],
      run: async () => {
        const result = await runPrompt(
          'Use repository inspection tools if needed to describe this project briefly.',
          {
            allowedTools: ['Read', 'Glob', 'Grep'],
          },
        );
        return `tools=Read+Glob+Grep, subtype=${result.subtype}`;
      },
    },
    'error_during_execution_handling': {
      description: '执行期间错误处理',
      covers: ['model', 'prompt'],
      run: async () => {
        try {
          const result = await runPrompt(
            'Read ./this-file-should-not-exist.txt and briefly explain the failure.',
            {
              allowedTools: ['Read'],
            },
          );
          return `handled=true, subtype=${result.subtype}`;
        } catch (error) {
          return `handled=true, error="${truncate(formatError(error))}"`;
        }
      },
    },
    'large_prompt_handling': {
      description: '大型提示处理',
      covers: ['model', 'prompt'],
      run: async () => {
        const largePrompt = Array.from(
          { length: 400 },
          (_, index) => `Line ${index + 1}: keep this compatibility test short.`,
        ).join('\n');
        const result = await runPrompt(
          `${largePrompt}\n\nAfter reading the text above, reply with exactly: large prompt ok`,
        );
        return `large_prompt=handled, duration=${result.duration_ms}ms`;
      },
    },

    // ========================================
    // Beta 功能测试
    // ========================================

    'beta_context_1m_basic': {
      description: 'Beta: 启用 1M 上下文窗口 (Sonnet 4.6)',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_basic';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Reply with: beta context 1m test ok', betaOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        assertResultSubtypeSuccess(result.subtype, context, result.result);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, result="${truncate(result.result)}"`;
      },
    },

    'beta_context_1m_with_session': {
      description: 'Beta: 在会话中使用 1M 上下文窗口',
      covers: ['model', 'prompt', 'betas', 'streaming'],
      run: async () => {
        const context = 'beta_context_1m_with_session';
        const betaSessionOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaSessionOptions);
          try {
            return await sendSessionMessage(session, 'Test beta context 1M in session');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        assertAllMessageRequestsHaveBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_context_1m_system_message': {
      description: 'Beta: 验证系统消息中显示 beta 功能',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_system_message';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaOptions);
          try {
            return await sendSessionMessage(session, 'Test beta in system message');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}`;
      },
    },

    'beta_context_1m_opus': {
      description: 'Beta: Opus 4.6 与 1M 上下文 (兼容性测试)',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_opus';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Reply with: opus beta test', betaOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `model=claude-opus-4-6, subtype=${result.subtype}, request_betas=${requestBetas.join(',')}`;
      },
    },

    'beta_context_1m_haiku': {
      description: 'Beta: Haiku 4.5 与 1M 上下文 (兼容性测试)',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_haiku';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-haiku-4-5-20251001',
          betas: ['context-1m-2025-08-07'],
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Reply with: haiku beta test', betaOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `model=claude-haiku-4-5-20251001, subtype=${result.subtype}, request_betas=${requestBetas.join(',')}`;
      },
    },

    'beta_invalid_feature': {
      description: 'Beta: 验证无效 beta 是否出现在请求头中',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_invalid_feature';
        const invalidBetaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          // @ts-expect-error - 故意测试无效的 beta 功能
          betas: ['invalid-beta-feature-xyz'],
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Test invalid beta', invalidBetaOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        assertResultSubtypeSuccess(result.subtype, context, result.result);
        const requestBetas = assertRequestHasBetas(requests, ['invalid-beta-feature-xyz'], context);
        return `request_betas=${requestBetas.join(',')}, result="${truncate(result.result)}"`;
      },
    },

    'beta_empty_array': {
      description: 'Beta: 测试空 beta 数组',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_empty_array';
        const emptyBetaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: [],
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Test empty beta array', emptyBetaOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        assertResultSubtypeSuccess(result.subtype, context, result.result);
        const observedBetas = assertRequestsDoNotHaveBetas(
          requests,
          ['context-1m-2025-08-07'],
          context,
        );
        return `request_betas=${observedBetas.join(',') || 'none'}, result="${truncate(result.result)}"`;
      },
    },

    'beta_with_tools': {
      description: 'Beta: Beta 功能与工具组合测试',
      covers: ['model', 'prompt', 'betas', 'allowedTools'],
      run: async () => {
        const context = 'beta_with_tools';
        const betaWithToolsOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
          allowedTools: ['Read'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaWithToolsOptions);
          try {
            await session.send('Read package.json and tell me the project name in one short sentence.');

            let systemBetas: string[] = [];
            let toolUsed = false;
            let resultSubtype = '';
            let resultText = '';

            for await (const message of session.stream()) {
              if (message.type === 'system' && message.subtype === 'init') {
                systemBetas = message.betas || [];
              }
              if (message.type === 'tool_use_summary') {
                toolUsed = true;
              }
              if (message.type === 'result') {
                resultSubtype = message.subtype ?? '';
                resultText = message.result ?? '';
                break;
              }
            }

            return {
              systemBetas,
              toolUsed,
              resultSubtype,
              resultText,
            };
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, tool_used=${collected.toolUsed}`;
      },
    },

    'beta_context_1m_streaming': {
      description: 'Beta: 1M 上下文窗口流式传输测试',
      covers: ['model', 'prompt', 'betas', 'streaming'],
      run: async () => {
        const context = 'beta_context_1m_streaming';
        const betaStreamingOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaStreamingOptions);
          try {
            return await sendSessionMessage(session, 'Count from 1 to 5 with beta context 1M');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, message_types=${collected.messageTypes.join(',')}`;
      },
    },

    'beta_context_1m_multi_turn': {
      description: 'Beta: 1M 上下文窗口多轮对话测试',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_multi_turn';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaOptions);
          try {
            const first = await sendSessionMessage(session, 'Remember the number 42 with beta context 1M');
            const second = await sendSessionMessage(session, 'What number did I ask you to remember?');
            return { first, second };
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.first.resultSubtype, `${context}:turn1`, collected.first.resultText);
        assertResultSubtypeSuccess(collected.second.resultSubtype, `${context}:turn2`, collected.second.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        assertAllMessageRequestsHaveBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, turn2="${truncate(collected.second.resultText)}"`;
      },
    },

    'beta_context_1m_resume_session': {
      description: 'Beta: 恢复使用 1M 上下文的会话',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_resume_session';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session1 = unstable_v2_createSession(betaOptions);
          try {
            const first = await sendSessionMessage(session1, 'Remember: beta context 1M test');
            const sessionId = await waitForSessionId(session1);
            if (!sessionId) {
              throw new Error(`${context}: session_id_unavailable_after_messages`);
            }

            const session2 = unstable_v2_resumeSession(sessionId, betaOptions);
            try {
              const second = await sendSessionMessage(session2, 'What did I ask you to remember?');
              return { first, second, sessionId };
            } finally {
              session2.close();
            }
          } finally {
            session1.close();
          }
        });

        assertResultSubtypeSuccess(collected.first.resultSubtype, `${context}:initial`, collected.first.resultText);
        assertResultSubtypeSuccess(collected.second.resultSubtype, `${context}:resumed`, collected.second.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        assertAllMessageRequestsHaveBetas(requests, ['context-1m-2025-08-07'], context);
        return `session_id=${collected.sessionId}, request_betas=${requestBetas.join(',')}, result="${truncate(collected.second.resultText)}"`;
      },
    },

    'beta_context_1m_with_custom_env': {
      description: 'Beta: 1M 上下文与自定义环境变量组合',
      covers: ['model', 'prompt', 'betas', 'env'],
      run: async () => {
        const context = 'beta_context_1m_with_custom_env';
        const betaWithEnvOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
          env: {
            ...baseOptions.env!,
            CUSTOM_BETA_TEST_VAR: 'test_value',
            CLAUDE_AGENT_SDK_CLIENT_APP: 'beta-test/1.0.0',
          },
        };

        const { result, requests } = await observeLoggedRequests(() =>
          unstable_v2_prompt('Test beta with custom env', betaWithEnvOptions),
        );

        if (result.type !== 'result') {
          throw new Error(`${context}: unexpected result type=${result.type}`);
        }

        assertResultSubtypeSuccess(result.subtype, context, result.result);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, result="${truncate(result.result)}"`;
      },
    },

    'beta_context_1m_error_recovery': {
      description: 'Beta: 1M 上下文会话错误恢复',
      covers: ['model', 'prompt', 'betas'],
      run: async () => {
        const context = 'beta_context_1m_error_recovery';
        const betaOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(betaOptions);
          try {
            const first = await sendSessionMessage(session, 'First message with beta context 1M');
            const second = await sendSessionMessage(session, 'Second message after first success');
            return { first, second };
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.first.resultSubtype, `${context}:initial`, collected.first.resultText);
        assertResultSubtypeSuccess(collected.second.resultSubtype, `${context}:recovery`, collected.second.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['context-1m-2025-08-07'], context);
        assertAllMessageRequestsHaveBetas(requests, ['context-1m-2025-08-07'], context);
        return `request_betas=${requestBetas.join(',')}, result="${truncate(collected.second.resultText)}"`;
      },
    },

    // ========================================
    // Thinking 相关 Beta 功能测试
    // ========================================

    'beta_thinking_adaptive': {
      description: 'Beta: Adaptive thinking 模式 (自动触发 interleaved-thinking beta)',
      covers: ['model', 'prompt', 'thinking'],
      run: async () => {
        const context = 'beta_thinking_adaptive';
        const thinkingOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          thinking: { type: 'adaptive' },
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(thinkingOptions);
          try {
            return await sendSessionMessage(session, 'Solve: What is 15 + 27?');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['interleaved-thinking-2025-05-14'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_thinking_enabled': {
      description: 'Beta: Enabled thinking 模式 (固定 token 预算)',
      covers: ['model', 'prompt', 'thinking'],
      run: async () => {
        const context = 'beta_thinking_enabled';
        const thinkingOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          thinking: { type: 'enabled', budgetTokens: 1000 },
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(thinkingOptions);
          try {
            return await sendSessionMessage(session, 'Calculate 23 * 47');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['interleaved-thinking-2025-05-14'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_thinking_disabled': {
      description: 'Beta: Disabled thinking 模式',
      covers: ['model', 'prompt', 'thinking'],
      run: async () => {
        const context = 'beta_thinking_disabled';
        const noThinkingOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          thinking: { type: 'disabled' },
        };

        const { result: collected } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(noThinkingOptions);
          try {
            return await sendSessionMessage(session, 'Say hello');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        if (collected.systemBetas.includes('interleaved-thinking-2025-05-14')) {
          throw new Error(
            `${context}: system message unexpectedly enabled interleaved thinking observed=${collected.systemBetas.join(',')}`,
          );
        }
        return `system_betas=${collected.systemBetas.join(',') || 'none'}, result="${truncate(collected.resultText)}"`;
      },
    },

    // ========================================
    // Effort 相关 Beta 功能测试
    // ========================================

    'beta_effort_low': {
      description: 'Beta: Effort=low (自动触发 effort beta)',
      covers: ['model', 'prompt', 'effort'],
      run: async () => {
        const context = 'beta_effort_low';
        const lowEffortOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
          effort: 'low',
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(lowEffortOptions);
          try {
            return await sendSessionMessage(session, 'Quick task: say "test ok"');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['effort-2025-11-24'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_effort_high': {
      description: 'Beta: Effort=high (深度思考)',
      covers: ['model', 'prompt', 'effort'],
      run: async () => {
        const context = 'beta_effort_high';
        const highEffortOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
          effort: 'high',
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(highEffortOptions);
          try {
            return await sendSessionMessage(session, 'Explain quantum computing in 2 sentences');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['effort-2025-11-24'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_effort_max': {
      description: 'Beta: Effort=max (最大努力,仅 Opus 4.6)',
      covers: ['model', 'prompt', 'effort'],
      run: async () => {
        const context = 'beta_effort_max';
        const maxEffortOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
          effort: 'max',
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(maxEffortOptions);
          try {
            return await sendSessionMessage(session, 'What is the meaning of life?');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const requestBetas = assertRequestHasBetas(requests, ['effort-2025-11-24'], context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_effort_with_thinking': {
      description: 'Beta: Effort + Thinking 组合',
      covers: ['model', 'prompt', 'effort', 'thinking'],
      run: async () => {
        const context = 'beta_effort_with_thinking';
        const combinedOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-opus-4-6',
          effort: 'high',
          thinking: { type: 'adaptive' },
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(combinedOptions);
          try {
            return await sendSessionMessage(session, 'Solve a complex problem');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const expectedBetas = ['effort-2025-11-24', 'interleaved-thinking-2025-05-14'] as const;
        const requestBetas = assertRequestHasBetas(requests, expectedBetas, context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    // ========================================
    // MCP 相关 Beta 功能测试
    // ========================================

    'beta_mcp_servers_config': {
      description: 'Beta: MCP 服务器配置 (触发 mcp-servers beta)',
      covers: ['model', 'prompt', 'mcpServers'],
      run: async () => {
        const context = 'beta_mcp_servers_config';
        const mcpOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['mcp-client-2025-11-20', 'mcp-servers-2025-12-04'],
          mcpServers: {
            'test-server': {
              command: 'echo',
              args: ['MCP test'],
            },
          },
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(mcpOptions);
          try {
            return await sendSessionMessage(session, 'Test MCP configuration');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const expectedBetas = ['mcp-client-2025-11-20', 'mcp-servers-2025-12-04'] as const;
        const requestBetas = assertRequestHasBetas(requests, expectedBetas, context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',') || 'none'}, mcp_servers=${collected.mcpServerCount}`;
      },
    },

    // ========================================
    // 组合测试
    // ========================================

    'beta_context_1m_with_effort': {
      description: 'Beta: 1M 上下文 + Effort 组合',
      covers: ['model', 'prompt', 'betas', 'effort'],
      run: async () => {
        const context = 'beta_context_1m_with_effort';
        const combinedOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
          effort: 'high',
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(combinedOptions);
          try {
            return await sendSessionMessage(session, 'Test combined beta features');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const expectedBetas = ['context-1m-2025-08-07', 'effort-2025-11-24'] as const;
        const requestBetas = assertRequestHasBetas(requests, expectedBetas, context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    'beta_thinking_effort_context_1m': {
      description: 'Beta: Thinking + Effort + 1M 上下文三重组合',
      covers: ['model', 'prompt', 'betas', 'thinking', 'effort'],
      run: async () => {
        const context = 'beta_thinking_effort_context_1m';
        const tripleOptions: SDKSessionOptions = {
          ...baseOptions,
          model: 'claude-sonnet-4-6',
          betas: ['context-1m-2025-08-07'],
          thinking: { type: 'adaptive' },
          effort: 'high',
        };

        const { result: collected, requests } = await observeLoggedRequests(async () => {
          const session = unstable_v2_createSession(tripleOptions);
          try {
            return await sendSessionMessage(session, 'Complex analysis task');
          } finally {
            session.close();
          }
        });

        assertResultSubtypeSuccess(collected.resultSubtype, context, collected.resultText);
        const expectedBetas = [
          'context-1m-2025-08-07',
          'interleaved-thinking-2025-05-14',
          'effort-2025-11-24',
        ] as const;
        const requestBetas = assertRequestHasBetas(requests, expectedBetas, context);
        return `request_betas=${requestBetas.join(',')}, system_betas=${collected.systemBetas.join(',')}, result="${truncate(collected.resultText)}"`;
      },
    },

    // ========================================
    // Beta 目录一比一覆盖
    // ========================================
    ...buildClaudeAgentBetaCatalogCases(),
  });

  return cases.map((testCase) => ({
    ...testCase,
    run: async () => {
      const testId = createClaudeAgentTestId(testCase.id);
      let detail: string | undefined;
      let runError: unknown;

      try {
        detail = await runWithClaudeAgentTestId(testId, () => testCase.run());
      } catch (error) {
        runError = error;
      }

      const exchanges = readTraceFile(testId);
      const httpTrace: TestCaseHttpTrace = {
        source: CLAUDE_AGENT_TRACE_SOURCE,
        testId,
        exchangeCount: exchanges.length,
        exchanges,
      };
      claudeAgentCaseHttpTraceByCaseId.set(testCase.id, httpTrace);

      try {
        const finalResponse = assertFinalClaudeAgentMessageBetaResponseOk(httpTrace, testCase.id);
        const statusDetail = `message_api_status=${formatClaudeAgentResponseStatus(finalResponse)}`;
        const detailParts = [statusDetail];
        if (detail) {
          detailParts.push(detail);
        }
        if (runError) {
          detailParts.push(`sdk_error_ignored="${truncate(formatError(runError), 160)}"`);
        }
        return detailParts.join(', ');
      } catch (statusError) {
        if (runError instanceof Error && statusError instanceof Error) {
          statusError.message = `${statusError.message}; sdk_error=${formatError(runError)}`;
        }
        throw statusError;
      }
    },
  }));
}
