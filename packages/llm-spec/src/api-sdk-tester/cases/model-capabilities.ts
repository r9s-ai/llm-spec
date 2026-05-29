import type { TestCase } from './types';

// Centralized model/parameter gates. These rules mirror the local API docs under
// docs/api-reference and keep case selection aligned with documented model-specific
// parameters such as OpenAI reasoning, legacy max_tokens/stop behavior, Anthropic
// extended thinking/server tools, and Gemini image/audio generation models.

export interface ModelCaseSelectionInput {
  provider: string;
  providerModel: string;
  apiBaseUrl?: string;
  testCase: TestCase;
}

export interface ModelCaseSelectionResult {
  selected: boolean;
  reason?: string;
}

export function normalizeModelName(model: string): string {
  return model.trim().toLowerCase();
}

export function isOSeriesModel(model: string): boolean {
  return /^o\d/.test(normalizeModelName(model));
}

export function isO3OrO4MiniModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('o3') || normalized.startsWith('o4-mini');
}

export function isGpt5SeriesModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5');
}

export function isGpt5NanoModel(model: string): boolean {
  return /^gpt-5(?:\.\d+)?-nano(?:-|$)/.test(normalizeModelName(model));
}

export function isGpt4oOrNewerModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return (
    normalized.startsWith('gpt-4o') ||
    normalized.startsWith('gpt-5') ||
    isOSeriesModel(normalized)
  );
}

export function isReasoningModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.startsWith('gpt-5') || isOSeriesModel(model);
}

export function isGpt5ProModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5-pro');
}

export function isLikelyAudioOutputModel(model: string): boolean {
  return normalizeModelName(model).includes('audio');
}

export function isOpenAICompatibilityGateway(apiBaseUrl: string | undefined): boolean {
  if (!apiBaseUrl) {
    return false;
  }

  try {
    const hostname = new URL(apiBaseUrl).hostname.toLowerCase();
    return !(hostname === 'api.openai.com' || hostname.endsWith('.openai.com'));
  } catch {
    return false;
  }
}

export function isGeminiOpenAICompatibilityTarget(model: string): boolean {
  return normalizeModelName(model).startsWith('gemini-');
}

export function supportsExtendedThinking(model: string): boolean {
  const normalized = normalizeModelName(model);
  return (
    normalized.includes('claude-4') ||
    normalized.includes('claude-opus-4') ||
    normalized.includes('claude-sonnet-4')
  );
}

export function supportsAnthropicServerTools(model: string): boolean {
  const normalized = normalizeModelName(model);
  return (
    normalized.includes('claude-opus-4') ||
    normalized.includes('claude-sonnet-4') ||
    normalized.includes('claude-haiku-4') ||
    normalized.includes('claude-mythos')
  );
}

export function isGemini25FlashModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gemini-2.5-flash');
}

export function isGeminiAudioOutputModel(model: string): boolean {
  const normalized = normalizeModelName(model);
  return normalized.includes('tts') || normalized.includes('audio');
}

export function isGeminiImageGenerationModel(model: string): boolean {
  return normalizeModelName(model).includes('image');
}

export function resolveReasoningEffort(model: string): 'none' | 'low' | 'high' {
  const normalized = normalizeModelName(model);
  if (isGpt5ProModel(normalized)) {
    return 'high';
  }
  if (normalized.startsWith('gpt-5.1')) {
    return 'none';
  }
  return 'low';
}

function selectedTestModel(providerModel: string, testCase: TestCase): string {
  return testCase.testModel ?? providerModel;
}

function isOpenAIChatProtocol(provider: string, protocol: string | undefined): boolean {
  return protocol === 'openai.chat' || provider.toLowerCase().includes('(chatcompletions)');
}

function isOpenAIResponsesProtocol(provider: string, protocol: string | undefined): boolean {
  return protocol === 'openai.responses' || provider.toLowerCase().includes('(responses)');
}

function isAnthropicMessagesProtocol(provider: string, protocol: string | undefined): boolean {
  return protocol === 'anthropic.messages' || provider.toLowerCase() === 'anthropic';
}

function isGeminiProtocol(provider: string, protocol: string | undefined): boolean {
  return protocol === 'gemini.generateContent' || provider.toLowerCase() === 'gemini';
}

function exclude(reason: string): ModelCaseSelectionResult {
  return { selected: false, reason };
}

