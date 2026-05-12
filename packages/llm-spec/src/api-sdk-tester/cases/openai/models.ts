import { defineCases } from '../define-cases';
import { summarizeOpenAIResponse, summarizeOpenAIResponses } from '../runtime';
import type { TestCase } from '../types';
import {
  createBaseMessages,
  isOpenAICompatibilityGateway,
  type OpenAICaseContext,
} from './shared';

const OPENAI_MODEL_CATALOG_ENV = 'OPENAI_INCLUDE_MODEL_CATALOG_CASES';

export const OPENAI_CHAT_SERVED_MODEL_IDS = [
  'gpt-5.5',
  'gpt-5.5-2026-04-23',
  'gpt-5.4',
  'gpt-5.4-2026-03-05',
  'gpt-5.4-mini',
  'gpt-5.4-mini-2026-03-17',
  'gpt-5.4-nano',
  'gpt-5.4-nano-2026-03-17',
  'gpt-5.3-codex',
  'chat-latest',
  'gpt-5.3-chat-latest',
  'gpt-5.2',
  'gpt-5.2-2025-12-11',
  'gpt-5.2-chat-latest',
  'gpt-5.2-pro',
  'gpt-5.2-pro-2025-12-11',
  'gpt-5.2-codex',
  'gpt-5.1',
  'gpt-5.1-2025-11-13',
  'gpt-5.1-codex',
  'gpt-5.1-codex-mini',
  'gpt-5.1-mini',
  'gpt-5.1-chat-latest',
  'gpt-5',
  'gpt-5-mini',
  'gpt-5-nano',
  'gpt-5-2025-08-07',
  'gpt-5-mini-2025-08-07',
  'gpt-5-nano-2025-08-07',
  'gpt-5-chat-latest',
  'gpt-4.1',
  'gpt-4.1-mini',
  'gpt-4.1-nano',
  'gpt-4.1-2025-04-14',
  'gpt-4.1-mini-2025-04-14',
  'gpt-4.1-nano-2025-04-14',
  'o4-mini',
  'o4-mini-2025-04-16',
  'o3',
  'o3-2025-04-16',
  'o3-mini',
  'o3-mini-2025-01-31',
  'o1',
  'o1-2024-12-17',
  'gpt-4o',
  'gpt-4o-2024-11-20',
  'gpt-4o-2024-08-06',
  'gpt-4o-2024-05-13',
  'gpt-4o-audio-preview',
  'gpt-4o-audio-preview-2024-12-17',
  'gpt-4o-audio-preview-2025-06-03',
  'gpt-4o-mini-audio-preview',
  'gpt-4o-mini-audio-preview-2024-12-17',
  'gpt-4o-realtime-preview',
  'gpt-4o-realtime-preview-2024-12-17',
  'gpt-4o-mini-realtime-preview',
  'gpt-4o-mini-realtime-preview-2024-12-17',
  'gpt-4o-search-preview',
  'gpt-4o-search-preview-2025-03-11',
  'gpt-4o-mini-search-preview',
  'gpt-4o-mini-search-preview-2025-03-11',
  'gpt-4o-mini',
  'gpt-4o-mini-2024-07-18',
  'gpt-audio-1.5',
  'gpt-audio',
  'gpt-audio-2025-08-28',
  'gpt-audio-mini',
  'gpt-audio-mini-2025-12-15',
  'gpt-audio-mini-2025-10-06',
  'gpt-realtime-2',
  'gpt-realtime-1.5',
  'gpt-realtime',
  'gpt-realtime-2025-08-28',
  'gpt-realtime-mini',
  'gpt-realtime-mini-2025-12-15',
  'gpt-realtime-mini-2025-10-06',
  'gpt-4-turbo',
  'gpt-4-turbo-2024-04-09',
  'gpt-4',
  'gpt-4-0613',
  'gpt-3.5-turbo',
  'gpt-3.5-turbo-16k',
  'gpt-3.5-turbo-0125',
  'gpt-3.5-turbo-1106',
] as const;

