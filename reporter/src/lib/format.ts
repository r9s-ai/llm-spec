export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export function formatCoverage(covered: number, total: number): string {
  if (total <= 0) return '0/0 (0.0%)'
  const percent = ((covered / total) * 100).toFixed(1)
  return `${covered}/${total} (${percent}%)`
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString()
}

export function formatTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleTimeString()
}

export function formatProviderName(provider: string): string {
  if (provider.includes('claude-agent')) return 'Claude Agent'
  if (provider.includes('codex')) return 'Codex'
  if (provider.includes('openai')) return 'OpenAI'
  if (provider.includes('anthropic')) return 'Anthropic'
  if (provider.includes('gemini')) return 'Gemini'
  return provider
}

export function isAgentProvider(provider: string): boolean {
  return provider.includes('claude-agent') || provider.includes('codex')
}

export function tryFormatJson(text: string | undefined): string {
  if (!text) return '(empty)'
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

export function truncate(text: string, max = 120): string {
  if (text.length <= max) return text
  return `${text.slice(0, max - 3)}...`
}
