import OpenAI from 'openai';

import type { ProviderSummary } from '../types';
import { buildOpenAICases, OPENAI_CHAT_PARAMS, OPENAI_RESPONSES_PARAMS } from './cases/openai';
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
): Promise<ProviderSummary[]> {
  if (!config.apiKey) {
    const skipReason = 'missing API key (set OPENAI_API_KEY or API_KEY)';
    return [
      createSetupSkippedSummary('openai(chatCompletions)', config.model, config.apiBaseUrl, OPENAI_CHAT_PARAMS, skipReason),
      createSetupSkippedSummary('openai(responses)', config.model, config.apiBaseUrl, OPENAI_RESPONSES_PARAMS, skipReason),
    ];
  }

  const client = new OpenAI({
    apiKey: config.apiKey,
    baseURL: config.apiBaseUrl,
    timeout: config.timeoutMs,
    maxRetries: 0,
    fetch: createLoggingFetch('openai'),
  });

  // 运行 chatCompletions 测试
  setCurrentProvider('openai(chatCompletions)');
  const chatCompletionsCases = buildOpenAICases({ client, config }, 'chatCompletions');
  const chatCompletionsSummary = await executeProviderCases(
    'openai(chatCompletions)',
    config.model,
    config.apiBaseUrl,
    OPENAI_CHAT_PARAMS,
    chatCompletionsCases,
    failFast,
  );

  // 运行 responses 测试
  setCurrentProvider('openai(responses)');
  const responsesCases = buildOpenAICases({ client, config }, 'responses');
  const responsesSummary = await executeProviderCases(
    'openai(responses)',
    config.model,
    config.apiBaseUrl,
    OPENAI_RESPONSES_PARAMS,
    responsesCases,
    failFast,
  );

  return [chatCompletionsSummary, responsesSummary];
}
