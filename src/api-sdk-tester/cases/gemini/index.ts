import {
  FeatureSelectionPreference,
  FunctionCallingConfigMode,
  HarmBlockThreshold,
  HarmCategory,
  MediaResolution,
} from '@google/genai';

import type { GoogleGenAI } from '@google/genai';

import type { GeminiProviderConfig } from '../../runtime-config';
import { summarizeGeminiResponse, truncate, type TestCase } from '../../shared';
import { defineCases } from '../define-cases';

export const GEMINI_GENERATE_CONTENT_PARAMS = [
  'model',
  'contents',
  'httpOptions',
  'abortSignal',
  'systemInstruction',
  'temperature',
  'topP',
  'topK',
  'candidateCount',
  'maxOutputTokens',
  'stopSequences',
  'responseLogprobs',
  'logprobs',
  'presencePenalty',
  'frequencyPenalty',
  'seed',
  'responseMimeType',
  'responseSchema',
  'responseJsonSchema',
  'routingConfig',
  'modelSelectionConfig',
  'safetySettings',
  'tools',
  'toolConfig',
  'labels',
  'cachedContent',
  'responseModalities',
  'mediaResolution',
  'speechConfig',
  'audioTimestamp',
  'automaticFunctionCalling',
  'thinkingConfig',
  'imageConfig',
  'enableEnhancedCivicAnswers',
  'modelArmorConfig',
] as const;

export interface GeminiCaseContext {
  ai: GoogleGenAI;
  config: GeminiProviderConfig;
}

