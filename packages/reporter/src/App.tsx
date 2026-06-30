import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertCircle,
  BarChart3,
  Bot,
  CheckCircle2,
  PanelLeft,
  Server,
  TerminalSquare,
  Wifi,
} from 'lucide-react'
import { useReportData } from '@/hooks/useReportData'
import { PlatformConsole, type PlatformConsoleStatus } from '@/components/platform/PlatformConsole'
import { Header } from '@/components/layout/Header'
import { SummaryCards } from '@/components/summary/SummaryCards'
import { ProviderTabs } from '@/components/summary/ProviderTabs'
import { ParamCoverage } from '@/components/coverage/ParamCoverage'
import { TestCaseGrid } from '@/components/test-cases/TestCaseGrid'
import { TraceModal } from '@/components/trace/TraceModal'
import type { ProviderSummary, RunSummary, TestCaseResult } from '@/types'
import { isAgentProvider, formatProviderName } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

type AppView = 'console' | 'reporter'

const DEFAULT_CONSOLE_STATUS: PlatformConsoleStatus = {
  running: false,
  hasRunProgress: false,
  statusText: 'Ready',
  detailText: 'Waiting for a run',
  percent: 0,
  passed: 0,
  failed: 0,
  skipped: 0,
  enabledTargets: 0,
  siteName: 'Unsaved site',
  executionSummary: 'Browser fetch',
  requiresBackend: false,
  backendStatus: null,
  activeBackendJobId: null,
  error: null,
}

export default function App() {
  const { report, error, loading, loadFile, loadReport, reset } = useReportData()
  const [activeView, setActiveView] = useState<AppView>('console')
  const [activeProvider, setActiveProvider] = useState('__overview__')
  const [traceCase, setTraceCase] = useState<TestCaseResult | null>(null)
  const [consoleStatus, setConsoleStatus] = useState<PlatformConsoleStatus>(DEFAULT_CONSOLE_STATUS)
  const [siteControls, setSiteControls] = useState<ReactNode | null>(null)
  const [reporterHome, setReporterHome] = useState<ReactNode | null>(null)
  const [sidebarExpanded, setSidebarExpanded] = useState(false)

  useEffect(() => {
    if (report) {
      setActiveView('reporter')
    }
  }, [report])

  const handleReport = useCallback((data: RunSummary) => {
    setActiveProvider('__overview__')
    setTraceCase(null)
    loadReport(data)
    setActiveView('reporter')
  }, [loadReport])

  const handleLoadFile = useCallback(async (file: File) => {
    setActiveProvider('__overview__')
    setTraceCase(null)
    await loadFile(file)
    setActiveView('reporter')
  }, [loadFile])

  const handleClearReport = useCallback(() => {
    setActiveProvider('__overview__')
    setTraceCase(null)
    reset()
    setActiveView('console')

    const url = new URL(window.location.href)
    if (url.searchParams.has('report')) {
      url.searchParams.delete('report')
      window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
    }
  }, [reset])

  return (
    <div className="h-screen overflow-hidden bg-[#f3f3f3] font-sans text-slate-900">
      <div className="flex h-[calc(100vh-2rem)] overflow-hidden">
        <ActivityBar
          activeView={activeView}
          expanded={sidebarExpanded}
          hasReport={Boolean(report)}
          onToggleExpanded={() => { setSidebarExpanded((current) => !current) }}
          onViewChange={setActiveView}
        />

        <main className="min-w-0 flex-1 overflow-hidden bg-[#F8F9FB]">
          <section className={cn('h-full', activeView === 'console' ? 'block' : 'hidden')}>
            <PlatformConsole
              onReport={handleReport}
              onLoadFile={handleLoadFile}
              onStatusChange={setConsoleStatus}
              onSiteControlsChange={setSiteControls}
              onReporterHomeChange={setReporterHome}
              loading={loading}
              error={error}
            />
          </section>

          <section className={cn('h-full', activeView === 'reporter' ? 'block' : 'hidden')}>
            <ReporterPage
              report={report}
              activeProvider={activeProvider}
              onProviderChange={setActiveProvider}
              onViewTrace={setTraceCase}
              onClearReport={handleClearReport}
              reporterHome={reporterHome}
            />
          </section>
        </main>
      </div>

      <StatusBar
        status={consoleStatus}
        activeView={activeView}
        hasReport={Boolean(report)}
        siteControls={siteControls}
      />

      {traceCase && (
        <TraceModal result={traceCase} onClose={() => { setTraceCase(null) }} />
      )}
    </div>
  )
}

