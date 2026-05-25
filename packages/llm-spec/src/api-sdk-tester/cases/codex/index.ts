import {
  Codex,
  type CodexOptions,
  type Input as CodexInput,
  type Thread,
  type ThreadOptions as CodexThreadOptions,
  type TurnOptions as CodexTurnOptions,
} from '@openai/codex-sdk';

import type { CodexProviderConfig } from '../../environment';
import { getActiveTestContext } from '../../environment';
import {
  setCodexCaseHttpTrace,
  startCodexReverseProxy,
} from '../../codex-reverse-proxy';
import { defineCases } from '../define-cases';
import { truncate } from '../runtime';
import type { TestCase } from '../types';

export const CODEX_PARAMS = [
  'model',
  'prompt',
  'outputSchema',
  'workingDirectory',
  'skipGitRepoCheck',
  'config',
  'env',
  'streaming',
] as const;

export interface CodexCaseContext {
  config: CodexProviderConfig;
  codexPathOverride?: string;
  codexConfig?: CodexOptions['config'];
}

interface TracedCodexCaseContext {
  client: Codex;
  createClient(options?: Pick<CodexOptions, 'config' | 'env'>): Codex;
}

const CODEX_HTTP_ONLY_PROVIDER_ID = 'llm_spec_openai_proxy';
const CODEX_HTTP_ONLY_PROVIDER_ENV_KEY = 'CODEX_API_KEY';
type CodexConfigObject = NonNullable<CodexOptions['config']>;

function isAbortLikeError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return (
    error.name === 'AbortError' ||
    /\babort(?:ed|ing)?\b/i.test(error.message) ||
    /^Codex Exec exited with signal SIG(?:TERM|KILL):/i.test(error.message)
  );
}

function codexThreadOptions(config: CodexProviderConfig): CodexThreadOptions {
  return {
    model: config.model,
    workingDirectory: config.workingDirectory,
    skipGitRepoCheck: config.skipGitRepoCheck,
  };
}

function startCodexThread(client: Codex, config: CodexProviderConfig): Thread {
  return client.startThread(codexThreadOptions(config));
}

function isCodexConfigObject(value: unknown): value is CodexConfigObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function buildCodexClientConfig(
  proxyBaseUrl: string,
  baseConfig?: CodexOptions['config'],
): CodexConfigObject {
  const config = isCodexConfigObject(baseConfig) ? baseConfig : {};
  const modelProviders = isCodexConfigObject(config.model_providers) ? config.model_providers : {};
  const existingProxyProvider = isCodexConfigObject(modelProviders[CODEX_HTTP_ONLY_PROVIDER_ID])
    ? modelProviders[CODEX_HTTP_ONLY_PROVIDER_ID]
    : {};
  const proxyResponsesBaseUrl = new URL('/v1', proxyBaseUrl).toString();

  return {
    ...config,
    model_provider: CODEX_HTTP_ONLY_PROVIDER_ID,
    model_providers: {
      ...modelProviders,
      // Official Codex docs expose supports_websockets on custom providers, not the built-in OpenAI provider.
      [CODEX_HTTP_ONLY_PROVIDER_ID]: {
        ...existingProxyProvider,
        name: CODEX_HTTP_ONLY_PROVIDER_ID,
        base_url: proxyResponsesBaseUrl,
        env_key: CODEX_HTTP_ONLY_PROVIDER_ENV_KEY,
        wire_api: 'responses',
        supports_websockets: false,
      },
    },
  };
}

function createCodexClient(options: {
  config: CodexProviderConfig;
  proxyBaseUrl: string;
  codexPathOverride?: string;
  codexConfig?: CodexOptions['config'];
  clientOverrides?: Pick<CodexOptions, 'config' | 'env'>;
}): Codex {
  const { config, proxyBaseUrl, codexPathOverride, codexConfig, clientOverrides } = options;
  return new Codex({
    apiKey: config.apiKey,
    codexPathOverride,
    config: buildCodexClientConfig(proxyBaseUrl, clientOverrides?.config ?? codexConfig),
    env: clientOverrides?.env,
  });
}

