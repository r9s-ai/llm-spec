import type Anthropic from '@anthropic-ai/sdk';

import type { AnthropicProviderConfig } from '../../environment';
import { defineCases } from '../define-cases';
import { summarizeAnthropicResponse } from '../runtime';
import type { TestCase } from '../types';

const ANTHROPIC_MODEL_CATALOG_ENV = 'ANTHROPIC_INCLUDE_MODEL_CATALOG_CASES';

interface AnthropicModelCatalogContext {
  client: Anthropic;
  config: AnthropicProviderConfig;
}

export const ANTHROPIC_MESSAGES_SERVED_MODEL_IDS = [
  'claude-haiku-4.5',
  'claude-opus-4-6',
  'claude-opus-4-7',
  'claude-opus-4.6',
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

export function shouldIncludeAnthropicModelCatalogCases(): boolean {
  return envFlagEnabled(process.env[ANTHROPIC_MODEL_CATALOG_ENV]) || hasTargetCaseFilter();
}

export function anthropicModelCatalogCaseId(model: string): string {
  return `model_${model
    .replace(/\./g, '_dot_')
    .replace(/[^a-zA-Z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')}`;
}

export function buildAnthropicMessageServedModelCases({
  client,
}: AnthropicModelCatalogContext): TestCase[] {
  if (!shouldIncludeAnthropicModelCatalogCases()) {
    return [];
  }

  const cases: Record<string, {
    description: string;
    covers: readonly string[];
    run: () => Promise<string>;
  }> = {};

  for (const model of ANTHROPIC_MESSAGES_SERVED_MODEL_IDS) {
    cases[anthropicModelCatalogCaseId(model)] = {
      description: `Anthropic Messages served model smoke: ${model}`,
      covers: ['model'],
      run: async () => {
        const response = await client.messages.create({
          model,
          max_tokens: 64,
          messages: [
            {
              role: 'user',
              content: 'Reply with exactly: ok',
            },
          ],
        });
        return `model=${model}, ${summarizeAnthropicResponse(response)}`;
      },
    };
  }

  return defineCases(cases, {
    protocol: 'anthropic.messages',
    modelScope: 'anthropic-model-catalog',
  });
}
