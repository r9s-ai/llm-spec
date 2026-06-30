import { motion } from 'motion/react'
import { ShieldCheck, Activity, AlertCircle, ReceiptText } from 'lucide-react'
import type {
  R9SBillingAuditModelComparison,
  R9SBillingAuditToolCallCounts,
  R9SBillingAuditUsageTotals,
  RunSummary,
} from '@/types'

interface SummaryCardsProps {
  report: RunSummary
}

function formatInteger(value: number | undefined): string {
  return value === undefined ? 'not fetched' : new Intl.NumberFormat('en-US').format(value)
}

function formatSignedInteger(value: number | undefined): string {
  if (value === undefined) {
    return 'not fetched'
  }
  const formatted = new Intl.NumberFormat('en-US').format(Math.abs(value))
  if (value > 0) {
    return `+${formatted}`
  }
  if (value < 0) {
    return `-${formatted}`
  }
  return '0'
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

function hasAnyUsageMetric(value: R9SBillingAuditUsageTotals): boolean {
  return value.inputTokens !== undefined ||
    value.outputTokens !== undefined ||
    value.cachedTokens !== undefined ||
    value.totalTokens !== undefined
}

function comparisonModels(comparison: R9SBillingAuditModelComparison, side: 'local' | 'remote'): string[] {
  const models = side === 'local' ? comparison.localModels : comparison.remoteModels
  if (models && models.length > 0) {
    return models
  }
  return hasAnyUsageMetric(side === 'local' ? comparison.local : comparison.remote) ? [comparison.model] : []
}

function normalizeToolCallName(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[\s.-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase()
}

function isIgnoredToolCallName(value: string): boolean {
  const normalized = normalizeToolCallName(value)
  return normalized === 'amount' ||
    normalized === 'price' ||
    normalized === 'cost' ||
    normalized.endsWith('_amount') ||
    normalized.endsWith('_price') ||
    normalized.endsWith('_cost')
}

function toolCallEntries(toolCalls: R9SBillingAuditToolCallCounts | undefined): Array<[string, number]> {
  return Object.entries(toolCalls ?? {})
    .filter(([toolName, count]) => !isIgnoredToolCallName(toolName) && Number.isFinite(count) && count !== 0)
    .sort(([left], [right]) => left.localeCompare(right))
}

function remoteToolCalls(comparison: R9SBillingAuditModelComparison): R9SBillingAuditToolCallCounts | undefined {
  return comparison.remoteToolCalls ?? comparison.toolCalls
}

function hasToolCalls(comparison: R9SBillingAuditModelComparison): boolean {
  return toolCallEntries(comparison.localToolCalls).length > 0 ||
    toolCallEntries(remoteToolCalls(comparison)).length > 0 ||
    toolCallEntries(comparison.toolCallDiff).length > 0
}

function ModelSide(props: { label: string; models: string[]; missingLabel: string }) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className="mt-0.5 w-12 shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-center text-[11px] font-semibold uppercase text-slate-500">
        {props.label}
      </span>
      {props.models.length > 0 ? (
        <div className="min-w-0 space-y-1">
          {props.models.map((model) => (
            <code key={model} className="block break-all rounded bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-700">
              {model}
            </code>
          ))}
        </div>
      ) : (
        <span className="text-xs text-slate-400">{props.missingLabel}</span>
      )}
    </div>
  )
}

function ModelMapping({ comparison }: { comparison: R9SBillingAuditModelComparison }) {
  return (
    <div className="min-w-[260px] space-y-2">
      <div className="flex min-w-0 items-start gap-2">
        <span className="mt-0.5 w-12 shrink-0 rounded bg-slate-900 px-1.5 py-0.5 text-center text-[11px] font-semibold uppercase text-white">
          Bill
        </span>
        {comparison.responseId ? (
          <code className="block min-w-0 break-all rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">
            {comparison.responseId}
          </code>
        ) : (
          <span className="text-xs text-slate-400">No billing id</span>
        )}
      </div>
      <ModelSide label="Local" models={comparisonModels(comparison, 'local')} missingLabel="No local record" />
      <ModelSide label="R9S" models={comparisonModels(comparison, 'remote')} missingLabel="No R9S record" />
    </div>
  )
}

