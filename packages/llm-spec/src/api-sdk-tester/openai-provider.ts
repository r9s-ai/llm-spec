import OpenAI from 'openai';

import type { ProviderSummary, RunProgressHandler } from '../types';
import type { OpenAIProviderConfig } from './environment';
import {
  buildOpenAIChatCases,
  isGeminiOpenAICompatibilityTarget,
  isOpenAICompatibilityGateway,
  OPENAI_CHAT_PARAMS,
} from './cases/openai';
import { buildGeminiOpenAIChatCases } from './cases/openai/gemini';
import { buildOfficialOpenAIChatCases } from './cases/openai/openai';
import {
  buildOpenAIResponsesCases,
  OPENAI_RESPONSES_PARAMS,
} from './cases/openai-responses';
import {
  buildOpenAIExtendedCases,
  OPENAI_EXTENDED_PARAMS,
} from './cases/openai-extended';
import {
  createLoggingFetch,
  setCurrentProvider,
} from './environment';
import { createSetupSkippedSummary, executeProviderCases } from './cases/runtime';
import { normalizeVersionedApiBaseUrl } from './base-url';

function normalizeOpenAIProviderConfig(config: OpenAIProviderConfig): OpenAIProviderConfig {
  return {
    ...config,
    apiBaseUrl: normalizeVersionedApiBaseUrl(config.apiBaseUrl),
  };
}

function createOpenAIClient(config: OpenAIProviderConfig): OpenAI {
  return new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.apiBaseUrl,
    timeout: config.timeoutMs,
    maxRetries: 0,
    fetch: createLoggingFetch(config.provider),
    ...(config.customHeaders ? { defaultHeaders: config.customHeaders } : {}),
  });
}

function openAIProviderLabel(config: OpenAIProviderConfig, surface: string): string {
  return `${config.provider}(${surface})`;
}

function missingOpenAICompatibleKeyMessage(config: OpenAIProviderConfig): string {
  if (config.provider === 'xai') {
    return 'missing API key (set XAI_API_KEY / X_AI_API_KEY or API_KEY)';
  }
  return 'missing API key (set OPENAI_API_KEY or API_KEY)';
}

export async function runOpenAIChatCases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  const runConfig = normalizeOpenAIProviderConfig(config);
  const providerLabel = openAIProviderLabel(runConfig, 'chatCompletions');

  if (!runConfig.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      runConfig.model,
      runConfig.apiBaseUrl,
      OPENAI_CHAT_PARAMS,
      missingOpenAICompatibleKeyMessage(runConfig),
      onProgress,
    );
  }

  const client = createOpenAIClient(runConfig);
  setCurrentProvider(providerLabel);
  const protocolCases = buildOpenAIChatCases({ client, config: runConfig });
  const chatCompletionsCases = [...protocolCases];

  if (isGeminiOpenAICompatibilityTarget(runConfig.model)) {
    chatCompletionsCases.push(...buildGeminiOpenAIChatCases({ client, config: runConfig }));
  } else if (runConfig.provider === 'xai' || !isOpenAICompatibilityGateway(runConfig.apiBaseUrl)) {
    chatCompletionsCases.push(...buildOfficialOpenAIChatCases({ client, config: runConfig }));
  }

  return executeProviderCases(
    providerLabel,
    runConfig.model,
    runConfig.apiBaseUrl,
    OPENAI_CHAT_PARAMS,
    chatCompletionsCases,
    failFast,
    concurrency,
    onProgress,
  );
}

export async function runOpenAIResponsesCases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  const runConfig = normalizeOpenAIProviderConfig(config);
  const providerLabel = openAIProviderLabel(runConfig, 'responses');

  if (!runConfig.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      runConfig.model,
      runConfig.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      missingOpenAICompatibleKeyMessage(runConfig),
      onProgress,
    );
  }

  if (isGeminiOpenAICompatibilityTarget(runConfig.model)) {
    return createSetupSkippedSummary(
      providerLabel,
      runConfig.model,
      runConfig.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      'Gemini OpenAI compatibility coverage in gemini.md only targets chat.completions',
      onProgress,
    );
  }

  const client = createOpenAIClient(runConfig);
  setCurrentProvider(providerLabel);
  const responsesCases = buildOpenAIResponsesCases({ client, config: runConfig });
  return executeProviderCases(
    providerLabel,
    runConfig.model,
    runConfig.apiBaseUrl,
    OPENAI_RESPONSES_PARAMS,
    responsesCases,
    failFast,
    concurrency,
    onProgress,
  );
}

export async function runOpenAIExtendedCases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  const runConfig = normalizeOpenAIProviderConfig(config);
  const providerLabel = openAIProviderLabel(runConfig, 'extended');

  if (!runConfig.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      runConfig.model,
      runConfig.apiBaseUrl,
      OPENAI_EXTENDED_PARAMS,
      missingOpenAICompatibleKeyMessage(runConfig),
      onProgress,
    );
  }

  if (isGeminiOpenAICompatibilityTarget(runConfig.model)) {
    return createSetupSkippedSummary(
      providerLabel,
      runConfig.model,
      runConfig.apiBaseUrl,
      OPENAI_EXTENDED_PARAMS,
      'Gemini OpenAI compatibility coverage only targets chat.completions',
      onProgress,
    );
  }

  const client = createOpenAIClient(runConfig);
  setCurrentProvider(providerLabel);
  const extendedCases = buildOpenAIExtendedCases({ client, config: runConfig });
  return executeProviderCases(
    providerLabel,
    runConfig.model,
    runConfig.apiBaseUrl,
    OPENAI_EXTENDED_PARAMS,
    extendedCases,
    failFast,
    concurrency,
    onProgress,
  );
}

export async function runOpenAICases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary[]> {
  const chatCompletionsSummary = await runOpenAIChatCases(config, failFast, concurrency, onProgress);
  const responsesSummary = await runOpenAIResponsesCases(config, failFast, concurrency, onProgress);
  const extendedSummary = await runOpenAIExtendedCases(config, failFast, concurrency, onProgress);
  return [chatCompletionsSummary, responsesSummary, extendedSummary];
}

export async function runXAICases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
  onProgress?: RunProgressHandler,
): Promise<ProviderSummary> {
  return runOpenAIChatCases(config, failFast, concurrency, onProgress);
}
