export type AuditProvider = 'openai' | 'anthropic' | 'gemini';

export type OpenAIChatCompletionUsage = {
  completion_tokens: number;
  prompt_tokens: number;
  total_tokens: number;
  completion_tokens_details?: {
    accepted_prediction_tokens?: number;
    audio_tokens?: number;
    reasoning_tokens?: number;
    rejected_prediction_tokens?: number;
  };
  prompt_tokens_details?: {
    audio_tokens?: number;
    cached_tokens?: number;
  };
};

export type OpenAIResponsesUsage = {
  input_tokens: number;
  input_tokens_details?: {
    cached_tokens?: number;
  };
  output_tokens: number;
  output_tokens_details?: {
    reasoning_tokens?: number;
  };
  total_tokens: number;
};

export type OpenAIUsage = OpenAIChatCompletionUsage | OpenAIResponsesUsage;

export type AnthropicUsage = {
  cache_creation_input_tokens: number | null;
  cache_read_input_tokens: number | null;
  input_tokens: number | null;
  output_tokens: number;
  server_tool_use?: {
    web_search_requests?: number;
  };
  service_tier?: string;
};

export type GeminiMediaModality =
  | 'TEXT'
  | 'IMAGE'
  | 'VIDEO'
  | 'AUDIO'
  | 'DOCUMENT'
  | 'TOOL'
  | string;

export type GeminiModalityTokenCount = {
  modality?: GeminiMediaModality;
  tokenCount?: number;
};

export type GeminiUsage = {
  // Gemini 的 usage 既有总量，也有按模态拆分的明细。
  // 做匹配时建议先看总量，再看各模态 breakdown。
  cacheTokensDetails?: GeminiModalityTokenCount[];
  cachedContentTokenCount?: number;
  candidatesTokenCount?: number;
  candidatesTokensDetails?: GeminiModalityTokenCount[];
  promptTokenCount?: number;
  promptTokensDetails?: GeminiModalityTokenCount[];
  thoughtsTokenCount?: number;
  toolUsePromptTokenCount?: number;
  toolUsePromptTokensDetails?: GeminiModalityTokenCount[];
  totalTokenCount?: number;
  trafficType?: string;
};

export type UsageCaptureBase = {
  endTime: string;
  model: string;
  startTime: string;
};

export type OpenAIUsageCaptureResult = UsageCaptureBase & {
  provider: 'openai';
  usage: OpenAIUsage;
};

export type AnthropicUsageCaptureResult = UsageCaptureBase & {
  provider: 'anthropic';
  usage: AnthropicUsage;
};

export type GeminiUsageCaptureResult = UsageCaptureBase & {
  provider: 'gemini';
  usage: GeminiUsage;
};

export type UsageCaptureResult =
  | OpenAIUsageCaptureResult
  | AnthropicUsageCaptureResult
  | GeminiUsageCaptureResult;

export type UsageCaptureRecord = {
  model: string;
  provider: AuditProvider;
  usage: OpenAIUsage | AnthropicUsage | GeminiUsage;
};

export type UsageCaptureArtifact = {
  endTime: string;
  records: UsageCaptureRecord[];
  startTime: string;
};


export interface MediaUsageDetail {
  unit: string;
  price: number;
  usage: number;
  amount: number;
}

export interface BillingRecordItem {
  id: string;
  request_time: number;
  user_id: string;
  custom_user_id: string;
  token_id: string;
  model: string;
  model_type: string;
  input_token: number;
  output_token: number;
  input_price: number;
  output_price: number;
  cached_token: number;
  cached_price: number;
  total_amount: number;
  discount_amount: number;
  amount: number;
  channel_id: number;
  ext?: { // 建议设为可选，取决于真实接口
    input_v2?: {
      audio?: MediaUsageDetail;
      video?: MediaUsageDetail;
      image?: MediaUsageDetail;
    };
  };
}

export interface BillingRecord {
  meta: {
    code: number;
    message: string;
    request_id: string;
  };
  data: {
    list: BillingRecordItem[]; // Array<T> 简写为 T[] 也是推荐写法
    total: number;
  };
}
