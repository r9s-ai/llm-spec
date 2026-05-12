import type { PlatformRunConfig, RunProgressEvent, RunProgressHandler, RunSummary } from '@/types'
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
