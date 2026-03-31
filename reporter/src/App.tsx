import { useState } from 'react'
import { useReportData } from '@/hooks/useReportData'
import { UploadScreen } from '@/components/layout/UploadScreen'
import { Header } from '@/components/layout/Header'
import { SummaryCards } from '@/components/summary/SummaryCards'
import { ProviderTabs } from '@/components/summary/ProviderTabs'
import { ParamCoverage } from '@/components/coverage/ParamCoverage'
import { TestCaseGrid } from '@/components/test-cases/TestCaseGrid'
import { TraceModal } from '@/components/trace/TraceModal'
import type { TestCaseResult, ProviderSummary } from '@/types'
import { isAgentProvider, formatProviderName } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Bot } from 'lucide-react'

export default function App() {
  const { report, error, loading, loadSample, loadFile, reset } = useReportData()
  const [activeProvider, setActiveProvider] = useState('__overview__')
  const [traceCase, setTraceCase] = useState<TestCaseResult | null>(null)

  if (!report) {
    return (
      <UploadScreen
        onLoadFile={loadFile}
        onLoadSample={loadSample}
        loading={loading}
        error={error}
      />
    )
  }

  const activeProviderData: ProviderSummary | null =
    activeProvider === '__overview__'
      ? null
      : report.providers.find((p) => p.provider === activeProvider) ?? null

  const displayCases = activeProviderData
    ? activeProviderData.caseResults
    : report.providers.flatMap((p) => p.caseResults)

  return (
    <div className="min-h-screen p-6 md:p-12 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        <Header report={report} onLoadNew={reset} />

        <SummaryCards report={report} />

        <ProviderTabs
          providers={report.providers}
          activeProvider={activeProvider}
          onProviderChange={setActiveProvider}
        />

        {activeProviderData && <ParamCoverage provider={activeProviderData} />}

        {/* Provider section headers in overview mode */}
        {activeProvider === '__overview__' && (
          <div className="space-y-6">
            {report.providers.map((provider) => {
              const isAgent = isAgentProvider(provider.provider)
              return (
                <div key={provider.provider} className="space-y-3">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-slate-900">
                      {formatProviderName(provider.provider)}
                    </h3>
                    {isAgent && (
                      <Badge className="bg-gradient-to-r from-amber-400 to-orange-400 text-white text-xs">
                        <Bot className="w-3 h-3 mr-1" />
                        Agent SDK
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      {provider.model}
                    </Badge>
                    <span className="text-sm text-slate-500">
                      {provider.passed} passed / {provider.failed} failed / {provider.skipped} skipped
                    </span>
                  </div>
                  <TestCaseGrid
                    cases={provider.caseResults}
                    onViewTrace={setTraceCase}
                  />
                </div>
              )
            })}
          </div>
        )}

        {/* Single provider mode */}
        {activeProviderData && (
          <TestCaseGrid
            cases={activeProviderData.caseResults}
            onViewTrace={setTraceCase}
          />
        )}
      </div>

      {traceCase && (
        <TraceModal result={traceCase} onClose={() => setTraceCase(null)} />
      )}
    </div>
  )
}
