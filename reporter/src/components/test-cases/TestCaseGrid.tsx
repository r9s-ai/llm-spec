import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { TestCaseCard } from './TestCaseCard'
import type { TestCaseResult } from '@/types'

interface TestCaseGridProps {
  cases: TestCaseResult[]
  onViewTrace?: (result: TestCaseResult) => void
}

type Filter = 'all' | 'passed' | 'failed' | 'skipped'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'passed', label: 'Passed' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'Skipped' },
]

export function TestCaseGrid({ cases, onViewTrace }: TestCaseGridProps) {
  const [filter, setFilter] = useState<Filter>('all')

  const filtered = filter === 'all' ? cases : cases.filter((c) => c.status === filter)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-900">Test Cases</h2>
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          {FILTERS.map((f) => (
            <Button
              key={f.value}
              variant={filter === f.value ? 'default' : 'ghost'}
              size="sm"
              className="text-xs h-7 px-3"
              onClick={() => setFilter(f.value)}
            >
              {f.label}
              {f.value !== 'all' && (
                <span className="ml-1.5 text-[10px] opacity-70">
                  {cases.filter((c) => c.status === f.value).length}
                </span>
              )}
            </Button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          No test cases match the filter "{filter}"
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((result, index) => (
            <TestCaseCard
              key={result.id}
              result={result}
              index={index}
              onClick={onViewTrace}
            />
          ))}
        </div>
      )}
    </div>
  )
}
