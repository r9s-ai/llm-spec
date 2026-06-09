import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import type { ProviderSummary, RunProgressHandler, RunSummary, TestLifecyclePlugin } from './types';
import {
  formatError,
  initializeRequestLogFile,
  installGlobalFetchInterceptor,
  printProviderSummary,
  printRunSummary,
  printRuntimeConfig,
  resolveRuntimeConfig,
  runAnthropicCases,
  runClaudeAgentCases,
  runCodexCases,
  runGeminiCases,
  runOpenAICases,
  runOpenAIChatCases,
  runOpenAIResponsesCases,
  runXAICases,
} from './api-sdk-tester';
import type { RuntimeConfig } from './api-sdk-tester';
import {
  createTestPluginManager,
  runWithTestPluginManager,
  type TestPluginManager,
} from './api-sdk-tester/plugins';
import { createR9SBillingAuditPlugin } from './api-sdk-tester/r9s-billing-audit-plugin';

interface RunRuntimeOptions {
  onProgress?: RunProgressHandler;
  pluginManager?: TestPluginManager;
  runAfterRunPlugins?: boolean;
}

function writeReportFile(path: string, content: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, 'utf8');
}

async function runConfiguredTarget(
  config: RuntimeConfig,
  options: RunRuntimeOptions = {},
): Promise<ProviderSummary[]> {
  const target = config.testTarget;
  if (!target) {
    return [];
  }

  if (target.apiType === 'openai.chat') {
    return [
      await runOpenAIChatCases(
        {
          provider: 'openai',
          apiKey: target.apiKey,
          apiBaseUrl: target.apiBaseUrl,
          model: target.model,
          timeoutMs: target.timeoutMs,
          customHeaders: target.customHeaders,
        },
        config.failFast,
        config.concurrency,
        options.onProgress,
      ),
    ];
  }

  if (target.apiType === 'openai.responses') {
    return [
      await runOpenAIResponsesCases(
        {
          provider: 'openai',
          apiKey: target.apiKey,
          apiBaseUrl: target.apiBaseUrl,
          model: target.model,
          timeoutMs: target.timeoutMs,
          customHeaders: target.customHeaders,
        },
        config.failFast,
        config.concurrency,
        options.onProgress,
      ),
    ];
  }

  if (target.apiType === 'anthropic.messages') {
    return [
      await runAnthropicCases(
        {
          provider: 'anthropic',
          apiKey: target.apiKey,
          apiBaseUrl: target.apiBaseUrl,
          model: target.model,
          timeoutMs: target.timeoutMs,
          customHeaders: target.customHeaders,
        },
        config.failFast,
        config.concurrency,
        options.onProgress,
      ),
    ];
  }

  return [
    await runGeminiCases(
      {
        provider: 'gemini',
        apiKey: target.apiKey,
        apiBaseUrl: target.apiBaseUrl,
        model: target.model,
        timeoutMs: target.timeoutMs,
        apiVersion: target.apiVersion,
        customHeaders: target.customHeaders,
        cachedContent: undefined,
        audioModel: undefined,
        imageModel: undefined,
        enableVertexOnlyCases: false,
        modelArmorPromptTemplate: undefined,
        modelArmorResponseTemplate: undefined,
      },
      config.failFast,
      config.concurrency,
      options.onProgress,
    ),
  ];
}

async function runAfterCasePlugins(
  pluginManager: TestPluginManager,
  summary: ProviderSummary,
): Promise<void> {
  if (!pluginManager.hasPlugins) {
    return;
  }

  for (const result of summary.caseResults) {
    const exchanges = result.httpTrace?.exchanges ?? [];
    const primaryExchange = exchanges[0];
    await pluginManager.runAfterCase({
      provider: summary.provider,
      model: summary.model,
      apiBaseUrl: summary.apiBaseUrl,
      id: result.id,
      name: result.id,
      description: result.description,
      result,
      request: primaryExchange?.request,
      response: primaryExchange?.response,
      exchanges,
    });
  }
}

async function appendProviderSummary(
  providers: ProviderSummary[],
  summary: ProviderSummary,
  pluginManager: TestPluginManager,
): Promise<void> {
  providers.push(summary);
  await runAfterCasePlugins(pluginManager, summary);
  printProviderSummary(summary);
}

