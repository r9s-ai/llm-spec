import Anthropic from '@anthropic-ai/sdk';

import type { ProviderSummary } from '../types';
import type { AnthropicProviderConfig } from './environment';
import { ANTHROPIC_MESSAGE_PARAMS, buildAnthropicCases } from './cases/anthropic';
import {
  createLoggingFetch,
  setCurrentProvider,
} from './environment';
import { createSetupSkippedSummary, executeProviderCases } from './cases/runtime';

export async function runAnthropicCases(
  config: AnthropicProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  setCurrentProvider('anthropic');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'anthropic',
      config.model,
      config.apiBaseUrl,
      ANTHROPIC_MESSAGE_PARAMS,
      'missing API key (set ANTHROPIC_API_KEY or API_KEY)',
    );
  }

  const client = new Anthropic({
    apiKey: config.apiKey,
    baseURL: config.apiBaseUrl,
    timeout: config.timeoutMs,
    maxRetries: 0,
    fetch: createLoggingFetch('anthropic'),
  });

  const cases = buildAnthropicCases({ client, config });

  return executeProviderCases(
    'anthropic',
    config.model,
    config.apiBaseUrl,
    ANTHROPIC_MESSAGE_PARAMS,
    cases,
    failFast,
    concurrency,
  );
}