interface ActivityBarProps {
  activeView: AppView
  expanded: boolean
  hasReport: boolean
  onToggleExpanded: () => void
  onViewChange: (view: AppView) => void
}

function ActivityBar({
  activeView,
  expanded,
  hasReport,
  onToggleExpanded,
  onViewChange,
}: ActivityBarProps) {
  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col items-center justify-between border-r border-[#2b2b2b] bg-[#181818] py-2 text-slate-300 transition-[width] duration-150 ease-out',
        expanded ? 'w-48' : 'w-14',
      )}
    >
      <div className="flex w-full flex-col items-center gap-1">
        <button
          type="button"
          className={cn(
            'mb-2 flex h-10 w-full items-center gap-3 px-0 text-slate-400 transition-colors hover:text-white',
            expanded ? 'justify-start px-4' : 'justify-center',
          )}
          onClick={onToggleExpanded}
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          title={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <PanelLeft className="h-5 w-5" />
          {expanded && <span className="truncate text-xs font-semibold uppercase tracking-wide">Menu</span>}
        </button>
        <ActivityButton
          label="Console"
          active={activeView === 'console'}
          expanded={expanded}
          onClick={() => { onViewChange('console') }}
        >
          <TerminalSquare className="h-6 w-6" />
        </ActivityButton>
        <ActivityButton
          label="Reporter"
          active={activeView === 'reporter'}
          expanded={expanded}
          onClick={() => { onViewChange('reporter') }}
          badge={hasReport}
        >
          <BarChart3 className="h-6 w-6" />
        </ActivityButton>
      </div>
    </aside>
  )
}

interface ActivityButtonProps {
  label: string
  active: boolean
  expanded: boolean
  badge?: boolean
  onClick: () => void
  children: ReactNode
}

function ActivityButton({ label, active, expanded, badge, onClick, children }: ActivityButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        'relative flex h-12 w-full items-center gap-3 border-l-2 text-slate-400 transition-colors hover:text-white',
        expanded ? 'justify-start px-4' : 'justify-center px-0',
        active ? 'border-l-white bg-[#252526] text-white' : 'border-l-transparent',
      )}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      {children}
      {expanded && <span className="min-w-0 truncate text-sm font-medium">{label}</span>}
      {badge && (
        <span className={cn(
          'absolute h-2 w-2 rounded-full bg-emerald-400',
          expanded ? 'right-3 top-1/2 -translate-y-1/2' : 'right-2 top-2',
        )}
        />
      )}
    </button>
  )
}

interface ReporterPageProps {
  report: RunSummary | null
  activeProvider: string
  onProviderChange: (provider: string) => void
  onViewTrace: (result: TestCaseResult) => void
  onClearReport: () => void
  reporterHome: ReactNode | null
}

function ReporterPage({
  report,
  activeProvider,
  onProviderChange,
  onViewTrace,
  onClearReport,
  reporterHome,
}: ReporterPageProps) {
  if (!report) {
    return (
      <div className="h-full overflow-y-auto bg-[#F8F9FB]">
        <div className="mx-auto max-w-[1040px] p-4 md:p-6">
          {reporterHome}
        </div>
      </div>
    )
  }

  const activeProviderData: ProviderSummary | null =
    activeProvider === '__overview__'
      ? null
      : report.providers.find((p) => p.provider === activeProvider) ?? null

  return (
    <div className="h-full overflow-y-auto bg-[#F8F9FB]">
      <div className="mx-auto max-w-[1440px] space-y-6 p-4 md:p-6">
        <Header report={report} onBackHome={onClearReport} />

        <SummaryCards report={report} />

        <ProviderTabs
          providers={report.providers}
          activeProvider={activeProvider}
          onProviderChange={onProviderChange}
        />

        {activeProviderData && <ParamCoverage provider={activeProviderData} />}

        {activeProvider === '__overview__' && (
          <div className="space-y-6">
            {report.providers.map((provider) => {
              const isAgent = isAgentProvider(provider.provider)
              return (
                <div key={provider.provider} className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-lg font-semibold text-slate-900">
                      {formatProviderName(provider.provider)}
                    </h3>
                    {isAgent && (
                      <Badge className="bg-gradient-to-r from-amber-400 to-orange-400 text-xs text-white">
                        <Bot className="mr-1 h-3 w-3" />
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
                  {provider.setupDetail && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      {provider.setupDetail}
                    </div>
                  )}
                  <TestCaseGrid
                    cases={provider.caseResults}
                    onViewTrace={onViewTrace}
                  />
                </div>
              )
            })}
          </div>
        )}

        {activeProviderData && (
          <div className="space-y-3">
            {activeProviderData.setupDetail && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {activeProviderData.setupDetail}
              </div>
            )}
            <TestCaseGrid
              cases={activeProviderData.caseResults}
              onViewTrace={onViewTrace}
            />
          </div>
        )}
      </div>
    </div>
  )
}