function UsageTotalsBlock(props: { totals: R9SBillingAuditUsageTotals; signed?: boolean; highlightNonZero?: boolean }) {
  const rows = [
    { label: 'Input', value: props.totals.inputTokens },
    { label: 'Output', value: props.totals.outputTokens },
    { label: 'Cached', value: props.totals.cachedTokens },
  ]

  return (
    <div className="min-w-[130px] space-y-1">
      {rows.map((row) => {
        const hasDiff = props.highlightNonZero && row.value !== undefined && row.value !== 0
        return (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <span className="text-xs text-slate-500">{row.label}</span>
            <span className={`font-medium tabular-nums ${hasDiff ? 'text-rose-700' : 'text-slate-800'}`}>
              {props.signed ? formatSignedInteger(row.value) : formatInteger(row.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function DiffTotalsBlock({ comparison }: { comparison: R9SBillingAuditModelComparison }) {
  return (
    <UsageTotalsBlock totals={comparison.diff} signed highlightNonZero />
  )
}

function ToolCallsBlock(props: {
  toolCalls: R9SBillingAuditToolCallCounts | undefined
  signed?: boolean
  highlightNonZero?: boolean
}) {
  const entries = toolCallEntries(props.toolCalls)
  const formatCount = props.signed ? formatSignedInteger : formatInteger
  const emptyLabel = props.signed ? '0' : 'none'

  if (entries.length === 0) {
    return <span className="text-xs text-slate-400">{emptyLabel}</span>
  }

  return (
    <div className="min-w-[140px] space-y-1">
      {entries.map(([toolName, count]) => {
        const hasDiff = props.highlightNonZero && count !== 0
        return (
          <div key={toolName} className="flex items-center justify-between gap-3">
            <code className="break-all rounded bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-700">
              {toolName}
            </code>
            <span className={`font-medium tabular-nums ${hasDiff ? 'text-rose-700' : 'text-slate-800'}`}>
              {props.signed ? formatCount(count) : `x${formatCount(count)}`}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function ToolCallsComparisonBlock({ comparison }: { comparison: R9SBillingAuditModelComparison }) {
  return (
    <div className="min-w-[180px] space-y-2">
      <div className="grid grid-cols-[42px_minmax(0,1fr)] gap-2">
        <span className="text-xs font-semibold uppercase text-slate-500">Local</span>
        <ToolCallsBlock toolCalls={comparison.localToolCalls} />
      </div>
      <div className="grid grid-cols-[42px_minmax(0,1fr)] gap-2">
        <span className="text-xs font-semibold uppercase text-slate-500">R9S</span>
        <ToolCallsBlock toolCalls={remoteToolCalls(comparison)} />
      </div>
      <div className="grid grid-cols-[42px_minmax(0,1fr)] gap-2">
        <span className="text-xs font-semibold uppercase text-slate-500">Diff</span>
        <ToolCallsBlock toolCalls={comparison.toolCallDiff} signed highlightNonZero />
      </div>
    </div>
  )
}

export function SummaryCards({ report }: SummaryCardsProps) {
  const total = report.totalPassed + report.totalFailed + report.totalSkipped
  const score = total > 0 ? Math.round((report.totalPassed / total) * 100) : 0
  const audit = report.billingAudit
  const showToolCalls = Boolean(audit?.comparisons.some(hasToolCalls))

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
                    <th className="py-2 pr-4 font-semibold">R9S Billing ID / Model Mapping</th>
                    <th className="py-2 pr-4 font-semibold">Local Usage</th>
                    <th className="py-2 pr-4 font-semibold">R9S Usage</th>
                    <th className="py-2 pr-4 font-semibold">Difference</th>
                    {showToolCalls && (
                      <th className="py-2 pr-4 font-semibold">Tool Calls</th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {audit.comparisons.map((comparison, index) => (
                    <tr key={`${comparison.responseId ?? comparison.model}-${index}`}>
                      <td className="py-3 pr-5 align-top">
                        <ModelMapping comparison={comparison} />
                      </td>
                      <td className="py-3 pr-5 align-top">
                        <UsageTotalsBlock totals={comparison.local} />
                      </td>
                      <td className="py-3 pr-5 align-top">
                        <UsageTotalsBlock totals={comparison.remote} />
                      </td>
                      <td className="py-3 pr-4 align-top">
                        <DiffTotalsBlock comparison={comparison} />
                      </td>
                      {showToolCalls && (
                        <td className="py-3 pr-4 align-top">
                          <ToolCallsComparisonBlock comparison={comparison} />
                        </td>
                      )}
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
