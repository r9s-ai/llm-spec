export type ProviderName = 'openai' | 'anthropic' | 'gemini' | 'xai' | 'claude-agent' | 'codex';

export type TestStatus = 'passed' | 'failed' | 'skipped';

export type RunProgressPhase = 'provider-start' | 'case-start' | 'case-complete' | 'provider-complete';

export interface RunProgressEvent {
  phase: RunProgressPhase;
  provider: string;
  caseId?: string;
  description?: string;
  status?: TestStatus;
  completed: number;
  total: number;
}

export type RunProgressHandler = (event: RunProgressEvent) => void;

export interface HttpTraceRequest {
  requestId?: string;
  testId?: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}

export interface HttpTraceResponse {
  requestId?: string;
  testId?: string;
  kind: 'response' | 'error';
  url: string;
  status?: number;
  statusText?: string;
  durationMs?: number;
  headers: Record<string, string>;
  body?: string;
  error?: string;
}

export interface HttpTraceExchange {
  request: HttpTraceRequest;
  response?: HttpTraceResponse;
}

export interface TestCaseHttpTrace {
  source: string;
  testId: string;
  exchangeCount: number;
  exchanges: HttpTraceExchange[];
}

export type MaybePromise<T> = T | Promise<T>;

export interface PluginRequestParams {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}

export interface PluginRequestPatch {
  url?: string;
  method?: string;
  headers?: Record<string, string | null | undefined>;
  body?: unknown;
}

export type PluginBeforeCaseResult =
  | PluginRequestPatch
  | { request?: PluginRequestPatch }
  | void;

export interface PluginCaseRequestContext {
  provider: string;
  testId: string;
  id: string;
  name: string;
  description: string;
  requestId?: string;
  requestIndex: number;
  request: PluginRequestParams;
}

export interface PluginCaseCompleteContext {
  provider: string;
  model: string;
  apiBaseUrl?: string;
  id: string;
  name: string;
  description: string;
  result: TestCaseResult;
  request?: HttpTraceRequest;
  response?: HttpTraceResponse;
  exchanges: HttpTraceExchange[];
}

export interface PluginRunCompleteContext {
  summary: RunSummary;
}

export interface TestLifecyclePlugin {
  name?: string;
  beforeCase?: (context: PluginCaseRequestContext) => MaybePromise<PluginBeforeCaseResult>;
  afterCase?: (context: PluginCaseCompleteContext) => MaybePromise<void>;
  afterRun?: (context: PluginRunCompleteContext) => MaybePromise<void>;
}

export interface R9SBillingAuditConfig {
  enabled: boolean;
  managerBaseUrl?: string;
  managerKey?: string;
  apiKey?: string;
  tokenId?: string;
}

export type R9SBillingAuditStatus = 'passed' | 'mismatched' | 'warning' | 'error';

export interface R9SBillingAuditUsageTotals {
  inputTokens?: number;
  outputTokens?: number;
  cachedTokens?: number;
  totalTokens?: number;
  amount?: number;
  totalAmount?: number;
}

export type R9SBillingAuditToolCallCounts = Record<string, number>;

export interface R9SBillingAuditLocalRecord {
  provider: string;
  model: string;
  apiBaseUrl?: string;
  caseId: string;
  name: string;
  description: string;
  requestId?: string;
  xRequestId?: string;
  responseId?: string;
  usage: R9SBillingAuditUsageTotals;
  toolCalls?: R9SBillingAuditToolCallCounts;
}

export interface R9SBillingAuditRemoteRecord {
  id?: string;
  xRequestId?: string;
  responseId?: string;
  requestTime?: number;
  userId?: string;
  customUserId?: string;
  tokenId?: string;
  model: string;
  modelType?: string;
  usage: R9SBillingAuditUsageTotals;
  toolCalls?: R9SBillingAuditToolCallCounts;
  ext?: unknown;
}

export interface R9SBillingAuditUsageSummary {
  recordCount: number;
  totals: R9SBillingAuditUsageTotals;
  byModel: Record<string, R9SBillingAuditUsageTotals>;
}

export interface R9SBillingAuditModelComparison {
  responseId?: string;
  model: string;
  localModels?: string[];
  remoteModels?: string[];
  matched: boolean;
  local: R9SBillingAuditUsageTotals;
  remote: R9SBillingAuditUsageTotals;
  diff: R9SBillingAuditUsageTotals;
  localToolCalls?: R9SBillingAuditToolCallCounts;
  remoteToolCalls?: R9SBillingAuditToolCallCounts;
  toolCallDiff?: R9SBillingAuditToolCallCounts;
  toolCalls?: R9SBillingAuditToolCallCounts;
}

export interface R9SBillingAuditReport {
  status: R9SBillingAuditStatus;
  startedAt: string;
  finishedAt: string;
  query: {
    endpoint: string;
    startTime: number;
    endTime: number;
    pageSize: number;
    tokenId?: string;
    apiKeyFingerprint?: string;
  };
  local: R9SBillingAuditUsageSummary & {
    records: R9SBillingAuditLocalRecord[];
  };
  remote: R9SBillingAuditUsageSummary & {
    totalAvailable: number;
    records: R9SBillingAuditRemoteRecord[];
  };
  comparisons: R9SBillingAuditModelComparison[];
  warnings: string[];
  error?: string;
}

export interface ProviderConfig {
  provider: ProviderName;
  apiKey?: string;
  apiBaseUrl?: string;
  model: string;
  timeoutMs: number;
}

export interface TestCaseResult {
  id: string;
  description: string;
  status: TestStatus;
  durationMs: number;
  coveredParams: string[];
  detail?: string;
  error?: string;
  apiType?: 'chatCompletions' | 'responses' | 'embeddings' | 'audio' | 'images';
  protocol?: string;
  modelScope?: string;
  testModel?: string;
  httpTrace?: TestCaseHttpTrace;
}

export interface ProviderSummary {
  provider: string; // 可以是 'openai', 'openai(chatCompletions)', 'openai(responses)', 'anthropic', 'gemini' 等
  model: string;
  apiBaseUrl?: string;
  setupDetail?: string;
  startedAt: string;
  finishedAt: string;
  passed: number;
  failed: number;
  skipped: number;
  caseResults: TestCaseResult[];
  allParams: string[];
  coveredParams: string[];
  untestedParams: string[];
}

export interface RunSummary {
  startedAt: string;
  finishedAt: string;
  providers: ProviderSummary[];
  totalPassed: number;
  totalFailed: number;
  totalSkipped: number;
  runSnapshot?: RunSnapshot;
  billingAudit?: R9SBillingAuditReport;
}

export interface RunTargetSnapshot {
  kind: 'standard' | 'agent';
  enabled: boolean;
  apiType?: string;
  agentProvider?: string;
  model?: string;
  targetCases?: string;
  execution?: 'browser' | 'backend';
}

export interface RunSnapshot {
  siteName?: string;
  apiBaseUrl?: string;
  backendUrl?: string;
  standardExecution: 'browser' | 'backend';
  timeoutMs: number;
  concurrency: number;
  failFast: boolean;
  targets: RunTargetSnapshot[];
}