async function withCodexCaseTrace<T>(
  caseId: string,
  { config, codexPathOverride, codexConfig }: CodexCaseContext,
  run: (context: TracedCodexCaseContext) => Promise<T>,
): Promise<T> {
  const activeTestContext = getActiveTestContext();
  const testId = activeTestContext?.testId ?? `codex-${caseId}-${Date.now()}`;
  const proxy = await startCodexReverseProxy(testId, config.apiBaseUrl);

  const createClient = (clientOverrides?: Pick<CodexOptions, 'config' | 'env'>): Codex =>
    createCodexClient({
      config,
      proxyBaseUrl: proxy.baseUrl,
      codexPathOverride,
      codexConfig,
      clientOverrides,
    });

  try {
    return await run({
      client: createClient(),
      createClient,
    });
  } finally {
    setCodexCaseHttpTrace(caseId, await proxy.close());
  }
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

export function buildCodexCases({
  config,
  codexPathOverride,
  codexConfig,
}: CodexCaseContext): TestCase[] {
  const runTracedCase = <T>(
    caseId: string,
    run: (context: TracedCodexCaseContext) => Promise<T>,
  ): Promise<T> =>
    withCodexCaseTrace(caseId, { config, codexPathOverride, codexConfig }, run);

  const cases = defineCases(
    {
      'basic_thread': {
        description: '创建并运行基础thread',
        covers: ['model', 'prompt', 'workingDirectory'],
        run: async () => runTracedCase('basic_thread', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const turn = await runCodexTurn(thread, 'Reply with exactly: ok', config);

          return `finalResponse="${truncate(turn.finalResponse)}", items=${turn.items.length}`;
        }),
      },
      'basic_thread_streaming': {
        description: '创建并运行基础thread (streaming)',
        covers: ['model', 'prompt', 'workingDirectory', 'streaming'],
        run: async () => runTracedCase('basic_thread_streaming', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const { eventCount, text } = await collectCodexStream(
            thread,
            'Reply with exactly: ok',
            config,
          );

          return `events=${eventCount}, text="${truncate(text)}"`;
        }),
      },
      'structured_output': {
        description: '使用structured output输出JSON',
        covers: ['model', 'prompt', 'outputSchema'],
        run: async () => runTracedCase('structured_output', async ({ client }) => {
          const thread = startCodexThread(client, config);

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
        }),
      },
      'structured_output_streaming': {
        description: '使用structured output输出JSON (streaming)',
        covers: ['model', 'prompt', 'outputSchema', 'streaming'],
        run: async () => runTracedCase('structured_output_streaming', async ({ client }) => {
          const thread = startCodexThread(client, config);

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
        }),
      },
      'multi_turn_conversation': {
        description: '多轮对话',
        covers: ['model', 'prompt'],
        run: async () => runTracedCase('multi_turn_conversation', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const turn1 = await runCodexTurn(thread, 'Remember the number 42', config);
          const turn2 = await runCodexTurn(
            thread,
            'What number did I ask you to remember?',
            config,
          );

          return `turn1="${truncate(turn1.finalResponse)}", turn2="${truncate(turn2.finalResponse)}"`;
        }),
      },
      'image_input': {
        description: '图片输入测试',
        covers: ['model', 'prompt'],
        precondition: () =>
          config.testImagePath ? undefined : 'set CODEX_TEST_IMAGE_PATH to enable image test',
        run: async () => runTracedCase('image_input', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const turn = await runCodexTurn(
            thread,
            [
              { type: 'text', text: 'What is in this image? Reply briefly.' },
              { type: 'local_image', path: config.testImagePath! },
            ],
            config,
          );

          return `finalResponse="${truncate(turn.finalResponse)}"`;
        }),
      },
      'resume_thread': {
        description: '恢复已存在的thread',
        covers: ['model', 'prompt'],
        run: async () => runTracedCase('resume_thread', async ({ client }) => {
          const thread1 = startCodexThread(client, config);

          await runCodexTurn(thread1, 'Remember the word "test"', config);
          const threadId = thread1.id;

          if (!threadId) {
            return 'error: thread id is null';
          }

          const thread2 = client.resumeThread(threadId, codexThreadOptions(config));
          const turn = await runCodexTurn(thread2, 'What word did I ask you to remember?', config);

          return `threadId=${threadId}, finalResponse="${truncate(turn.finalResponse)}"`;
        }),
      },
      'config_override': {
        description: '使用config覆盖',
        covers: ['model', 'config'],
        run: async () => runTracedCase('config_override', async ({ createClient }) => {
          const customClient = createClient({
            config: {
              ...(codexConfig ?? {}),
              show_raw_agent_reasoning: true,
            },
          });

          const thread = startCodexThread(customClient, config);

          const turn = await runCodexTurn(thread, 'Reply with: config test ok', config);

          return `finalResponse="${truncate(turn.finalResponse)}"`;
        }),
      },
      'env_control': {
        description: '控制环境变量',
        covers: ['model', 'env'],
        run: async () => runTracedCase('env_control', async ({ createClient }) => {
          const customClient = createClient({
            env: {
              PATH: process.env.PATH || '',
              HOME: process.env.HOME || '',
              TMPDIR: process.env.TMPDIR || '',
            },
          });

          const thread = startCodexThread(customClient, config);

          const turn = await runCodexTurn(thread, 'Reply with: env test ok', config);

          return `finalResponse="${truncate(turn.finalResponse)}"`;
        }),
      },
      'abort_signal': {
        description: '使用AbortSignal取消操作',
        covers: ['model', 'prompt'],
        run: async () => runTracedCase('abort_signal', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const controller = new AbortController();
          controller.abort();

          try {
            await thread.run('This should be aborted', { signal: controller.signal });
            return 'error: should have been aborted';
          } catch (error) {
            if (!isAbortLikeError(error)) {
              throw error;
            }
            const errorMessage = error instanceof Error ? error.message : String(error);
            return `aborted successfully: ${truncate(errorMessage)}`;
          }
        }),
      },
      'thread_events': {
        description: '监听thread事件',
        covers: ['model', 'prompt', 'streaming'],
        run: async () => runTracedCase('thread_events', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const { eventTypes } = await collectCodexStream(thread, 'Count from 1 to 3', config);

          return `eventTypes=${eventTypes.join(',')}`;
        }),
      },
      'usage_tracking': {
        description: '追踪token使用情况',
        covers: ['model', 'prompt'],
        run: async () => runTracedCase('usage_tracking', async ({ client }) => {
          const thread = startCodexThread(client, config);

          const turn = await runCodexTurn(thread, 'Reply with: usage test', config);

          if (turn.usage) {
            return `input_tokens=${turn.usage.input_tokens}, output_tokens=${turn.usage.output_tokens}`;
          }
          return 'usage=null';
        }),
      },
    },
    {
      protocol: 'codex.thread',
      modelScope: 'default',
    },
  );

  return cases;
}