export const OPENAI_RESPONSES_ONLY_SERVED_MODEL_IDS = [
  'gpt-5.5-pro',
  'gpt-5.5-pro-2026-04-23',
  'gpt-5.4-pro',
  'gpt-5.4-pro-2026-03-05',
  'gpt-5-codex',
  'gpt-5-pro',
  'gpt-5-pro-2025-10-06',
  'gpt-5.1-codex-max',
  'o1-pro',
  'o1-pro-2025-03-19',
  'o3-pro',
  'o3-pro-2025-06-10',
  'o3-deep-research',
  'o3-deep-research-2025-06-26',
  'o4-mini-deep-research',
  'o4-mini-deep-research-2025-06-26',
  'computer-use-preview',
  'computer-use-preview-2025-03-11',
] as const;

export const OPENAI_RESPONSES_SERVED_MODEL_IDS = [
  ...OPENAI_CHAT_SERVED_MODEL_IDS,
  ...OPENAI_RESPONSES_ONLY_SERVED_MODEL_IDS,
] as const;

function envFlagEnabled(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
}

function hasTargetCaseFilter(): boolean {
  return ['TARGET_CASES', 'TEST_CASES', 'CASE_IDS'].some((key) =>
    Boolean(process.env[key]?.trim()),
  );
}

export function shouldIncludeOpenAIModelCatalogCases(): boolean {
  return envFlagEnabled(process.env[OPENAI_MODEL_CATALOG_ENV]) || hasTargetCaseFilter();
}

export function openAIModelCatalogCaseId(prefix: 'model_' | 'responses_model_', model: string): string {
  return `${prefix}${model.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`;
}

function createOpenAIModelCatalogPrecondition(
  { config }: OpenAICaseContext,
  apiSurface: 'chat.completions' | 'responses',
): () => string | undefined {
  return () =>
    isOpenAICompatibilityGateway(config.apiBaseUrl)
      ? `OpenAI model catalog smoke tests target native OpenAI model IDs; skip ${apiSurface} on compatibility gateway ${config.apiBaseUrl ?? '(unknown)'}`
      : undefined;
}

function isLongRunningResponsesModel(model: string): boolean {
  const normalized = model.toLowerCase();
  return normalized.includes('-pro') || normalized.includes('deep-research');
}

export function buildOpenAIChatServedModelCases(context: OpenAICaseContext): TestCase[] {
  if (!shouldIncludeOpenAIModelCatalogCases()) {
    return [];
  }

  const { client } = context;
  const cases: Record<string, {
    description: string;
    covers: readonly string[];
    precondition: () => string | undefined;
    run: () => Promise<string>;
  }> = {};

  for (const model of OPENAI_CHAT_SERVED_MODEL_IDS) {
    cases[openAIModelCatalogCaseId('model_', model)] = {
      description: `OpenAI served model smoke: ${model}`,
      covers: ['model'],
      precondition: createOpenAIModelCatalogPrecondition(context, 'chat.completions'),
      run: async () => {
        const response = await client.chat.completions.create({
          model,
          messages: createBaseMessages(model),
        });
        return `model=${model}, ${summarizeOpenAIResponse(response)}`;
      },
    };
  }

  return defineCases(cases, {
    protocol: 'openai.chat',
    modelScope: 'openai-model-catalog',
  });
}

export function buildOpenAIResponsesServedModelCases(context: OpenAICaseContext): TestCase[] {
  if (!shouldIncludeOpenAIModelCatalogCases()) {
    return [];
  }

  const { client } = context;
  const cases: Record<string, {
    description: string;
    covers: readonly string[];
    precondition: () => string | undefined;
    run: () => Promise<string>;
  }> = {};

  for (const model of OPENAI_RESPONSES_SERVED_MODEL_IDS) {
    cases[openAIModelCatalogCaseId('responses_model_', model)] = {
      description: `OpenAI Responses served model smoke: ${model}`,
      covers: ['model'],
      precondition: createOpenAIModelCatalogPrecondition(context, 'responses'),
      run: async () => {
        const response = await client.responses.create({
          model,
          input: 'Reply with exactly: ok',
          max_output_tokens: 64,
          ...(isLongRunningResponsesModel(model) ? { background: true } : {}),
        });
        return `model=${model}, ${summarizeOpenAIResponses(response)}`;
      },
    };
  }

  return defineCases(cases, {
    apiType: 'responses',
    protocol: 'openai.responses',
    modelScope: 'openai-model-catalog',
  });
}
