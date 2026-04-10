import OpenAI from 'openai';

import type { ProviderSummary } from '../types';
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
    fetch: createLoggingFetch('openai'),
    ...(config.customHeaders ? { defaultHeaders: config.customHeaders } : {}),
  });
}

export async function runOpenAIChatCases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'openai(chatCompletions)',
      config.model,
      config.apiBaseUrl,
      OPENAI_CHAT_PARAMS,
      'missing API key (set OPENAI_API_KEY or API_KEY)',
    );
  }

  const client = createOpenAIClient(config);
  setCurrentProvider('openai(chatCompletions)');
  const protocolCases = buildOpenAIChatCases({ client, config });
  const chatCompletionsCases = [...protocolCases];

  if (isGeminiOpenAICompatibilityTarget(config.model)) {
    chatCompletionsCases.push(...buildGeminiOpenAIChatCases({ client, config }));
  } else if (!isOpenAICompatibilityGateway(config.apiBaseUrl)) {
    chatCompletionsCases.push(...buildOfficialOpenAIChatCases({ client, config }));
  }

  return executeProviderCases(
    'openai(chatCompletions)',
    config.model,
    config.apiBaseUrl,
    OPENAI_CHAT_PARAMS,
    chatCompletionsCases,
    failFast,
    concurrency,
  );
}

export async function runOpenAIResponsesCases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'openai(responses)',
      config.model,
      config.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      'missing API key (set OPENAI_API_KEY or API_KEY)',
    );
  }

  if (isGeminiOpenAICompatibilityTarget(config.model)) {
    return createSetupSkippedSummary(
      'openai(responses)',
      config.model,
      config.apiBaseUrl,
      OPENAI_RESPONSES_PARAMS,
      'Gemini OpenAI compatibility coverage in gemini.md only targets chat.completions',
    );
  }

  const client = createOpenAIClient(config);
  setCurrentProvider('openai(responses)');
  const responsesCases = buildOpenAIResponsesCases({ client, config });
  return executeProviderCases(
    'openai(responses)',
    config.model,
    config.apiBaseUrl,
    OPENAI_RESPONSES_PARAMS,
    responsesCases,
    failFast,
    concurrency,
  );
}

export async function runOpenAICases(
  config: OpenAIProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary[]> {
  const chatCompletionsSummary = await runOpenAIChatCases(config, failFast, concurrency);
  const responsesSummary = await runOpenAIResponsesCases(config, failFast, concurrency);
  return [chatCompletionsSummary, responsesSummary];
}
