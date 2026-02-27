import { useState, useMemo, useCallback } from "react";
import { SearchInput } from "./SearchInput";
import { ProviderNode } from "./ProviderNode";
import type { Suite, TestSelectionMap, VersionsMap, RunMode } from "../../types";

interface TestSelectorProps {
  providers: string[];
  suites: Suite[];
  versionsBySuite: VersionsMap;
  selectedVersionBySuite: Record<string, string>;
  selectedTestsBySuite: TestSelectionMap;
  expandedProviders: Set<string>;
  expandedSuites: Set<string>;
  selectedTestCount: number;
  runMode: RunMode;
  maxConcurrent: number;
  isRunning: boolean;
  isLoading: boolean;
  isRefreshingCache: boolean;
  onToggleProvider: (provider: string) => void;
  onToggleProviderExpanded: (provider: string) => void;
  onToggleSuiteExpanded: (suiteId: string) => void;
  onToggleTests: (suiteId: string, testNames: string[], checked: boolean) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onRunModeChange: (mode: RunMode) => void;
  onMaxConcurrentChange: (max: number) => void;
  onRefreshCache: () => void;
  onRun: () => void;
}

export function TestSelector({
  providers,
  suites,
  versionsBySuite,
  selectedVersionBySuite,
  selectedTestsBySuite,
  expandedProviders,
  expandedSuites,
  selectedTestCount,
  runMode,
  maxConcurrent,
  isRunning,
  isLoading,
  isRefreshingCache,
  onToggleProviderExpanded,
  onToggleSuiteExpanded,
  onToggleTests,
  onToggleTest,
  onSelectAll,
  onClearAll,
  onRunModeChange,
  onMaxConcurrentChange,
  onRefreshCache,
  onRun,
}: TestSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");

  // Group suites by provider
  const suitesByProvider = useMemo(() => {
    const grouped: Record<string, Suite[]> = {};
    suites.forEach((suite) => {
      if (!grouped[suite.provider]) {
        grouped[suite.provider] = [];
      }
      grouped[suite.provider].push(suite);
    });
    return grouped;
  }, [suites]);

  const { routeCount, modelCount } = useMemo(() => {
    const routeSet = new Set<string>();
    const modelSet = new Set<string>();
    suites.forEach((suite) => {
      routeSet.add(`${suite.provider}:${suite.route}`);
      modelSet.add(`${suite.provider}:${suite.model}`);
    });
    return { routeCount: routeSet.size, modelCount: modelSet.size };
  }, [suites]);

  // Expand all when searching
  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchQuery(value);
      // Auto-expand all providers when searching
      if (value) {
        providers.forEach((provider) => {
          if (!expandedProviders.has(provider)) {
            onToggleProviderExpanded(provider);
          }
        });
      }
    },
    [providers, expandedProviders, onToggleProviderExpanded]
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex-shrink-0 space-y-2 pb-2">
        {/* Row 1: Run controls */}
        <div className="flex items-center gap-2">
          {/* Mode selector */}
          <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 p-0.5">
            <button
              onClick={() => onRunModeChange("real")}
              disabled={isRunning}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                runMode === "real"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              } ${isRunning ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
              Real
            </button>
            <button
              onClick={() => onRunModeChange("mock")}
              disabled={isRunning}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                runMode === "mock"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              } ${isRunning ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              Mock
            </button>
          </div>

          {/* Concurrent selector */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-slate-500">Concurrent:</span>
            <select
              value={maxConcurrent}
              onChange={(e) => onMaxConcurrentChange(Number(e.target.value))}
              disabled={isRunning}
              className={`h-7 rounded-md border border-slate-200 bg-white px-1.5 text-xs font-medium text-slate-700 ${
                isRunning ? "cursor-not-allowed opacity-50" : ""
              }`}
            >
              <option value={1}>1</option>
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>

          {/* Run button */}
          <button
            onClick={onRun}
            disabled={selectedTestCount === 0 || isRunning}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              selectedTestCount > 0 && !isRunning
                ? "bg-violet-600 text-white shadow-lg shadow-violet-200 hover:bg-violet-700 active:scale-[0.98]"
                : "cursor-not-allowed bg-slate-200 text-slate-400"
            }`}
          >
            {isRunning ? (
              <>
                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Running...
              </>
            ) : (
              <>
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Run {selectedTestCount}
              </>
            )}
          </button>
        </div>

        {/* Row 2: Stats - centered with bold numbers */}
        <div className="text-center text-xs text-slate-600">
          <span className="font-bold text-slate-900">{providers.length}</span> providers ·{" "}
          <span className="font-bold text-slate-900">{modelCount}</span> models ·{" "}
          <span className="font-bold text-slate-900">{routeCount}</span> routes ·{" "}
          <span className="font-bold text-slate-900">{selectedTestCount}</span> selected
        </div>

        {/* Row 3: Search + Buttons (same height) */}
        <div className="flex items-center gap-1.5">
          <div className="flex-1">
            <SearchInput value={searchQuery} onChange={handleSearchChange} />
          </div>
          <button
            onClick={onRefreshCache}
            disabled={isRefreshingCache || isLoading}
            className={`h-8 rounded-lg border border-slate-200 px-2.5 text-xs font-medium ${
              isRefreshingCache || isLoading
                ? "cursor-not-allowed text-slate-400"
                : "text-slate-600 hover:bg-slate-50"
            }`}
          >
            {isRefreshingCache ? "Refreshing..." : "Refresh Memory"}
          </button>
          <button
            onClick={onSelectAll}
            className="h-8 rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            All
          </button>
          <button
            onClick={onClearAll}
            className="h-8 rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Divider */}
      <div className="border-b border-slate-200" />

      {/* Provider List */}
      <div className="flex-1 overflow-auto pt-2">
        {isLoading && (
          <div className="space-y-2 px-1 py-2">
            {[0, 1, 2].map((idx) => (
              <div key={idx} className="animate-pulse rounded-lg border border-slate-200 bg-white p-3">
                <div className="mb-2 h-3 w-28 rounded bg-slate-200" />
                <div className="h-2.5 w-44 rounded bg-slate-100" />
              </div>
            ))}
          </div>
        )}

        {!isLoading &&
          providers.sort().map((provider) => {
            const providerSuites = suitesByProvider[provider] ?? [];
            if (searchQuery && providerSuites.length === 0) return null;

            return (
              <ProviderNode
                key={provider}
                provider={provider}
                suites={providerSuites}
                versionsBySuite={versionsBySuite}
                selectedVersionBySuite={selectedVersionBySuite}
                selectedTestsBySuite={selectedTestsBySuite}
                expandedSuites={expandedSuites}
                isExpanded={expandedProviders.has(provider)}
                searchQuery={searchQuery}
                onToggleExpanded={() => onToggleProviderExpanded(provider)}
                onToggleSuiteExpanded={onToggleSuiteExpanded}
                onToggleTests={onToggleTests}
                onToggleTest={onToggleTest}
              />
            );
          })}

        {!isLoading && providers.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">No suites available</div>
        )}
      </div>
    </div>
  );
}
