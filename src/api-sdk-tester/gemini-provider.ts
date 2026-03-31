import { GoogleGenAI } from '@google/genai';

import type { ProviderSummary } from '../types';
import { GEMINI_GENERATE_CONTENT_PARAMS, buildGeminiCases } from './cases/gemini';
import type { GeminiProviderConfig } from './runtime-config';
import {
  createLoggingFetch,
  createSetupSkippedSummary,
  executeProviderCases,
  setCurrentProvider,
} from './shared';

export async function runGeminiCases(
  config: GeminiProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  setCurrentProvider('gemini');

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'gemini',
      config.model,
      config.apiBaseUrl,
      GEMINI_GENERATE_CONTENT_PARAMS,
      'missing API key (set GEMINI_API_KEY / GOOGLE_API_KEY / API_KEY)',
    );
  }

  const clientOptions: {
    apiKey: string;
    apiVersion?: string;
    httpOptions?: {
      baseUrl?: string;
      timeout?: number;
    };
    fetch?: typeof fetch;
  } = {
    apiKey: config.apiKey,
    fetch: createLoggingFetch('gemini'),
  };

  if (config.apiVersion) {
    clientOptions.apiVersion = config.apiVersion;
  }
  if (config.apiBaseUrl || config.timeoutMs > 0) {
    clientOptions.httpOptions = {
      baseUrl: config.apiBaseUrl,
      timeout: config.timeoutMs,
    };
  }

  const ai = new GoogleGenAI(clientOptions);
  const cases = buildGeminiCases({ ai, config });

  return executeProviderCases(
    'gemini',
    config.model,
    config.apiBaseUrl,
    GEMINI_GENERATE_CONTENT_PARAMS,
    cases,
    failFast,
    concurrency,
  );
}
