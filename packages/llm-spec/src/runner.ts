import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import type { ProviderSummary, RunProgressHandler, RunSummary } from './types';
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

interface RunRuntimeOptions {
  onProgress?: RunProgressHandler;
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

export async function runRuntimeConfig(
  config: RuntimeConfig,
  options: RunRuntimeOptions = {},
): Promise<RunSummary> {
  initializeRequestLogFile();
  installGlobalFetchInterceptor();
  printRuntimeConfig(config);

  const startedAt = new Date().toISOString();
  const providers: ProviderSummary[] = [];

  if (config.testTarget) {
    const summaries = await runConfiguredTarget(config, options);
    for (const summary of summaries) {
      providers.push(summary);
      printProviderSummary(summary);
    }
  } else {
    for (const provider of config.targetProviders) {
      if (provider === 'openai') {
        const summaries = await runOpenAICases(config.openai, config.failFast, config.concurrency, options.onProgress);
        for (const summary of summaries) {
          providers.push(summary);
          printProviderSummary(summary);
        }
        continue;
      }

      if (provider === 'anthropic') {
        const summary = await runAnthropicCases(config.anthropic, config.failFast, config.concurrency, options.onProgress);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'gemini') {
        const summary = await runGeminiCases(config.gemini, config.failFast, config.concurrency, options.onProgress);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'xai') {
        const summary = await runXAICases(
          config.xai,
          config.failFast,
          config.concurrency,
          options.onProgress,
        );
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'claude-agent') {
        const summary = await runClaudeAgentCases(
          config.claudeAgent,
          config.failFast,
          config.concurrency,
          options.onProgress,
        );
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'codex') {
        const summary = await runCodexCases(config.codex, config.failFast, config.concurrency, options.onProgress);
        providers.push(summary);
        printProviderSummary(summary);
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

  printRunSummary(summary);

  if (config.reportFile) {
    const jsonPath = resolvePath(process.cwd(), config.reportFile);
    writeReportFile(jsonPath, `${JSON.stringify(summary, null, 2)}\n`);
    console.log(`report written: ${jsonPath}`);
  }

  return summary;
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
