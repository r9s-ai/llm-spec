import Anthropic from '@anthropic-ai/sdk';

import type { ProviderSummary, RunProgressHandler } from '../types';
import type { AnthropicProviderConfig } from './environment';
import { ANTHROPIC_MESSAGE_PARAMS, buildAnthropicCases } from './cases/anthropic';
import {
  createLoggingFetch,
  setCurrentProvider,
} from './environment';
import { createSetupSkippedSummary, executeProviderCases } from './cases/runtime';
import { normalizeVersionedApiBaseUrl, removeTrailingApiVersion } from './base-url';

function normalizeAnthropicReportConfig(config: AnthropicProviderConfig): AnthropicProviderConfig {
  return {
    ...config,
    apiBaseUrl: normalizeVersionedApiBaseUrl(config.apiBaseUrl),
  };
}

function normalizeAnthropicExecutionConfig(config: AnthropicProviderConfig): AnthropicProviderConfig {
  return {
    ...config,
    apiBaseUrl: removeTrailingApiVersion(normalizeVersionedApiBaseUrl(config.apiBaseUrl)),
  };
}

export async function runAnthropicCases(
  config: AnthropicProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  const reportConfig = normalizeAnthropicReportConfig(config);
  const executionConfig = normalizeAnthropicExecutionConfig(config);
  setCurrentProvider('anthropic');

  if (!reportConfig.apiKey) {
    return createSetupSkippedSummary(
      'anthropic',
      reportConfig.model,
      reportConfig.apiBaseUrl,
      ANTHROPIC_MESSAGE_PARAMS,
      'missing API key (set ANTHROPIC_API_KEY or API_KEY)',
      onProgress,
    );
  }

  const client = new Anthropic({
    apiKey: executionConfig.apiKey,
    baseURL: executionConfig.apiBaseUrl,
    timeout: executionConfig.timeoutMs,
    maxRetries: 0,
    fetch: createLoggingFetch('anthropic'),
    ...(executionConfig.customHeaders ? { defaultHeaders: executionConfig.customHeaders } : {}),
  });

  const cases = buildAnthropicCases({ client, config: executionConfig });

  return executeProviderCases(
    'anthropic',
    reportConfig.model,
    reportConfig.apiBaseUrl,
    ANTHROPIC_MESSAGE_PARAMS,
    cases,
    failFast,
    concurrency,
    onProgress,
  );
}
