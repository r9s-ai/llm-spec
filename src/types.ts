export type ProviderName = 'openai' | 'anthropic' | 'gemini';

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
}

export interface ProviderSummary {
  provider: ProviderName;
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
