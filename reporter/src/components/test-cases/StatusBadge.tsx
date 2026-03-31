import type { TestStatus } from '@/types'

interface StatusBadgeProps {
  status: TestStatus
}

const STYLES: Record<TestStatus, string> = {
  passed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-rose-100 text-rose-700 border-rose-200',
  skipped: 'bg-amber-100 text-amber-700 border-amber-200',
}

const LABELS: Record<TestStatus, string> = {
  passed: 'Passed',
  failed: 'Failed',
  skipped: 'Skipped',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  )
}
