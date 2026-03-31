import { motion } from 'motion/react'
import { Terminal, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { StatusIcon } from './StatusIcon'
import { StatusBadge } from './StatusBadge'
import type { TestCaseResult } from '@/types'
import { formatDuration, truncate } from '@/lib/format'

interface TestCaseCardProps {
  result: TestCaseResult
  index: number
  onClick?: (result: TestCaseResult) => void
}

export function TestCaseCard({ result, index, onClick }: TestCaseCardProps) {
  const hasTrace = result.httpTrace && result.httpTrace.exchanges.length > 0

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: Math.min(index * 0.05, 0.5) }}
      onClick={() => onClick?.(result)}
      className={`bg-white p-5 rounded-xl border shadow-sm transition-all flex gap-4 group cursor-pointer
        ${result.status === 'failed'
          ? 'border-rose-200 hover:border-rose-400 hover:shadow-md'
          : result.status === 'skipped'
            ? 'border-amber-200 hover:border-amber-400 hover:shadow-md'
            : 'border-slate-200 hover:border-blue-300 hover:shadow-md'
        }`}
    >
      <div className="flex-shrink-0 mt-1">
        <StatusIcon status={result.status} className="w-6 h-6" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <h3 className="font-semibold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
            {result.id}
          </h3>
          <StatusBadge status={result.status} />
        </div>

        <p className="text-sm text-slate-600 mb-2">{result.description}</p>

        <div className="flex items-center gap-3 text-xs text-slate-500 mb-2">
          <span className="flex items-center gap-1 font-mono">
            <Clock className="w-3 h-3" />
            {formatDuration(result.durationMs)}
          </span>
          {result.apiType && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {result.apiType}
            </Badge>
          )}
        </div>

        {result.coveredParams.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {result.coveredParams.slice(0, 5).map((param) => (
              <span
                key={param}
                className="text-[10px] font-mono bg-slate-50 px-1.5 py-0.5 rounded text-slate-500 border border-slate-100"
              >
                {param}
              </span>
            ))}
            {result.coveredParams.length > 5 && (
              <span className="text-[10px] font-mono text-slate-400">
                +{result.coveredParams.length - 5} more
              </span>
            )}
          </div>
        )}

        {result.error && (
          <div className="text-xs font-mono bg-rose-50 px-2 py-1.5 rounded text-rose-600 border border-rose-100 break-all">
            {truncate(result.error, 200)}
          </div>
        )}

        {!result.error && result.detail && (
          <div className="text-xs font-mono bg-slate-50 px-2 py-1.5 rounded text-slate-500 border border-slate-100">
            {truncate(result.detail, 200)}
          </div>
        )}

        <div className="flex items-center justify-end mt-2">
          <div className="flex items-center gap-1 text-xs font-medium text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">
            <Terminal className="w-3 h-3" />
            {hasTrace ? 'View Trace' : 'View Details'}
          </div>
        </div>
      </div>
    </motion.div>
  )
}
