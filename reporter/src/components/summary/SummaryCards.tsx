import { motion } from 'motion/react'
import { ShieldCheck, Activity, AlertCircle } from 'lucide-react'
import type { RunSummary } from '@/types'

interface SummaryCardsProps {
  report: RunSummary
}

export function SummaryCards({ report }: SummaryCardsProps) {
  const total = report.totalPassed + report.totalFailed + report.totalSkipped
  const score = total > 0 ? Math.round((report.totalPassed / total) * 100) : 0

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-emerald-100 text-emerald-600 rounded-lg">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-700">Pass Rate</h3>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold tracking-tight">{score}</span>
          <span className="text-slate-500 font-medium">/ 100</span>
        </div>
        <div className="w-full bg-slate-100 h-2 rounded-full mt-4 overflow-hidden">
          <motion.div
            className="bg-emerald-500 h-full rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${score}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-100 text-blue-600 rounded-lg">
            <Activity className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-700">Tests Passed</h3>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold tracking-tight">{report.totalPassed}</span>
          <span className="text-slate-500 font-medium">/ {total}</span>
        </div>
        <p className="text-sm text-slate-500 mt-4">
          Successfully completed test cases
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-amber-100 text-amber-600 rounded-lg">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h3 className="font-semibold text-slate-700">Failed / Skipped</h3>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold tracking-tight">{report.totalFailed + report.totalSkipped}</span>
          <span className="text-slate-500 font-medium">tests</span>
        </div>
        <p className="text-sm text-slate-500 mt-4">
          {report.totalFailed} failed, {report.totalSkipped} skipped
        </p>
      </motion.div>
    </div>
  )
}
