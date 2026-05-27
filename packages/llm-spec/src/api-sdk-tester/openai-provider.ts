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
  const providerLabel = openAIProviderLabel(config, 'chatCompletions');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      config.model,
      config.apiBaseUrl,
      OPENAI_CHAT_PARAMS,
      missingOpenAICompatibleKeyMessage(config),
      onProgress,
    );
  }

  const client = createOpenAIClient(config);
  setCurrentProvider(providerLabel);
  const protocolCases = buildOpenAIChatCases({ client, config });
  const chatCompletionsCases = [...protocolCases];

  if (isGeminiOpenAICompatibilityTarget(config.model)) {
    chatCompletionsCases.push(...buildGeminiOpenAIChatCases({ client, config }));
  } else if (config.provider === 'xai' || !isOpenAICompatibilityGateway(config.apiBaseUrl)) {
    chatCompletionsCases.push(...buildOfficialOpenAIChatCases({ client, config }));
  }

  return executeProviderCases(
    providerLabel,
    config.model,
    config.apiBaseUrl,
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
  const providerLabel = openAIProviderLabel(config, 'responses');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      config.model,
      config.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      missingOpenAICompatibleKeyMessage(config),
      onProgress,
    );
  }

  if (isGeminiOpenAICompatibilityTarget(config.model)) {
    return createSetupSkippedSummary(
      providerLabel,
      config.model,
      config.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      'Gemini OpenAI compatibility coverage in gemini.md only targets chat.completions',
      onProgress,
    );
  }

  const client = createOpenAIClient(config);
  setCurrentProvider(providerLabel);
  const responsesCases = buildOpenAIResponsesCases({ client, config });
  return executeProviderCases(
    providerLabel,
    config.model,
    config.apiBaseUrl,
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
  const providerLabel = openAIProviderLabel(config, 'extended');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      providerLabel,
      config.model,
      config.apiBaseUrl,
      OPENAI_EXTENDED_PARAMS,
      missingOpenAICompatibleKeyMessage(config),
      onProgress,
    );
  }

  if (isGeminiOpenAICompatibilityTarget(config.model)) {
    return createSetupSkippedSummary(
      providerLabel,
      config.model,
      config.apiBaseUrl,
      OPENAI_EXTENDED_PARAMS,
      'Gemini OpenAI compatibility coverage only targets chat.completions',
      onProgress,
    );
  }

  const client = createOpenAIClient(config);
  setCurrentProvider(providerLabel);
  const extendedCases = buildOpenAIExtendedCases({ client, config });
  return executeProviderCases(
    providerLabel,
    config.model,
    config.apiBaseUrl,
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
