export type TestStatus = 'passed' | 'failed' | 'skipped'
export type RunProgressPhase = 'provider-start' | 'case-start' | 'case-complete' | 'provider-complete'

export interface RunProgressEvent {
  phase: RunProgressPhase
  provider: string
  caseId?: string
  description?: string
  status?: TestStatus
  completed: number
  total: number
}

export type RunProgressHandler = (event: RunProgressEvent) => void

export type StandardApiType =
  | 'openai.chat'
  | 'openai.responses'
  | 'anthropic.messages'
  | 'gemini.generateContent'
export type AgentProvider = 'claude-agent' | 'codex'

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
  protocol?: string
  modelScope?: string
  httpTrace?: TestCaseHttpTrace
}

export interface ProviderSummary {
  provider: string
  model: string
  apiBaseUrl?: string
  setupDetail?: string
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
  runSnapshot?: RunSnapshot
}

export interface RunTargetSnapshot {
  kind: 'standard' | 'agent'
  enabled: boolean
  apiType?: StandardApiType
  agentProvider?: AgentProvider
  model?: string
  targetCases?: string
  execution?: 'browser' | 'backend'
}

export interface RunSnapshot {
  siteName?: string
  apiBaseUrl?: string
  backendUrl?: string
  standardExecution: 'browser' | 'backend'
  timeoutMs: number
  concurrency: number
  failFast: boolean
  targets: RunTargetSnapshot[]
}

export interface PlatformRunConfig {
  kind: 'standard' | 'agent'
  apiType?: StandardApiType
  agentProvider?: AgentProvider
  apiKey?: string
  apiBaseUrl?: string
  model?: string
  timeoutMs: number
  targetCases?: string
  customHeaders?: Record<string, string>
  apiVersion?: string
  failFast: boolean
  concurrency: number
  workingDirectory?: string
  skipGitRepoCheck?: boolean
  testImagePath?: string
}
