import OpenAI from 'openai';

import type { ProviderSummary } from '../types';
import { buildOpenAICases, OPENAI_PARAMS } from './cases/openai';
import type { OpenAIProviderConfig } from './runtime-config';
import {
  createLoggingFetch,
  createSetupSkippedSummary,
  executeProviderCases,
  setCurrentProvider,
} from './shared';

export async function runOpenAICases(
  config: OpenAIProviderConfig,
  failFast: boolean,
): Promise<ProviderSummary> {
  setCurrentProvider('openai');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'openai',
      config.model,
      config.apiBaseUrl,
      OPENAI_PARAMS,
      'missing API key (set OPENAI_API_KEY or API_KEY)',
    );
  }

  const client = new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.apiBaseUrl,
    timeout: config.timeoutMs,
    maxRetries: 0,
    fetch: createLoggingFetch('openai'),
  });

  const cases = buildOpenAICases({ client, config });

  return executeProviderCases(
    'openai',
    config.model,
    config.apiBaseUrl,
    OPENAI_PARAMS,
    cases,
    failFast,
  );
}
