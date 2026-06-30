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
  testModel?: string
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
  billingAudit?: R9SBillingAuditReport
}

export interface R9SBillingAuditConfig {
  enabled: boolean
  managerBaseUrl?: string
  managerKey?: string
  apiKey?: string
  tokenId?: string
}

export type R9SBillingAuditStatus = 'passed' | 'mismatched' | 'warning' | 'error'

export interface R9SBillingAuditUsageTotals {
  inputTokens?: number
  outputTokens?: number
  cachedTokens?: number
  totalTokens?: number
  amount?: number
  totalAmount?: number
}

export type R9SBillingAuditToolCallCounts = Record<string, number>

export interface R9SBillingAuditLocalRecord {
  provider: string
  model: string
  apiBaseUrl?: string
  caseId: string
  name: string
  description: string
  requestId?: string
  xRequestId?: string
  responseId?: string
  usage: R9SBillingAuditUsageTotals
  toolCalls?: R9SBillingAuditToolCallCounts
}

export interface R9SBillingAuditRemoteRecord {
  id?: string
  xRequestId?: string
  responseId?: string
  requestTime?: number
  userId?: string
  customUserId?: string
  tokenId?: string
  model: string
  modelType?: string
  usage: R9SBillingAuditUsageTotals
  toolCalls?: R9SBillingAuditToolCallCounts
  ext?: unknown
}

export interface R9SBillingAuditUsageSummary {
  recordCount: number
  totals: R9SBillingAuditUsageTotals
  byModel: Record<string, R9SBillingAuditUsageTotals>
}

export interface R9SBillingAuditModelComparison {
  responseId?: string
  model: string
  localModels?: string[]
  remoteModels?: string[]
  matched: boolean
  local: R9SBillingAuditUsageTotals
  remote: R9SBillingAuditUsageTotals
  diff: R9SBillingAuditUsageTotals
  localToolCalls?: R9SBillingAuditToolCallCounts
  remoteToolCalls?: R9SBillingAuditToolCallCounts
  toolCallDiff?: R9SBillingAuditToolCallCounts
  toolCalls?: R9SBillingAuditToolCallCounts
}

export interface R9SBillingAuditReport {
  status: R9SBillingAuditStatus
  startedAt: string
  finishedAt: string
  query: {
    endpoint: string
    startTime: number
    endTime: number
    pageSize: number
    tokenId?: string
    apiKeyFingerprint?: string
  }
  local: R9SBillingAuditUsageSummary & {
    records: R9SBillingAuditLocalRecord[]
  }
  remote: R9SBillingAuditUsageSummary & {
    totalAvailable: number
    records: R9SBillingAuditRemoteRecord[]
  }
  comparisons: R9SBillingAuditModelComparison[]
  warnings: string[]
  error?: string
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
  pluginPaths?: string[]
  billingAudit?: R9SBillingAuditConfig
  persistResult?: boolean
  runSnapshot?: RunSnapshot
}

export type BackendJobStatus = 'queued' | 'running' | 'completed' | 'failed'
export type BackendJobTargetStatus = 'pending' | 'running' | 'complete'

export interface BackendJobTarget {
  id: string
  kind: 'standard' | 'agent'
  enabled: boolean
  apiType?: StandardApiType
  agentProvider?: AgentProvider
  apiKey?: string
  apiBaseUrl?: string
  model?: string
  timeoutMs?: number
  concurrency?: number
  targetCases?: string
  customHeaders?: Record<string, string>
  apiVersion?: string
  workingDirectory?: string
  skipGitRepoCheck?: boolean
  testImagePath?: string
  failFast?: boolean
}

export interface BackendJobRequest {
  apiKey?: string
  apiBaseUrl?: string
  backendUrl?: string
  standardExecution: 'browser' | 'backend'
  timeoutMs: number
  concurrency: number
  failFast?: boolean
  customHeaders?: Record<string, string>
  apiVersion?: string
  workingDirectory?: string
  skipGitRepoCheck?: boolean
  testImagePath?: string
  pluginPaths?: string[]
  billingAudit?: R9SBillingAuditConfig
  persistResult?: boolean
  runSnapshot?: RunSnapshot
  targets: BackendJobTarget[]
}

export interface BackendJobTargetProgress {
  id: string
  label: string
  status: BackendJobTargetStatus
  completed: number
  total: number
  passed: number
  failed: number
  skipped: number
  currentCase?: string
}

export interface BackendJobProgress {
  completed: number
  total: number
  percent: number
  statusText: string
  detailText: string
  passed: number
  failed: number
  skipped: number
  targets: BackendJobTargetProgress[]
}

export interface BackendRunHistoryEntry {
  id: string
  fileName: string
  createdAt: string
  startedAt: string
  finishedAt: string
  providerCount: number
  providers: string[]
  models: string[]
  totalPassed: number
  totalFailed: number
  totalSkipped: number
  siteName?: string
  apiBaseUrl?: string
  backendUrl?: string
}

export interface BackendJobStatusResponse {
  id: string
  status: BackendJobStatus
  createdAt: string
  startedAt?: string
  finishedAt?: string
  error?: string
  progress: BackendJobProgress
  summary?: RunSummary
  historyEntry?: BackendRunHistoryEntry
}
