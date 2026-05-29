import type { StandardApiType } from '@/types'

export function normalizeModelName(model: string): string {
  return model.trim().toLowerCase()
}

export function isOpenAIOSeriesModel(model: string): boolean {
  return /^o\d/.test(normalizeModelName(model))
}

export function isOpenAIO3OrO4MiniModel(model: string): boolean {
  const normalized = normalizeModelName(model)
  return normalized.startsWith('o3') || normalized.startsWith('o4-mini')
}

export function isOpenAIGpt5SeriesModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gpt-5')
}

export function isOpenAIGpt5NanoModel(model: string): boolean {
  return /^gpt-5(?:\.\d+)?-nano(?:-|$)/.test(normalizeModelName(model))
}

export function isOpenAIGpt4oOrNewerModel(model: string): boolean {
  const normalized = normalizeModelName(model)
  return normalized.startsWith('gpt-4o') || normalized.startsWith('gpt-5') || isOpenAIOSeriesModel(model)
}

export function isOpenAIReasoningModel(model: string): boolean {
  const normalized = normalizeModelName(model)
  return normalized.startsWith('gpt-5') || isOpenAIOSeriesModel(model)
}

export function isOpenAIAudioOutputModel(model: string): boolean {
  return normalizeModelName(model).includes('audio')
}

export function isGeminiOpenAICompatibilityModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gemini-')
}

export function isGemini25FlashModel(model: string): boolean {
  return normalizeModelName(model).startsWith('gemini-2.5-flash')
}

export function isGeminiAudioOutputModel(model: string): boolean {
  const normalized = normalizeModelName(model)
  return normalized.includes('tts') || normalized.includes('audio')
}

export function isGeminiImageGenerationModel(model: string): boolean {
  return normalizeModelName(model).includes('image')
}

export function supportsAnthropicExtendedThinking(model: string): boolean {
  const normalized = normalizeModelName(model)
  return normalized.includes('claude-4') || normalized.includes('claude-opus-4') || normalized.includes('claude-sonnet-4')
}

export function supportsAnthropicServerTools(model: string): boolean {
  const normalized = normalizeModelName(model)
  return (
    normalized.includes('claude-opus-4')
    || normalized.includes('claude-sonnet-4')
    || normalized.includes('claude-haiku-4')
    || normalized.includes('claude-mythos')
  )
}

export function isCaseRecommendedForModel(apiType: StandardApiType, caseId: string, model: string): boolean {
  if (apiType === 'openai.chat') {
    if (caseId.startsWith('gemini_')) {
      return isGeminiOpenAICompatibilityModel(model)
    }
    if (caseId === 'input_text_image') {
      return !isGeminiOpenAICompatibilityModel(model)
    }
    if (caseId === 'max_tokens_legacy' || caseId === 'max_tokens_legacy_stream') {
      return !isOpenAIGpt5SeriesModel(model) && !isOpenAIOSeriesModel(model)
    }
    if (caseId === 'stop_sequences' || caseId === 'stop_string' || caseId === 'stop_sequences_stream') {
      return !isOpenAIO3OrO4MiniModel(model)
    }
    if (caseId === 'response_format_json_object' || caseId === 'response_format_json_object_stream') {
      return !isOpenAIGpt4oOrNewerModel(model)
    }
    if (caseId.startsWith('reasoning_effort')) {
      return isOpenAIReasoningModel(model)
    }
    if (caseId === 'audio_modalities') {
      return isOpenAIAudioOutputModel(model)
    }
    if (caseId === 'n_choices' || caseId === 'n_choices_stream') {
      return !isOpenAIGpt5NanoModel(model)
    }
  }

  if (apiType === 'openai.responses' && caseId.startsWith('responses_reasoning')) {
    return isOpenAIReasoningModel(model)
  }

  if (apiType === 'anthropic.messages') {
    if (caseId === 'thinking' || caseId === 'thinking_stream') {
      return supportsAnthropicExtendedThinking(model)
    }
    if (
      caseId === 'tool_result_tool_reference'
      || caseId === 'web_fetch_20260309_use_cache'
      || caseId === 'web_fetch_tool_result_error_url_not_in_prior_context'
    ) {
      return supportsAnthropicServerTools(model)
    }
  }

  if (apiType === 'gemini.generateContent') {
    if (caseId === 'penalties' || caseId === 'penalties_stream' || caseId === 'logprobs' || caseId === 'logprobs_stream') {
      return !isGemini25FlashModel(model)
    }
    if (caseId === 'audio_modality') {
      return isGeminiAudioOutputModel(model)
    }
    if (caseId === 'image_config' || caseId === 'image_response_modalities_text_image' || caseId === 'image_google_search_tool') {
      return isGeminiImageGenerationModel(model)
    }
  }

  return true
}