function inferBillingAuditApiKey(config: RuntimeConfig): string | undefined {
  if (config.r9sBillingAudit?.apiKey) {
    return config.r9sBillingAudit.apiKey;
  }
  if (config.testTarget?.apiKey) {
    return config.testTarget.apiKey;
  }
  if (config.targetProviders.length !== 1) {
    return undefined;
  }

  const [provider] = config.targetProviders;
  if (provider === 'openai') {
    return config.openai.apiKey;
  }
  if (provider === 'anthropic') {
    return config.anthropic.apiKey;
  }
  if (provider === 'gemini') {
    return config.gemini.apiKey;
  }
  if (provider === 'xai') {
    return config.xai.apiKey;
  }
  if (provider === 'claude-agent') {
    return config.claudeAgent.apiKey;
  }
  if (provider === 'codex') {
    return config.codex.apiKey;
  }
  return undefined;
}

function createRuntimePlugins(config: RuntimeConfig): TestLifecyclePlugin[] {
  const billingAuditPlugin = createR9SBillingAuditPlugin(
    config.r9sBillingAudit
      ? {
          ...config.r9sBillingAudit,
          apiKey: config.r9sBillingAudit.apiKey ?? inferBillingAuditApiKey(config),
        }
      : undefined,
  );
  return billingAuditPlugin ? [billingAuditPlugin] : [];
}

export async function runRuntimeConfig(
  config: RuntimeConfig,
  options: RunRuntimeOptions = {},
): Promise<RunSummary> {
  const pluginManager = options.pluginManager ?? await createTestPluginManager(config.pluginPaths, createRuntimePlugins(config));

  return runWithTestPluginManager(pluginManager, async () => {
    initializeRequestLogFile();
    installGlobalFetchInterceptor();
    printRuntimeConfig(config);

    const startedAt = new Date().toISOString();
    const providers: ProviderSummary[] = [];

    if (config.testTarget) {
      const summaries = await runConfiguredTarget(config, options);
      for (const summary of summaries) {
        await appendProviderSummary(providers, summary, pluginManager);
      }
    } else {
      for (const provider of config.targetProviders) {
        if (provider === 'openai') {
          const summaries = await runOpenAICases(config.openai, config.failFast, config.concurrency, options.onProgress);
          for (const summary of summaries) {
            await appendProviderSummary(providers, summary, pluginManager);
          }
          continue;
        }

        if (provider === 'anthropic') {
          const summary = await runAnthropicCases(config.anthropic, config.failFast, config.concurrency, options.onProgress);
          await appendProviderSummary(providers, summary, pluginManager);
          continue;
        }

        if (provider === 'gemini') {
          const summary = await runGeminiCases(config.gemini, config.failFast, config.concurrency, options.onProgress);
          await appendProviderSummary(providers, summary, pluginManager);
          continue;
        }

        if (provider === 'xai') {
          const summary = await runXAICases(
            config.xai,
            config.failFast,
            config.concurrency,
            options.onProgress,
          );
          await appendProviderSummary(providers, summary, pluginManager);
          continue;
        }

        if (provider === 'claude-agent') {
          const summary = await runClaudeAgentCases(
            config.claudeAgent,
            config.failFast,
            config.concurrency,
            options.onProgress,
          );
          await appendProviderSummary(providers, summary, pluginManager);
          continue;
        }

        if (provider === 'codex') {
          const summary = await runCodexCases(config.codex, config.failFast, config.concurrency, options.onProgress);
          await appendProviderSummary(providers, summary, pluginManager);
        }
      }
    }

    const totalPassed = providers.reduce((acc, item) => acc + item.passed, 0);
    const totalFailed = providers.reduce((acc, item) => acc + item.failed, 0);
    const totalSkipped = providers.reduce((acc, item) => acc + item.skipped, 0);

    const summary: RunSummary = {
      startedAt,
      finishedAt: new Date().toISOString(),
      providers,
      totalPassed,
      totalFailed,
      totalSkipped,
    };

    if (options.runAfterRunPlugins !== false) {
      await pluginManager.runAfterRun({ summary });
    }

    printRunSummary(summary);

    if (config.reportFile) {
      const jsonPath = resolvePath(process.cwd(), config.reportFile);
      writeReportFile(jsonPath, `${JSON.stringify(summary, null, 2)}\n`);
      console.log(`report written: ${jsonPath}`);
    }

    return summary;
  });
}

export async function runCli(): Promise<void> {
  try {
    const summary = await runRuntimeConfig(resolveRuntimeConfig());
    if (summary.totalFailed > 0) {
      process.exitCode = 1;
    }
  } catch (error: unknown) {
    console.error(`Fatal error: ${formatError(error)}`);
    process.exitCode = 1;
  }
}