export function selectCaseForModel({
  provider,
  providerModel,
  apiBaseUrl,
  testCase,
}: ModelCaseSelectionInput): ModelCaseSelectionResult {
  const caseId = testCase.id;
  const protocol = testCase.protocol;
  const model = selectedTestModel(providerModel, testCase);
  const compatibilityGateway = isOpenAICompatibilityGateway(apiBaseUrl);

  if (testCase.modelScope?.includes('model-catalog')) {
    return { selected: true };
  }

  if (isOpenAIChatProtocol(provider, protocol)) {
    if (caseId.startsWith('gemini_') && !isGeminiOpenAICompatibilityTarget(providerModel)) {
      return exclude(`case targets Gemini OpenAI compatibility; selected model=${providerModel}`);
    }
    if (caseId === 'input_text_image' && isGeminiOpenAICompatibilityTarget(providerModel)) {
      return exclude('Gemini OpenAI compatibility image input is covered by gemini_multimodal_image_input');
    }
    if ((caseId === 'max_tokens_legacy' || caseId === 'max_tokens_legacy_stream') &&
      (isGpt5SeriesModel(model) || isOSeriesModel(model))) {
      return exclude(`model ${model} uses max_completion_tokens; skip legacy max_tokens`);
    }
    if ((caseId === 'stop_sequences' || caseId === 'stop_string' || caseId === 'stop_sequences_stream') &&
      (isO3OrO4MiniModel(model) || (compatibilityGateway && isGpt5SeriesModel(model)))) {
      return exclude(`model ${model} is not a recommended stop-parameter target`);
    }
    if ((caseId === 'response_format_json_object' || caseId === 'response_format_json_object_stream') &&
      isGpt4oOrNewerModel(model)) {
      return exclude(`json_object mode is legacy for ${model}; json_schema is the recommended coverage`);
    }
    if (caseId.startsWith('reasoning_effort') && !isReasoningModel(model)) {
      return exclude(`reasoning_effort requires a gpt-5/o-series model; selected model=${model}`);
    }
    if (caseId === 'audio_modalities' && !isLikelyAudioOutputModel(model)) {
      return exclude(`audio output requires an audio-capable model; selected model=${model}`);
    }
    if ((caseId === 'n_choices' || caseId === 'n_choices_stream') && isGpt5NanoModel(model)) {
      return exclude(`model ${model} has fixed beta sampling limits with n=1`);
    }
    if ((caseId === 'prediction_and_verbosity' || caseId === 'prediction_and_verbosity_stream') &&
      compatibilityGateway && isReasoningModel(model)) {
      return exclude(`gateway ${apiBaseUrl ?? '(unknown)'} rejects prediction for ${model}`);
    }
  }

  if (isOpenAIResponsesProtocol(provider, protocol)) {
    if (caseId.startsWith('responses_reasoning') && !isReasoningModel(model)) {
      return exclude(`Responses reasoning requires a gpt-5/o-series model; selected model=${model}`);
    }
  }

  if (isAnthropicMessagesProtocol(provider, protocol)) {
    if ((caseId === 'thinking' || caseId === 'thinking_stream') && !supportsExtendedThinking(model)) {
      return exclude(`extended thinking requires Claude 4 or later; selected model=${model}`);
    }
    if (
      (
        caseId === 'tool_result_tool_reference' ||
        caseId === 'web_fetch_20260309_use_cache' ||
        caseId === 'web_fetch_tool_result_error_url_not_in_prior_context'
      ) &&
      !supportsAnthropicServerTools(model)
    ) {
      return exclude(`server-tool coverage requires Claude 4 or later; selected model=${model}`);
    }
  }

  if (isGeminiProtocol(provider, protocol)) {
    if (caseId === 'audio_modality' && !isGeminiAudioOutputModel(model)) {
      return exclude(`audio response coverage requires a Gemini TTS/audio model; selected model=${model}`);
    }
    if (
      (
        caseId === 'image_config' ||
        caseId === 'image_response_modalities_text_image' ||
        caseId === 'image_google_search_tool'
      ) &&
      !isGeminiImageGenerationModel(model)
    ) {
      return exclude(`image generation coverage requires a Gemini image model; selected model=${model}`);
    }
    if (
      (caseId === 'penalties' || caseId === 'penalties_stream' ||
        caseId === 'logprobs' || caseId === 'logprobs_stream') &&
      isGemini25FlashModel(model)
    ) {
      return exclude(`model ${model} rejects this parameter set on generateContent`);
    }
  }

  return { selected: true };
}

export function selectCasesForModel(
  provider: string,
  providerModel: string,
  apiBaseUrl: string | undefined,
  cases: readonly TestCase[],
): {
  selectedCases: readonly TestCase[];
  excluded: Array<{ id: string; reason: string }>;
} {
  const selectedCases: TestCase[] = [];
  const excluded: Array<{ id: string; reason: string }> = [];

  for (const testCase of cases) {
    const selection = selectCaseForModel({
      provider,
      providerModel,
      apiBaseUrl,
      testCase,
    });
    if (selection.selected) {
      selectedCases.push(testCase);
    } else {
      excluded.push({
        id: testCase.id,
        reason: selection.reason ?? 'not recommended for selected model',
      });
    }
  }

  return { selectedCases, excluded };
}