export function buildGeminiCases({ ai, config }: GeminiCaseContext): TestCase[] {
  const functionDeclaration = {
    name: 'echoText',
    description: 'Echoes text.',
    parametersJsonSchema: {
      type: 'object',
      properties: {
        text: { type: 'string' },
      },
      required: ['text'],
      additionalProperties: false,
    },
  };

  function countGeminiFunctionCalls(response: unknown): number {
    const obj = response as {
      functionCalls?: unknown[];
      candidates?: Array<{
        content?: {
          parts?: Array<{
            functionCall?: unknown;
          }>;
        };
      }>;
    };
    const directCount = Array.isArray(obj.functionCalls) ? obj.functionCalls.length : 0;
    const candidateCount =
      obj.candidates?.reduce((acc, candidate) => {
        const parts = candidate.content?.parts ?? [];
        const partCalls = parts.filter((part) => part.functionCall !== undefined).length;
        return acc + partCalls;
      }, 0) ?? 0;
    return directCount + candidateCount;
  }

  const cases = defineCases({
    'basic': {
      description: 'basic generateContent',
      covers: ['model', 'contents'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with exactly: ok',
        });
        return summarizeGeminiResponse(response);
      },
    },
    'sampling_and_limits': {
      description: 'sampling controls + penalties + seed',
      covers: [
        'temperature',
        'topP',
        'topK',
        'candidateCount',
        'maxOutputTokens',
        'stopSequences',
        'presencePenalty',
        'frequencyPenalty',
        'seed',
      ],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with one short word.',
          config: {
            temperature: 0.2,
            topP: 0.9,
            topK: 20,
            candidateCount: 1,
            maxOutputTokens: 32,
            stopSequences: ['\n'],
            presencePenalty: 0.1,
            frequencyPenalty: 0.1,
            seed: 7,
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'logprobs': {
      description: 'responseLogprobs + logprobs',
      covers: ['responseLogprobs', 'logprobs'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with exactly one token if possible.',
          config: {
            maxOutputTokens: 16,
            responseLogprobs: true,
            logprobs: 3,
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'system_labels_http_abort': {
      description: 'systemInstruction + httpOptions + abortSignal + civic answers',
      covers: ['systemInstruction', 'httpOptions', 'abortSignal', 'enableEnhancedCivicAnswers'],
      run: async () => {
        const controller = new AbortController();
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Give a concise answer: what is 2+2?',
          config: {
            systemInstruction: 'Keep answers concise.',
            httpOptions: {
              timeout: config.timeoutMs,
            },
            abortSignal: controller.signal,
            enableEnhancedCivicAnswers: false,
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'response_schema': {
      description: 'responseMimeType + responseSchema',
      covers: ['responseMimeType', 'responseSchema'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Return JSON with {ok:boolean, provider:string}.',
          config: {
            responseMimeType: 'application/json',
            responseSchema: {
              type: 'OBJECT',
              properties: {
                ok: { type: 'BOOLEAN' },
                provider: { type: 'STRING' },
              },
              required: ['ok', 'provider'],
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'response_json_schema': {
      description: 'responseMimeType + responseJsonSchema',
      covers: ['responseMimeType', 'responseJsonSchema'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Return JSON with {ok:string}.',
          config: {
            responseMimeType: 'application/json',
            responseJsonSchema: {
              type: 'object',
              properties: {
                ok: { type: 'string' },
              },
              required: ['ok'],
              additionalProperties: false,
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'safety_settings': {
      description: 'safetySettings',
      covers: ['safetySettings'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Say hello politely.',
          config: {
            safetySettings: [
              {
                category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH,
              },
            ],
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'tools_and_tool_config': {
      description: 'function tools + toolConfig.functionCallingConfig',
      covers: ['tools', 'toolConfig'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Call echoText with text "hello". Return only the tool call.',
          config: {
            tools: [{ functionDeclarations: [functionDeclaration] }],
            toolConfig: {
              functionCallingConfig: {
                mode: FunctionCallingConfigMode.ANY,
                allowedFunctionNames: ['echoText'],
              },
            },
          },
        });

        if (countGeminiFunctionCalls(response) <= 0) {
          throw new Error('expected at least one function call in response');
        }

        return summarizeGeminiResponse(response);
      },
    },
    'automatic_function_calling': {
      description: 'automaticFunctionCalling',
      covers: ['automaticFunctionCalling'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Call echoText with {"text":"auto"} and do not answer with plain text.',
          config: {
            tools: [{ functionDeclarations: [functionDeclaration] }],
            toolConfig: {
              functionCallingConfig: {
                mode: FunctionCallingConfigMode.ANY,
                allowedFunctionNames: ['echoText'],
              },
            },
            automaticFunctionCalling: {
              disable: false,
              maximumRemoteCalls: 1,
              ignoreCallHistory: true,
            },
          },
        });

        if (countGeminiFunctionCalls(response) <= 0) {
          throw new Error('expected at least one automatic function call in response');
        }

        return summarizeGeminiResponse(response);
      },
    },
    'thinking_config': {
      description: 'thinkingConfig',
      covers: ['thinkingConfig'],
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Solve 17*29 and return only the number.',
          config: {
            thinkingConfig: {
              includeThoughts: true,
              thinkingBudget: 128,
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'labels': {
      description: 'labels (endpoint-dependent)',
      covers: ['labels'],
      precondition: () =>
        config.enableVertexOnlyCases
          ? undefined
          : 'set GEMINI_ENABLE_VERTEX_ONLY_CASES=true to enable labels test on compatible endpoints',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with ok.',
          config: {
            labels: {
              suite: 'llm-spec',
              provider: 'gemini',
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'stream': {
      description: 'generateContentStream feature',
      covers: [],
      run: async () => {
        const stream = await ai.models.generateContentStream({
          model: config.model,
          contents: 'Count from 1 to 3, short response.',
        });
        let chunkCount = 0;
        let text = '';
        for await (const chunk of stream) {
          chunkCount += 1;
          const maybeText = (chunk as { text?: string }).text;
          if (typeof maybeText === 'string') {
            text += maybeText;
          }
          if (chunkCount >= 200) {
            break;
          }
        }
        return `chunks=${chunkCount}, text="${truncate(text)}"`;
      },
    },
    'cached_content': {
      description: 'cachedContent',
      covers: ['cachedContent'],
      precondition: () =>
        config.cachedContent ? undefined : 'set GEMINI_CACHED_CONTENT to enable cached content test',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Use cached context and say ok.',
          config: {
            cachedContent: config.cachedContent,
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'audio_modality': {
      description: 'responseModalities + mediaResolution + speechConfig + audioTimestamp',
      covers: ['responseModalities', 'mediaResolution', 'speechConfig', 'audioTimestamp'],
      precondition: () =>
        config.audioModel ? undefined : 'set GEMINI_AUDIO_MODEL to enable audio modality test',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.audioModel ?? config.model,
          contents: 'Say hello in one sentence.',
          config: {
            responseModalities: ['AUDIO'],
            mediaResolution: MediaResolution.MEDIA_RESOLUTION_LOW,
            speechConfig: {
              languageCode: 'en-US',
            },
            audioTimestamp: true,
            maxOutputTokens: 64,
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'image_config': {
      description: 'imageConfig',
      covers: ['imageConfig', 'responseModalities'],
      precondition: () =>
        config.imageModel ? undefined : 'set GEMINI_IMAGE_MODEL to enable image config test',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.imageModel ?? config.model,
          contents: 'Generate a simple landscape image.',
          config: {
            responseModalities: ['IMAGE'],
            imageConfig: {
              aspectRatio: '1:1',
              imageSize: '1K',
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'routing_and_model_selection': {
      description: 'routingConfig + modelSelectionConfig (mostly Vertex-only)',
      covers: ['routingConfig', 'modelSelectionConfig'],
      precondition: () =>
        config.enableVertexOnlyCases
          ? undefined
          : 'set GEMINI_ENABLE_VERTEX_ONLY_CASES=true to enable Vertex-only config tests',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with ok.',
          config: {
            routingConfig: {
              autoMode: {
                modelRoutingPreference: 'BALANCED',
              },
            },
            modelSelectionConfig: {
              featureSelectionPreference: FeatureSelectionPreference.BALANCED,
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
    'model_armor': {
      description: 'modelArmorConfig (Vertex-only)',
      covers: ['modelArmorConfig'],
      precondition: () =>
        config.modelArmorPromptTemplate && config.modelArmorResponseTemplate
          ? undefined
          : 'set GEMINI_MODEL_ARMOR_PROMPT_TEMPLATE and GEMINI_MODEL_ARMOR_RESPONSE_TEMPLATE',
      run: async () => {
        const response = await ai.models.generateContent({
          model: config.model,
          contents: 'Reply with ok.',
          config: {
            modelArmorConfig: {
              promptTemplateName: config.modelArmorPromptTemplate,
              responseTemplateName: config.modelArmorResponseTemplate,
            },
          },
        });
        return summarizeGeminiResponse(response);
      },
    },
  });

  return cases;
}
