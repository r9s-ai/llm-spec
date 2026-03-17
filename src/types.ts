export type ProviderName = 'openai' | 'anthropic' | 'gemini' | 'claude-agent' | 'codex';

export type TestStatus = 'passed' | 'failed' | 'skipped';

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
  apiType?: 'chatCompletions' | 'responses';
}

export interface ProviderSummary {
  provider: string; // 可以是 'openai', 'openai(chatCompletions)', 'openai(responses)', 'anthropic', 'gemini' 等
  model: string;
  apiBaseUrl?: string;
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
}
