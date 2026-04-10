import {
  Codex,
  type Input as CodexInput,
  type Thread,
  type TurnOptions as CodexTurnOptions,
} from '@openai/codex-sdk';

import type { CodexProviderConfig } from '../../environment';
import { defineCases } from '../define-cases';
import { truncate } from '../runtime';
import type { TestCase } from '../types';

export const CODEX_PARAMS = [
  'prompt',
  'outputSchema',
  'workingDirectory',
  'skipGitRepoCheck',
  'config',
  'env',
  'streaming',
] as const;

export interface CodexCaseContext {
  client: Codex;
  config: CodexProviderConfig;
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
  const cases = defineCases(
    {
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
          }
          return 'usage=null';
        },
      },
    },
    {
      protocol: 'codex.thread',
      modelScope: 'default',
    },
  );

  return cases;
}
