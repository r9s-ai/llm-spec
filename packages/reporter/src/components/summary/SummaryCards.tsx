import { motion } from 'motion/react'
import { ShieldCheck, Activity, AlertCircle, ReceiptText } from 'lucide-react'
import type { RunSummary } from '@/types'

interface SummaryCardsProps {
  report: RunSummary
}

function formatInteger(value: number | undefined): string {
  return value === undefined ? 'not fetched' : new Intl.NumberFormat('en-US').format(value)
}

function formatAmount(value: number | undefined): string {
  return value === undefined ? 'not fetched' : value.toFixed(8)
}

function diffInteger(remote: number | undefined, local: number | undefined): number | undefined {
  return remote !== undefined && local !== undefined ? remote - local : undefined
}

function auditStatusClass(status: string): string {
  if (status === 'passed') {
    return 'bg-emerald-100 text-emerald-700'
  }
  if (status === 'mismatched' || status === 'error') {
    return 'bg-rose-100 text-rose-700'
  }
  return 'bg-amber-100 text-amber-700'
}

export function SummaryCards({ report }: SummaryCardsProps) {
  const total = report.totalPassed + report.totalFailed + report.totalSkipped
  const score = total > 0 ? Math.round((report.totalPassed / total) * 100) : 0
  const audit = report.billingAudit

  return (
    <>
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

      {audit && (
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-slate-100 text-slate-700 rounded-lg">
                <ReceiptText className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-800">R9S Billing Audit</h3>
                <p className="text-sm text-slate-500">
                  {audit.local.recordCount} local records, {audit.remote.recordCount}/{audit.remote.totalAvailable} billing records
                </p>
              </div>
            </div>
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${auditStatusClass(audit.status)}`}>
              {audit.status}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-slate-500">Billing Amount</div>
              <div className="mt-1 font-semibold text-slate-900">{formatAmount(audit.remote.totals.amount)}</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-slate-500">Input Diff</div>
              <div className="mt-1 font-semibold text-slate-900">{formatInteger(diffInteger(audit.remote.totals.inputTokens, audit.local.totals.inputTokens))}</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-slate-500">Output Diff</div>
              <div className="mt-1 font-semibold text-slate-900">{formatInteger(diffInteger(audit.remote.totals.outputTokens, audit.local.totals.outputTokens))}</div>
            </div>
          </div>

          {audit.error && (
            <pre className="mt-4 whitespace-pre-wrap rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {audit.error}
            </pre>
          )}

          {audit.warnings.length > 0 && (
            <div className="mt-4 space-y-1 text-sm text-amber-700">
              {audit.warnings.map((warning) => (
                <div key={warning}>{warning}</div>
              ))}
            </div>
          )}

          {audit.comparisons.length > 0 && (
            <div className="mt-5 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-2 pr-4 font-semibold">Model</th>
                    <th className="py-2 pr-4 font-semibold">Local In/Out/Cached</th>
                    <th className="py-2 pr-4 font-semibold">R9S In/Out/Cached</th>
                    <th className="py-2 pr-4 font-semibold">Diff In/Out/Cached</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {audit.comparisons.map((comparison) => (
                    <tr key={comparison.model}>
                      <td className="py-2 pr-4 font-mono text-xs text-slate-700">{comparison.model}</td>
                      <td className="py-2 pr-4 text-slate-700">
                        {formatInteger(comparison.local.inputTokens)} / {formatInteger(comparison.local.outputTokens)} / {formatInteger(comparison.local.cachedTokens)}
                      </td>
                      <td className="py-2 pr-4 text-slate-700">
                        {formatInteger(comparison.remote.inputTokens)} / {formatInteger(comparison.remote.outputTokens)} / {formatInteger(comparison.remote.cachedTokens)}
                      </td>
                      <td className={comparison.matched ? 'py-2 pr-4 text-emerald-700' : 'py-2 pr-4 text-rose-700'}>
                        {formatInteger(comparison.diff.inputTokens)} / {formatInteger(comparison.diff.outputTokens)} / {formatInteger(comparison.diff.cachedTokens)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      )}
    </>
  )
}
