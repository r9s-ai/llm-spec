import { Codex } from '@openai/codex-sdk';

import type { ProviderSummary } from '../types';
import { buildCodexCases, CODEX_PARAMS } from './cases/openai';
import type { CodexProviderConfig } from './runtime-config';
import {
  createSetupSkippedSummary,
  executeProviderCases,
  setCurrentProvider,
} from './shared';

export async function runCodexCases(
  config: CodexProviderConfig,
  failFast: boolean,
): Promise<ProviderSummary> {
  setCurrentProvider('codex');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'codex',
      'agent',
      config.apiBaseUrl,
      CODEX_PARAMS,
      'missing API key (set CODEX_API_KEY, OPENAI_API_KEY, or API_KEY)',
    );
  }

  const client = new Codex({
    apiKey: config.apiKey,
    baseUrl: config.apiBaseUrl,
  });

  const cases = buildCodexCases({ client, config });

  return executeProviderCases(
    'codex',
    'agent',
    config.apiBaseUrl,
    CODEX_PARAMS,
    cases,
    failFast,
  );
}
