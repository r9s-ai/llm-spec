export type TestStatus = 'passed' | 'failed' | 'skipped'

export interface HttpTraceRequest {
  requestId?: string
  testId?: string
  url: string
  method: string
  headers: Record<string, string>
  body?: string
}

export interface HttpTraceResponse {
  requestId?: string
  testId?: string
  kind: 'response' | 'error'
  url: string
  status?: number
  statusText?: string
  durationMs?: number
  headers: Record<string, string>
  body?: string
  error?: string
}

export interface HttpTraceExchange {
  request: HttpTraceRequest
  response?: HttpTraceResponse
}

export interface TestCaseHttpTrace {
  source: string
  testId: string
  exchangeCount: number
  exchanges: HttpTraceExchange[]
}

export interface TestCaseResult {
  id: string
  description: string
  status: TestStatus
  durationMs: number
  coveredParams: string[]
  detail?: string
  error?: string
  apiType?: 'chatCompletions' | 'responses'
  httpTrace?: TestCaseHttpTrace
}

export interface ProviderSummary {
  provider: string
  model: string
  apiBaseUrl?: string
  startedAt: string
  finishedAt: string
  passed: number
  failed: number
  skipped: number
  caseResults: TestCaseResult[]
  allParams: string[]
  coveredParams: string[]
  untestedParams: string[]
}

export interface RunSummary {
  startedAt: string
  finishedAt: string
  providers: ProviderSummary[]
  totalPassed: number
  totalFailed: number
  totalSkipped: number
}
