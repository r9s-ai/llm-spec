import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import type { TestStatus } from '@/types'

interface StatusIconProps {
  status: TestStatus
  className?: string
}

export function StatusIcon({ status, className = '' }: StatusIconProps) {
  switch (status) {
    case 'passed':
      return <CheckCircle2 className={`text-emerald-500 ${className}`} />
    case 'failed':
      return <XCircle className={`text-rose-500 ${className}`} />
    case 'skipped':
      return <AlertCircle className={`text-amber-500 ${className}`} />
  }
}
