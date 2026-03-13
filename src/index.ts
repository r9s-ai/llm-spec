/**
 * LLM Spec - 三类 SDK 参数/特性兼容性测试器
 *
 * 入口文件仅负责编排执行，provider 逻辑位于：
 * - src/api-sdk-tester/openai-provider.ts
 * - src/api-sdk-tester/anthropic-provider.ts
 * - src/api-sdk-tester/gemini-provider.ts
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, extname, resolve as resolvePath } from 'node:path';

import type { ProviderSummary, RunSummary } from './types';
import {
  formatError,
  installGlobalFetchInterceptor,
  printProviderSummary,
  printRunSummary,
  printRuntimeConfig,
  renderHtmlReport,
  renderTextReport,
  resolveRuntimeConfig,
  runAnthropicCases,
  runGeminiCases,
  runOpenAICases,
} from './api-sdk-tester';

interface ReportPaths {
  jsonFile: string;
  htmlFile: string;
  textFile: string;
}

function resolveReportPaths(reportFile: string): ReportPaths {
  const extension = extname(reportFile);
  if (!extension) {
    return {
      jsonFile: reportFile,
      htmlFile: `${reportFile}.html`,
      textFile: `${reportFile}.txt`,
    };
  }

  const base = reportFile.slice(0, -extension.length);
  return {
    jsonFile: reportFile,
    htmlFile: `${base}.html`,
    textFile: `${base}.txt`,
  };
}

function writeReportFile(path: string, content: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, 'utf8');
}

async function run(): Promise<RunSummary> {
  // 安装全局fetch拦截器,用于记录所有HTTP请求和响应
  installGlobalFetchInterceptor();

  const config = resolveRuntimeConfig();
  printRuntimeConfig(config);

  const startedAt = new Date().toISOString();
  const providers: ProviderSummary[] = [];

  for (const provider of config.targetProviders) {
    if (provider === 'openai') {
      const summary = await runOpenAICases(config.openai, config.failFast);
      providers.push(summary);
      printProviderSummary(summary);
      continue;
    }

    if (provider === 'anthropic') {
      const summary = await runAnthropicCases(config.anthropic, config.failFast);
      providers.push(summary);
      printProviderSummary(summary);
      continue;
    }

    if (provider === 'gemini') {
      const summary = await runGeminiCases(config.gemini, config.failFast);
      providers.push(summary);
      printProviderSummary(summary);
      continue;
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
    const paths = resolveReportPaths(config.reportFile);
    const jsonPath = resolvePath(process.cwd(), paths.jsonFile);
    const htmlPath = resolvePath(process.cwd(), paths.htmlFile);
    const textPath = resolvePath(process.cwd(), paths.textFile);

    writeReportFile(jsonPath, `${JSON.stringify(summary, null, 2)}\n`);
    writeReportFile(htmlPath, renderHtmlReport(summary));
    writeReportFile(textPath, renderTextReport(summary));

    console.log(`report written (json): ${jsonPath}`);
    console.log(`report written (html): ${htmlPath}`);
    console.log(`report written (text): ${textPath}`);
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