interface StatusBarProps {
  status: PlatformConsoleStatus
  activeView: AppView
  hasReport: boolean
  siteControls: ReactNode | null
}

function StatusBar({ status, activeView, hasReport, siteControls }: StatusBarProps) {
  const hasFailure = status.hasRunProgress && status.failed > 0
  const statusTone = status.error
    ? 'bg-[#c42b1c]'
    : status.running
      ? 'bg-[#007acc]'
      : hasFailure
        ? 'bg-[#c42b1c]'
        : 'bg-[#16825d]'
  const StatusIcon = status.error || hasFailure ? AlertCircle : CheckCircle2
  const progressWidth = `${status.hasRunProgress ? status.percent : 0}%`

  return (
    <footer className="flex h-8 w-full items-center overflow-hidden bg-[#007acc] text-xs text-white">
      <div
        className={cn('flex h-full w-8 shrink-0 items-center justify-center', statusTone)}
        title={status.error ? status.error : status.statusText}
      >
        <StatusIcon className="h-3.5 w-3.5" />
      </div>

      {siteControls && (
        <div className="flex h-full shrink-0 items-center border-l border-white/20">
          {siteControls}
        </div>
      )}

      <div className="flex min-w-0 flex-1 items-center gap-3 px-3">
        <span className="min-w-0 truncate font-medium">
          {status.error ?? status.statusText}
        </span>
        <div className="hidden h-1.5 w-32 shrink-0 overflow-hidden rounded-sm bg-white/25 md:block">
          <div
            className="h-full bg-white transition-[width] duration-300 ease-out"
            style={{ width: progressWidth }}
          />
        </div>
        <span className="hidden min-w-0 truncate text-white/85 md:inline">
          {status.detailText}
        </span>
        {status.hasRunProgress && (
          <span className="hidden shrink-0 text-white/85 lg:inline">
            {status.passed} passed / {status.failed} failed / {status.skipped} skipped
          </span>
        )}
      </div>

      <div className="hidden h-full shrink-0 items-center border-l border-white/20 px-3 text-white/90 md:flex">
        {activeView === 'console' ? <TerminalSquare className="mr-1.5 h-3.5 w-3.5" /> : <BarChart3 className="mr-1.5 h-3.5 w-3.5" />}
        {activeView === 'console' ? 'Console' : hasReport ? 'Reporter' : 'Reporter: empty'}
      </div>
      <div className="hidden h-full shrink-0 items-center border-l border-white/20 px-3 text-white/90 lg:flex">
        {status.enabledTargets} target{status.enabledTargets === 1 ? '' : 's'}
      </div>
      <div className="hidden h-full shrink-0 items-center border-l border-white/20 px-3 text-white/90 xl:flex">
        {status.requiresBackend ? <Server className="mr-1.5 h-3.5 w-3.5" /> : <Wifi className="mr-1.5 h-3.5 w-3.5" />}
        {status.executionSummary}
      </div>
      {status.activeBackendJobId && (
        <div className="hidden h-full max-w-56 shrink-0 items-center truncate border-l border-white/20 px-3 text-white/90 xl:flex">
          <Server className="mr-1.5 h-3.5 w-3.5 shrink-0" />
          <span className="truncate">Job {status.activeBackendJobId}</span>
        </div>
      )}
      {status.backendStatus && (
        <div className="hidden h-full max-w-64 shrink-0 items-center truncate border-l border-white/20 px-3 text-white/90 2xl:flex">
          <span className="truncate">{status.backendStatus}</span>
        </div>
      )}
    </footer>
  )
}
