import type { RunSummary } from '@/types'

function sanitizeReportBackendInfo(report: RunSummary): RunSummary {
  if (!report.runSnapshot || !('backendUrl' in report.runSnapshot)) {
    return report
  }
  const runSnapshot = { ...report.runSnapshot }
  delete runSnapshot.backendUrl
  return { ...report, runSnapshot }
}

export function parseReport(json: unknown): RunSummary {
  if (!json || typeof json !== 'object') {
    throw new Error('Invalid report: expected a JSON object')
  }

  const data = json as Record<string, unknown>

  if (!Array.isArray(data.providers)) {
    throw new Error('Invalid report: missing "providers" array')
  }

  for (const provider of data.providers as unknown[]) {
    if (!provider || typeof provider !== 'object') {
      throw new Error('Invalid report: each provider must be an object')
    }
    const p = provider as Record<string, unknown>
    if (typeof p.provider !== 'string') {
      throw new Error('Invalid report: each provider must have a "provider" string')
    }
    if (!Array.isArray(p.caseResults)) {
      throw new Error(`Invalid report: provider "${p.provider}" missing "caseResults" array`)
    }
  }

  return sanitizeReportBackendInfo(json as RunSummary)
}

export async function loadFromFile(file: File): Promise<RunSummary> {
  const text = await file.text()
  const json = JSON.parse(text)
  return parseReport(json)
}

export async function loadFromUrl(url: string): Promise<RunSummary> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch report: ${response.status} ${response.statusText}`)
  }
  const json = await response.json()
  return parseReport(json)
}
