import { useCallback, useEffect, useRef, useState } from 'react'
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
type ConsoleLogLevel = 'log' | 'info' | 'warn' | 'error'

interface ConsoleLogEntry {
  id: number
  time: string
  level: ConsoleLogLevel
  message: string
}

interface IncomingConsoleLog {
  level: ConsoleLogLevel
  time?: string
  message: string
}

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
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [consoleLogs, setConsoleLogs] = useState<ConsoleLogEntry[]>([])
  const nextConsoleLogId = useRef(1)

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

  const appendConsoleLogs = useCallback((entries: IncomingConsoleLog[]) => {
    if (entries.length === 0) {
      return
    }
    const nextEntries = entries.map((entry) => {
      const id = nextConsoleLogId.current
      nextConsoleLogId.current += 1
      return {
        id,
        level: entry.level,
        time: formatLogTime(entry.time),
        message: entry.message,
      }
    })
    setConsoleLogs((current) => [...current, ...nextEntries].slice(-300))
  }, [])

  const handleClearConsole = useCallback(() => {
    setConsoleLogs([])
  }, [])

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
              onConsoleLogs={appendConsoleLogs}
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
        siteControls={siteControls}
        consoleLogs={consoleLogs}
        consoleOpen={consoleOpen}
        onToggleConsole={() => { setConsoleOpen((current) => !current) }}
        onCloseConsole={() => { setConsoleOpen(false) }}
        onClearConsole={handleClearConsole}
      />

      {traceCase && (
        <TraceModal result={traceCase} onClose={() => { setTraceCase(null) }} />
      )}
    </div>
  )
}

function formatLogTime(value?: string): string {
  const date = value ? new Date(value) : new Date()
  if (Number.isNaN(date.getTime())) {
    return value ?? ''
  }
  return date.toLocaleTimeString([], { hour12: false })
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
  siteControls: ReactNode | null
  consoleLogs: ConsoleLogEntry[]
  consoleOpen: boolean
  onToggleConsole: () => void
  onCloseConsole: () => void
  onClearConsole: () => void
}

function StatusBar({
  status,
  siteControls,
  consoleLogs,
  consoleOpen,
  onToggleConsole,
  onCloseConsole,
  onClearConsole,
}: StatusBarProps) {
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
    <>
      {consoleOpen && (
        <ConsoleLogPanel
          logs={consoleLogs}
          onClose={onCloseConsole}
          onClear={onClearConsole}
        />
      )}
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

      <button
        type="button"
        className="flex h-full shrink-0 items-center border-l border-white/20 px-2 text-white/90 transition-colors hover:bg-white/10 hover:text-white sm:px-3"
        onClick={onToggleConsole}
        aria-expanded={consoleOpen}
        aria-label="Toggle console logs"
      >
        <TerminalSquare className="mr-1.5 h-3.5 w-3.5" />
        <span className="hidden sm:inline">Console</span>
        {consoleLogs.length > 0 && (
          <span className="ml-1.5 rounded-sm bg-white/20 px-1 text-[10px] leading-4 text-white">
            {consoleLogs.length}
          </span>
        )}
      </button>
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
    </>
  )
}

interface ConsoleLogPanelProps {
  logs: ConsoleLogEntry[]
  onClose: () => void
  onClear: () => void
}

function ConsoleLogPanel({ logs, onClose, onClear }: ConsoleLogPanelProps) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [logs])

  return (
    <div className="fixed bottom-10 right-3 z-50 flex h-[min(24rem,calc(100vh-5rem))] w-[min(48rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-lg border border-slate-700 bg-[#111827] text-slate-100 shadow-2xl">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-slate-700 bg-[#0f172a] px-3">
        <div className="flex min-w-0 items-center gap-2">
          <TerminalSquare className="h-4 w-4 shrink-0 text-sky-300" />
          <span className="truncate text-sm font-semibold">Console</span>
          <span className="rounded-sm bg-slate-700 px-1.5 py-0.5 text-[10px] text-slate-300">
            {logs.length} lines
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="rounded px-2 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
            onClick={onClear}
          >
            Clear
          </button>
          <button
            type="button"
            className="rounded px-2 py-1 text-xs text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2 font-mono text-xs leading-5">
        {logs.length === 0 ? (
          <div className="py-6 text-center text-slate-500">No logs</div>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="grid grid-cols-[4.75rem_4.25rem_minmax(0,1fr)] gap-2 border-b border-slate-800/70 py-1 last:border-b-0">
              <span className="text-slate-500">{log.time}</span>
              <span className={cn(
                'uppercase',
                log.level === 'error' && 'text-rose-300',
                log.level === 'warn' && 'text-amber-300',
                log.level === 'info' && 'text-sky-300',
                log.level === 'log' && 'text-slate-300',
              )}
              >
                {log.level}
              </span>
              <span className="min-w-0 break-words text-slate-200">{log.message}</span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
