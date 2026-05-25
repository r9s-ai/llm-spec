import type {
  BackendRunHistoryEntry,
  PlatformRunConfig,
  RunProgressEvent,
  RunProgressHandler,
  RunSummary,
} from '@/types'
import { parseReport } from '@/lib/data-loader'

export interface BackendHealth {
  ok: boolean
  service?: string
  agentTests?: boolean
  backendRun?: boolean
}

interface BackendRunOptions {
  onProgress?: RunProgressHandler
}

type BackendRunStreamMessage =
  | { type: 'progress', event: RunProgressEvent }
  | { type: 'complete', summary: unknown }
  | { type: 'error', error: string }

function normalizeBackendUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim().replace(/\/+$/, '')
  if (!trimmed) {
    throw new Error('Backend URL is required')
  }
  return trimmed
}

export async function checkBackendHealth(rawUrl: string): Promise<BackendHealth> {
  const backendUrl = normalizeBackendUrl(rawUrl)
  const response = await fetch(`${backendUrl}/api/health`)
  if (!response.ok) {
    throw new Error(`Backend health check failed: ${response.status} ${response.statusText}`)
  }
  return await response.json() as BackendHealth
}

function isBackendRunStreamMessage(value: unknown): value is BackendRunStreamMessage {
  if (!value || typeof value !== 'object' || !('type' in value)) {
    return false
  }
  const message = value as { type: unknown }
  if (message.type === 'progress') {
    return 'event' in value
  }
  if (message.type === 'complete') {
    return 'summary' in value
  }
  if (message.type === 'error') {
    return 'error' in value
  }
  return false
}

async function readBackendRunStream(response: Response, onProgress: RunProgressHandler): Promise<RunSummary> {
  if (!response.body) {
    throw new Error('Backend run stream is not readable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completedSummary: RunSummary | undefined

  const handleLine = (line: string): void => {
    const trimmed = line.trim()
    if (!trimmed) {
      return
    }
    const parsed = JSON.parse(trimmed) as unknown
    if (!isBackendRunStreamMessage(parsed)) {
      throw new Error('Backend run stream returned an invalid message')
    }
    if (parsed.type === 'progress') {
      onProgress(parsed.event)
      return
    }
    if (parsed.type === 'complete') {
      completedSummary = parseReport(parsed.summary)
      return
    }
    throw new Error(`Backend run failed: ${parsed.error}`)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      handleLine(line)
    }
  }

  buffer += decoder.decode()
  handleLine(buffer)

  if (!completedSummary) {
    throw new Error('Backend run stream ended before returning a report')
  }
  return completedSummary
}

export async function runBackendCases(
  rawUrl: string,
  config: PlatformRunConfig,
  options: BackendRunOptions = {},
): Promise<RunSummary> {
  const backendUrl = normalizeBackendUrl(rawUrl)
  const response = await fetch(`${backendUrl}${options.onProgress ? '/api/run/stream' : '/api/run'}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })

  if (options.onProgress) {
    if (!response.ok) {
      const message = await response.text().catch(() => `${response.status} ${response.statusText}`)
      throw new Error(`Backend run failed: ${message}`)
    }
    return readBackendRunStream(response, options.onProgress)
  }

  const payload = await response.json().catch(() => undefined)
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'error' in payload
      ? String((payload as { error: unknown }).error)
      : `${response.status} ${response.statusText}`
    throw new Error(`Backend run failed: ${message}`)
  }
  return parseReport(payload)
}

function isBackendRunHistoryEntry(value: unknown): value is BackendRunHistoryEntry {
  if (!value || typeof value !== 'object') {
    return false
  }

  const entry = value as Record<string, unknown>
  return (
    typeof entry.id === 'string' &&
    typeof entry.fileName === 'string' &&
    typeof entry.startedAt === 'string' &&
    typeof entry.finishedAt === 'string' &&
    Array.isArray(entry.providers) &&
    Array.isArray(entry.models) &&
    typeof entry.totalPassed === 'number' &&
    typeof entry.totalFailed === 'number' &&
    typeof entry.totalSkipped === 'number'
  )
}

export async function listBackendRunHistory(rawUrl: string): Promise<BackendRunHistoryEntry[]> {
  const backendUrl = normalizeBackendUrl(rawUrl)
  const response = await fetch(`${backendUrl}/api/history`)
  if (!response.ok) {
    throw new Error(`Backend history failed: ${response.status} ${response.statusText}`)
  }

  const payload = await response.json() as unknown
  if (!payload || typeof payload !== 'object' || !Array.isArray((payload as { items?: unknown }).items)) {
    throw new Error('Backend history returned an invalid payload')
  }

  return (payload as { items: unknown[] }).items.filter(isBackendRunHistoryEntry)
}

export async function loadBackendRunHistoryReport(rawUrl: string, id: string): Promise<RunSummary> {
  const backendUrl = normalizeBackendUrl(rawUrl)
  const response = await fetch(`${backendUrl}/api/history/${encodeURIComponent(id)}`)
  if (!response.ok) {
    throw new Error(`Backend history report failed: ${response.status} ${response.statusText}`)
  }
  return parseReport(await response.json() as unknown)
}

export async function saveBackendRunReport(
  rawUrl: string,
  report: RunSummary,
): Promise<BackendRunHistoryEntry | undefined> {
  const backendUrl = normalizeBackendUrl(rawUrl)
  const response = await fetch(`${backendUrl}/api/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  })

  const payload = await response.json().catch(() => undefined) as unknown
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'error' in payload
      ? String((payload as { error: unknown }).error)
      : `${response.status} ${response.statusText}`
    throw new Error(`Backend history save failed: ${message}`)
  }

  if (!payload || typeof payload !== 'object') {
    return undefined
  }
  const entry = (payload as { entry?: unknown }).entry
  return isBackendRunHistoryEntry(entry) ? entry : undefined
}
