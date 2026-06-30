import { Clock, RotateCcw, Server } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { RunSummary } from '@/types'
import { formatDateTime } from '@/lib/format'

interface HeaderProps {
  report: RunSummary
  onBackHome: () => void
}

export function Header({ report, onBackHome }: HeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 md:flex-row md:items-center md:justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-3 text-slate-500 mb-2">
          <Server className="w-5 h-5" />
          <span className="font-mono text-sm tracking-tight">
            {report.providers.length} provider{report.providers.length > 1 ? 's' : ''} tested
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
          LLM Spec Test Report
        </h1>
        <p className="text-slate-500 max-w-2xl">
          Automated testing of LLM API feature compatibility and SDK parameter coverage.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center md:justify-end">
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-left shadow-sm sm:text-right">
          <div className="text-sm font-medium text-slate-900">Test Period</div>
          <div className="mt-1 flex items-center gap-1 text-xs text-slate-500 sm:justify-end">
            <Clock className="w-3 h-3" />
            <span>
              {formatDateTime(report.startedAt)} — {formatDateTime(report.finishedAt)}
            </span>
          </div>
        </div>
        <Button variant="outline" onClick={onBackHome} aria-label="Clear report">
          <RotateCcw className="mr-2 h-4 w-4" />
          Clear Report
        </Button>
      </div>
    </header>
  )
}
