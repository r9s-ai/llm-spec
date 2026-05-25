import { Modality } from '@google/genai';

import { defineCases } from '../define-cases';
import { summarizeGeminiResponse } from '../runtime';
import type { TestCase } from '../types';
import type { GeminiCaseContext } from './index';

const GEMINI_MODEL_CATALOG_ENV = 'GEMINI_INCLUDE_MODEL_CATALOG_CASES';

type GeminiGenerateContentModelKind = 'text' | 'image' | 'tts';

interface GeminiServedGenerateContentModel {
  id: string;
  kind: GeminiGenerateContentModelKind;
}

// Source: Google Gemini model pages and deprecations page checked on 2026-05-12.
// This catalog is limited to models that can be smoked through models.generateContent.
export const GEMINI_TEXT_SERVED_MODEL_IDS = [
  'gemini-3.1-pro-preview',
  'gemini-3.1-pro-preview-customtools',
  'gemini-3-flash-preview',
  'gemini-3.1-flash-lite',
  'gemini-3.1-flash-lite-preview',
  'gemini-2.5-pro',
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash',
  'gemini-2.0-flash-001',
  'gemini-2.0-flash-lite',
  'gemini-2.0-flash-lite-001',
  'gemini-robotics-er-1.6-preview',
] as const;

export const GEMINI_IMAGE_SERVED_MODEL_IDS = [
  'gemini-3.1-flash-image-preview',
  'gemini-3-pro-image-preview',
  'gemini-2.5-flash-image',
] as const;

export const GEMINI_TTS_SERVED_MODEL_IDS = [
  'gemini-3.1-flash-tts-preview',
  'gemini-2.5-flash-preview-tts',
  'gemini-2.5-pro-preview-tts',
] as const;

export const GEMINI_GENERATE_CONTENT_SERVED_MODEL_IDS = [
  ...GEMINI_TEXT_SERVED_MODEL_IDS,
  ...GEMINI_IMAGE_SERVED_MODEL_IDS,
  ...GEMINI_TTS_SERVED_MODEL_IDS,
] as const;

const GEMINI_SERVED_GENERATE_CONTENT_MODELS: readonly GeminiServedGenerateContentModel[] = [
  ...GEMINI_TEXT_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'text' as const })),
  ...GEMINI_IMAGE_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'image' as const })),
  ...GEMINI_TTS_SERVED_MODEL_IDS.map((id) => ({ id, kind: 'tts' as const })),
];

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

export function shouldIncludeGeminiModelCatalogCases(): boolean {
  return envFlagEnabled(process.env[GEMINI_MODEL_CATALOG_ENV]) || hasTargetCaseFilter();
}

export function geminiModelCatalogCaseId(model: string): string {
  return `model_${model.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`;
}

export function buildGeminiServedModelCases(context: GeminiCaseContext): TestCase[] {
  if (!shouldIncludeGeminiModelCatalogCases()) {
    return [];
  }

  const { ai } = context;
  const cases: Record<string, {
    description: string;
    covers: readonly string[];
    run: () => Promise<string>;
  }> = {};

  for (const model of GEMINI_SERVED_GENERATE_CONTENT_MODELS) {
    cases[geminiModelCatalogCaseId(model.id)] = {
      description: `Gemini served generateContent model smoke (${model.kind}): ${model.id}`,
      covers: ['model'],
      run: async () => {
        if (model.kind === 'image') {
          const response = await ai.models.generateContent({
            model: model.id,
            contents: 'Generate a simple one-color square icon.',
            config: {
              responseModalities: [Modality.IMAGE],
              imageConfig: {
                aspectRatio: '1:1',
                imageSize: '1K',
              },
            },
          });
          return `model=${model.id}, kind=${model.kind}, ${summarizeGeminiResponse(response)}`;
        }

        if (model.kind === 'tts') {
          const response = await ai.models.generateContent({
            model: model.id,
            contents: 'Say: ok.',
            config: {
              responseModalities: [Modality.AUDIO],
              speechConfig: {
                voiceConfig: {
                  prebuiltVoiceConfig: {
                    voiceName: 'Kore',
                  },
                },
              },
            },
          });
          return `model=${model.id}, kind=${model.kind}, ${summarizeGeminiResponse(response)}`;
        }

        const response = await ai.models.generateContent({
          model: model.id,
          contents: 'Reply with exactly: ok',
          config: {
            maxOutputTokens: 64,
          },
        });
        return `model=${model.id}, kind=${model.kind}, ${summarizeGeminiResponse(response)}`;
      },
    };
  }

  return defineCases(cases, {
    protocol: 'gemini.generateContent',
    modelScope: 'gemini-model-catalog',
  });
}
