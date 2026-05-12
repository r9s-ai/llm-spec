import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import type { ProviderSummary } from '@/types'
import { formatCoverage } from '@/lib/format'

interface ParamCoverageProps {
  provider: ProviderSummary
}

export function ParamCoverage({ provider }: ParamCoverageProps) {
  const total = provider.allParams.length
  const covered = provider.coveredParams.length
  const percent = total > 0 ? Math.round((covered / total) * 100) : 0

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-700">Parameter Coverage</h3>
        <span className="text-sm font-mono text-slate-500">
          {formatCoverage(covered, total)}
        </span>
      </div>
      <Progress value={percent} className="h-2" />
      {provider.untestedParams.length > 0 && (
        <div className="space-y-3">
          <div>
            <div className="text-xs font-medium text-slate-500 mb-2">
              Covered ({provider.coveredParams.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {provider.coveredParams.map((param) => (
                <Badge key={param} variant="secondary" className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100">
                  {param}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-slate-500 mb-2">
              Untested ({provider.untestedParams.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {provider.untestedParams.map((param) => (
                <Badge key={param} variant="outline" className="text-xs text-amber-600 border-amber-200">
                  {param}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
