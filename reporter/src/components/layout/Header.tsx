import { Server, Clock, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { RunSummary } from '@/types'
import { formatDateTime } from '@/lib/format'

interface HeaderProps {
  report: RunSummary
  onLoadNew: () => void
}

export function Header({ report, onLoadNew }: HeaderProps) {
  return (
    <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-200">
      <div className="space-y-2">
        <div className="flex items-center gap-3 text-slate-500 mb-2">
          <Server className="w-5 h-5" />
          <span className="font-mono text-sm tracking-tight">
            {report.providers.length} provider{report.providers.length > 1 ? 's' : ''} tested
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-slate-900">
          LLM Spec Test Report
        </h1>
        <p className="text-slate-500 max-w-2xl">
          Automated testing of LLM API feature compatibility and SDK parameter coverage.
        </p>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right hidden md:block">
          <div className="text-sm font-medium text-slate-900">Test Period</div>
          <div className="text-xs text-slate-500 flex items-center gap-1 justify-end mt-1">
            <Clock className="w-3 h-3" />
            {formatDateTime(report.startedAt)} — {formatDateTime(report.finishedAt)}
          </div>
        </div>
        <Button variant="outline" onClick={onLoadNew}>
          <Upload className="w-4 h-4 mr-2" />
          Load New
        </Button>
      </div>
    </header>
  )
}
