/**
 * LLM Spec - 三类 SDK 参数/特性兼容性测试器
 *
 * 入口文件仅负责编排执行，provider 逻辑位于：
 * - src/api-sdk-tester/openai-provider.ts
 * - src/api-sdk-tester/anthropic-provider.ts
 * - src/api-sdk-tester/gemini-provider.ts
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import type { ProviderSummary, RunSummary } from './types';
import { clearUsageCaptures, flushUsageCaptures } from './audit/usageCapture';
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
} from './api-sdk-tester';

function writeReportFile(path: string, content: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, 'utf8');
}

async function runConfiguredTarget(config: ReturnType<typeof resolveRuntimeConfig>): Promise<ProviderSummary[]> {
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
        },
        config.failFast,
        config.concurrency,
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
        cachedContent: undefined,
        audioModel: undefined,
        imageModel: undefined,
        enableVertexOnlyCases: false,
        modelArmorPromptTemplate: undefined,
        modelArmorResponseTemplate: undefined,
      },
      config.failFast,
      config.concurrency,
    ),
  ];
}

async function run(): Promise<RunSummary> {
  

  // 初始化请求日志文件
  initializeRequestLogFile();

  // 安装全局fetch拦截器,用于记录所有HTTP请求和响应
  installGlobalFetchInterceptor();

  //audit usage 收集
  clearUsageCaptures();

  const config = resolveRuntimeConfig();
  printRuntimeConfig(config);

  const startedAt = new Date().toISOString();
  const providers: ProviderSummary[] = [];

  if (config.testTarget) {
    const summaries = await runConfiguredTarget(config);
    for (const summary of summaries) {
      providers.push(summary);
      printProviderSummary(summary);
    }
  } else {
    for (const provider of config.targetProviders) {
      if (provider === 'openai') {
        const summaries = await runOpenAICases(config.openai, config.failFast, config.concurrency);
        for (const summary of summaries) {
          providers.push(summary);
          printProviderSummary(summary);
        }
        continue;
      }

      if (provider === 'anthropic') {
        const summary = await runAnthropicCases(config.anthropic, config.failFast, config.concurrency);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'gemini') {
        const summary = await runGeminiCases(config.gemini, config.failFast, config.concurrency);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'claude-agent') {
        const summary = await runClaudeAgentCases(config.claudeAgent, config.failFast, config.concurrency);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
      }

      if (provider === 'codex') {
        const summary = await runCodexCases(config.codex, config.failFast, config.concurrency);
        providers.push(summary);
        printProviderSummary(summary);
        continue;
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
  //将收集的usage写入文件
  const usageArtifactPath = flushUsageCaptures();
  if (usageArtifactPath) {
    console.log(`usage artifact written: ${usageArtifactPath}`);
  }

  if (totalFailed > 0) {
    process.exitCode = 1;
  }

  return summary;
}

run().catch((error: unknown) => {
  console.error(`Fatal error: ${formatError(error)}`);
  process.exitCode = 1;
});
