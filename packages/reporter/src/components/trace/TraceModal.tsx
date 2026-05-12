import { useState, lazy, Suspense, useMemo, useCallback } from 'react'
import { motion } from 'motion/react'
import { X, ListTree, Play, RefreshCw, Maximize2, Minimize2 } from 'lucide-react'
import { StatusBadge } from '@/components/test-cases/StatusBadge'
import { StatusIcon } from '@/components/test-cases/StatusIcon'
import type { TestCaseResult } from '@/types'

const Editor = lazy(() => import('@monaco-editor/react'))

interface EditableExchange {
  method: string
  url: string
  headers: string
  body: string
  originalResponse?: string
}

interface TraceModalProps {
  result: TestCaseResult
  onClose: () => void
}

export function TraceModal({ result, onClose }: TraceModalProps) {
  const trace = result.httpTrace
  const hasTrace = trace && trace.exchanges.length > 0
  const resultSummary = useMemo(() => formatResultSummary(result), [result])
  const traceStatus = useMemo(() => formatTraceStatus(trace), [trace])

  const [activeIndex, setActiveIndex] = useState(0)
  const [activeReqTab, setActiveReqTab] = useState<'body' | 'headers'>('body')
  const [isSending, setIsSending] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Deep-copy exchanges into editable state
  const [exchanges, setExchanges] = useState<EditableExchange[]>(() => {
    if (!hasTrace) return []
    return trace.exchanges.map((ex) => ({
      method: ex.request.method,
      url: ex.request.url,
      headers: tryFormatJson(JSON.stringify(ex.request.headers)),
      body: tryFormatJson(ex.request.body),
      originalResponse: ex.response
        ? ex.response.kind === 'error'
          ? ex.response.error ?? undefined
          : tryFormatJson(ex.response.body)
        : undefined,
    }))
  })

  // Responses from re-sent requests (per exchange index)
  const [sentResponses, setSentResponses] = useState<(string | null)[]>(
    () => exchanges.map(() => null),
  )

  const active = exchanges[activeIndex]

  const updateExchange = useCallback((index: number, updates: Partial<EditableExchange>) => {
    setExchanges((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], ...updates }
      return next
    })
  }, [])

  const handleSend = useCallback(async () => {
    if (!active) return
    setIsSending(true)
    const startTime = performance.now()

    // Clear previous sent response for this index, show loading
    setSentResponses((prev) => {
      const next = [...prev]
      next[activeIndex] = '// Sending request...'
      return next
    })

    try {
      let headersObj: Record<string, string> = {}
      try {
        headersObj = JSON.parse(active.headers)
      } catch {
        throw new Error('Invalid JSON in Headers')
      }

      const res = await fetch(active.url, {
        method: active.method,
        headers: headersObj,
        body: ['GET', 'HEAD'].includes(active.method) ? undefined : active.body,
      })

      const text = await res.text()
      const formatted = tryFormatJson(text)
      const durationMs = Math.round(performance.now() - startTime)

      const statusLabel = `// Status: ${res.status} ${res.statusText}\n// Duration: ${durationMs}ms\n\n`

      setSentResponses((prev) => {
        const next = [...prev]
        next[activeIndex] = statusLabel + formatted
        return next
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setSentResponses((prev) => {
        const next = [...prev]
        next[activeIndex] = `Error: ${message}\n\n(Note: This might be a CORS issue or network failure if calling external APIs directly from the browser.)`
        return next
      })
    } finally {
      setIsSending(false)
    }
  }, [active, activeIndex])

  const readOnlyOptions = useMemo(() => ({
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: 'JetBrains Mono, monospace',
    padding: { top: 16 },
    scrollBeyondLastLine: false,
    wordWrap: 'on' as const,
    readOnly: true,
  }), [])

  const editableOptions = useMemo(() => ({
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: 'JetBrains Mono, monospace',
    padding: { top: 16 },
    scrollBeyondLastLine: false,
    wordWrap: 'on' as const,
    readOnly: false,
  }), [])

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm ${isFullscreen ? '' : 'p-4'}`}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className={`bg-white rounded-2xl shadow-2xl w-full ${isFullscreen ? 'max-w-full h-full rounded-none' : 'max-w-6xl h-[85vh]'} flex flex-col overflow-hidden border border-slate-200 transition-all`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-4">
            <div className="p-2.5 bg-white border border-slate-200 shadow-sm rounded-xl">
              <StatusIcon status={result.status} className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-slate-900">{result.id}</h2>
                <StatusBadge status={result.status} />
              </div>
              <div className="text-xs text-slate-500 mt-0.5">HTTP Request Sequence Debugger</div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
            >
              {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        {hasTrace && active ? (
          <div className="flex-1 overflow-hidden flex bg-slate-100">
            {/* Left Sidebar */}
            {exchanges.length > 1 && (
              <div className="w-64 bg-white border-r border-slate-200 flex flex-col overflow-y-auto shrink-0">
                <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
                  <ListTree className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Requests</span>
                </div>
                <div className="flex flex-col p-2 gap-1">
                  {exchanges.map((ex, idx) => (
                    <button
                      key={idx}
                      onClick={() => setActiveIndex(idx)}
                      className={`text-left px-3 py-2.5 rounded-lg transition-colors flex flex-col gap-1 ${
                        activeIndex === idx
                          ? 'bg-blue-50 border border-blue-200 shadow-sm'
                          : 'hover:bg-slate-100 border border-transparent'
                      }`}
                    >
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 self-start ${
                        ex.method === 'GET' ? 'bg-emerald-100 text-emerald-700' :
                        ex.method === 'HEAD' ? 'bg-teal-100 text-teal-700' :
                        ex.method === 'POST' ? 'bg-blue-100 text-blue-700' :
                        ex.method === 'PUT' ? 'bg-amber-100 text-amber-700' :
                        'bg-rose-100 text-rose-700'
                      }`}>{ex.method}</span>
                      <span className={`text-xs font-mono truncate w-full ${activeIndex === idx ? 'text-blue-900' : 'text-slate-500'}`} title={ex.url}>
                        {ex.url}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Right Content */}
            <div className="flex-1 overflow-hidden flex flex-col">
              {/* URL Bar — editable + Send button */}
              <div className="p-4 border-b border-slate-200 bg-white flex flex-col sm:flex-row gap-3">
                <div className="flex flex-1 gap-2">
                  <select
                    value={active.method}
                    onChange={(e) => {
                      const newMethod = e.target.value
                      updateExchange(activeIndex, { method: newMethod })
                      if (['GET', 'HEAD'].includes(newMethod)) {
                        setActiveReqTab('headers')
                      }
                    }}
                    className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow shrink-0"
                  >
                    <option>GET</option>
                    <option>HEAD</option>
                    <option>POST</option>
                    <option>PUT</option>
                    <option>DELETE</option>
                    <option>PATCH</option>
                  </select>
                  <input
                    type="text"
                    value={active.url}
                    onChange={(e) => updateExchange(activeIndex, { url: e.target.value })}
                    className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
                    placeholder="https://api.example.com/v1/..."
                  />
                </div>
                <button
                  onClick={handleSend}
                  disabled={isSending}
                  className="flex items-center justify-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 shadow-sm"
                >
                  {isSending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                  Send Request
                </button>
              </div>

              {/* Editors Split View */}
              <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-px bg-slate-200 overflow-hidden">
                {/* Request Side — editable */}
                <div className="flex flex-col bg-white overflow-hidden">
                  <div className="flex items-center gap-6 px-4 pt-2 border-b border-slate-200 bg-slate-50 text-sm font-medium text-slate-600">
                    {!['GET', 'HEAD'].includes(active.method) && (
                      <button
                        className={`pb-2.5 border-b-2 transition-colors ${activeReqTab === 'body' ? 'border-blue-500 text-blue-700' : 'border-transparent hover:text-slate-900'}`}
                        onClick={() => setActiveReqTab('body')}
                      >
                        Request Body
                      </button>
                    )}
                    <button
                      className={`pb-2.5 border-b-2 transition-colors ${activeReqTab === 'headers' ? 'border-blue-500 text-blue-700' : 'border-transparent hover:text-slate-900'}`}
                      onClick={() => setActiveReqTab('headers')}
                    >
                      Headers
                    </button>
                  </div>
                  <div className="flex-1 relative">
                    <Suspense fallback={<div className="flex items-center justify-center h-full text-sm text-slate-400">Loading editor...</div>}>
                      <Editor
                        height="100%"
                        defaultLanguage="json"
                        value={activeReqTab === 'body' ? active.body : active.headers}
                        theme="light"
                        options={editableOptions}
                        onChange={(val) => {
                          if (activeReqTab === 'body') {
                            updateExchange(activeIndex, { body: val ?? '' })
                          } else {
                            updateExchange(activeIndex, { headers: val ?? '' })
                          }
                        }}
                      />
                    </Suspense>
                  </div>
                </div>

                {/* Response Side */}
                <div className="flex flex-col bg-white overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 bg-slate-50 text-sm font-medium text-slate-600">
                    <span className="text-slate-700">Response</span>
                    {sentResponses[activeIndex] !== null && (
                      <span className="px-2.5 py-0.5 rounded-md text-xs font-mono font-semibold bg-blue-100 text-blue-700">
                        Re-sent
                      </span>
                    )}
                  </div>
                  <div className="flex-1 relative">
                    <Suspense fallback={<div className="flex items-center justify-center h-full text-sm text-slate-400">Loading editor...</div>}>
                      <Editor
                        height="100%"
                        defaultLanguage="json"
                        value={
                          sentResponses[activeIndex]
                            ?? active.originalResponse
                            ?? '// Click "Send Request" to execute'
                        }
                        theme="light"
                        options={readOnlyOptions}
                      />
                    </Suspense>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* No trace — show test result summary instead of request/response editors */
          <div className="flex-1 overflow-hidden flex bg-slate-100">
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-slate-200 bg-white">
                <div className="text-sm font-semibold text-slate-900">No HTTP trace available</div>
                <div className="mt-1 text-xs text-slate-500">
                  This case only contains summarized execution output, so request replay is disabled.
                </div>
              </div>

              <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-px bg-slate-200 overflow-hidden">
                <div className="flex flex-col bg-white overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 text-sm font-medium text-slate-700">
                    Test Result
                  </div>
                  <div className="flex-1 relative">
                    <Suspense fallback={<div className="flex items-center justify-center h-full text-sm text-slate-400">Loading...</div>}>
                      <Editor
                        height="100%"
                        defaultLanguage="json"
                        value={resultSummary}
                        theme="light"
                        options={readOnlyOptions}
                      />
                    </Suspense>
                  </div>
                </div>
                <div className="flex flex-col bg-white overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 text-sm font-medium text-slate-700">
                    Trace Status
                  </div>
                  <div className="flex-1 relative">
                    <Suspense fallback={<div className="flex items-center justify-center h-full text-sm text-slate-400">Loading...</div>}>
                      <Editor
                        height="100%"
                        defaultLanguage="json"
                        value={traceStatus}
                        theme="light"
                        options={readOnlyOptions}
                      />
                    </Suspense>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  )
}

function tryFormatJson(text: string | undefined): string {
  if (!text) return ''
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

function formatResultSummary(result: TestCaseResult): string {
  return JSON.stringify({
    id: result.id,
    description: result.description,
    status: result.status,
    durationMs: result.durationMs,
    apiType: result.apiType,
    coveredParams: result.coveredParams,
    ...(result.detail ? { detail: result.detail } : {}),
    ...(result.error ? { error: result.error } : {}),
  }, null, 2)
}

function formatTraceStatus(trace: TestCaseResult['httpTrace']): string {
  if (!trace) {
    return JSON.stringify({
      available: false,
      message: 'HTTP trace was not captured for this test case.',
    }, null, 2)
  }

  return JSON.stringify({
    available: trace.exchanges.length > 0,
    source: trace.source,
    testId: trace.testId,
    exchangeCount: trace.exchangeCount,
    message: trace.exchanges.length > 0
      ? 'HTTP trace is available.'
      : 'Trace metadata exists, but no matching request/response exchange was captured.',
  }, null, 2)
}
