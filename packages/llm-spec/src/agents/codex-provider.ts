import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';

import type { ProviderSummary, RunProgressHandler } from '../types';
import { buildCodexCases, CODEX_PARAMS } from '../api-sdk-tester/cases/codex';
import {
  getCodexCaseHttpTrace,
  resetCodexCaseHttpTraces,
} from '../api-sdk-tester/codex-reverse-proxy';
import type { CodexProviderConfig } from '../api-sdk-tester/environment';
import {
  setCurrentProvider,
} from '../api-sdk-tester/environment';
import { createSetupSkippedSummary, executeProviderCases } from '../api-sdk-tester/cases/runtime';

const requireFromHere = createRequire(import.meta.url);
const MACOS_CODEX_APP_EXECUTABLE = '/Applications/Codex.app/Contents/Resources/codex';
const CODEX_CONFIG_OVERRIDES = {
  features: {
    remote_control: false,
  },
} as const;

const CODEX_PLATFORM_PACKAGES: Partial<
  Record<NodeJS.Platform, Partial<Record<NodeJS.Architecture, { packageName: string; targetTriple: string }>>>
> = {
  darwin: {
    arm64: {
      packageName: '@openai/codex-darwin-arm64',
      targetTriple: 'aarch64-apple-darwin',
    },
    x64: {
      packageName: '@openai/codex-darwin-x64',
      targetTriple: 'x86_64-apple-darwin',
    },
  },
  linux: {
    arm64: {
      packageName: '@openai/codex-linux-arm64',
      targetTriple: 'aarch64-unknown-linux-musl',
    },
    x64: {
      packageName: '@openai/codex-linux-x64',
      targetTriple: 'x86_64-unknown-linux-musl',
    },
  },
  win32: {
    arm64: {
      packageName: '@openai/codex-win32-arm64',
      targetTriple: 'aarch64-pc-windows-msvc',
    },
    x64: {
      packageName: '@openai/codex-win32-x64',
      targetTriple: 'x86_64-pc-windows-msvc',
    },
  },
};

function resolveCodexExecutablePath(): string | undefined {
  const explicitPath = process.env.CODEX_PATH || process.env.CODEX_EXECUTABLE_PATH;
  if (explicitPath) {
    return explicitPath;
  }

  if (process.platform === 'darwin' && existsSync(MACOS_CODEX_APP_EXECUTABLE)) {
    return MACOS_CODEX_APP_EXECUTABLE;
  }

  const platformPackage = CODEX_PLATFORM_PACKAGES[process.platform]?.[process.arch];
  if (!platformPackage) {
    return undefined;
  }

  try {
    const packageJsonPath = requireFromHere.resolve(`${platformPackage.packageName}/package.json`);
    const binaryName = process.platform === 'win32' ? 'codex.exe' : 'codex';
    const executablePath = join(
      dirname(packageJsonPath),
      'vendor',
      platformPackage.targetTriple,
      'codex',
      binaryName,
    );

    return existsSync(executablePath) ? executablePath : undefined;
  } catch {
    return undefined;
  }
}

export async function runCodexCases(
  config: CodexProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  setCurrentProvider('codex');
  resetCodexCaseHttpTraces();

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'codex',
      config.model ?? 'default',
      config.apiBaseUrl,
      CODEX_PARAMS,
      'missing API key (set CODEX_API_KEY, OPENAI_API_KEY, or API_KEY)',
      onProgress,
    );
  }

  const codexPathOverride = resolveCodexExecutablePath();
  const cases = buildCodexCases({
    config,
    codexPathOverride,
    codexConfig: CODEX_CONFIG_OVERRIDES,
  });
  const effectiveConcurrency = concurrency > 1 ? 1 : concurrency;

  if (concurrency > 1) {
    console.log(
      `[codex] requested concurrency=${concurrency}; running Codex CLI cases serially to avoid competing agent processes.`,
    );
  }

  const summary = await executeProviderCases(
    'codex',
    config.model ?? 'default',
    config.apiBaseUrl,
    CODEX_PARAMS,
    cases,
    failFast,
    effectiveConcurrency,
    onProgress,
  );

  return {
    ...summary,
    caseResults: summary.caseResults.map((result) => ({
      ...result,
      httpTrace: getCodexCaseHttpTrace(result.id) ?? result.httpTrace,
    })),
  };
}
