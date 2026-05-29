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
