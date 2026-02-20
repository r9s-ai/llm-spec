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
  isRunning: boolean;
  onToggleProvider: (provider: string) => void;
  onToggleProviderExpanded: (provider: string) => void;
  onToggleSuiteExpanded: (suiteId: string) => void;
  onToggleTests: (suiteId: string, testNames: string[], checked: boolean) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onRunModeChange: (mode: RunMode) => void;
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
  isRunning,
  onToggleProviderExpanded,
  onToggleSuiteExpanded,
  onToggleTests,
  onToggleTest,
  onSelectAll,
  onClearAll,
  onRunModeChange,
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

  // Calculate route count
  const routeCount = suites.length;

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
      <div className="flex-shrink-0 space-y-3 pb-3">
        {/* Row 1: Run controls */}
        <div className="flex items-center gap-2">
          {/* Mode selector */}
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
            <button
              onClick={() => onRunModeChange("real")}
              disabled={isRunning}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                runMode === "real"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              } ${isRunning ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <span className="h-2 w-2 rounded-full bg-green-500" />
              Real
            </button>
            <button
              onClick={() => onRunModeChange("mock")}
              disabled={isRunning}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                runMode === "mock"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              } ${isRunning ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              Mock
            </button>
          </div>

          {/* Run button */}
          <button
            onClick={onRun}
            disabled={selectedTestCount === 0 || isRunning}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition-all ${
              selectedTestCount > 0 && !isRunning
                ? "bg-violet-600 text-white shadow-lg shadow-violet-200 hover:bg-violet-700 active:scale-[0.98]"
                : "cursor-not-allowed bg-slate-200 text-slate-400"
            }`}
          >
            {isRunning ? (
              <>
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                Run {selectedTestCount} test{selectedTestCount !== 1 ? "s" : ""}
              </>
            )}
          </button>
        </div>

        {/* Row 2: Stats - centered with bold numbers */}
        <div className="text-center text-sm text-slate-600">
          <span className="font-bold text-slate-900">{providers.length}</span> providers ·{" "}
          <span className="font-bold text-slate-900">{routeCount}</span> routes ·{" "}
          <span className="font-bold text-slate-900">{selectedTestCount}</span> tests selected
        </div>

        {/* Row 3: Search + Buttons (same height) */}
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <SearchInput value={searchQuery} onChange={handleSearchChange} />
          </div>
          <button
            onClick={onSelectAll}
            className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            All
          </button>
          <button
            onClick={onClearAll}
            className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Divider */}
      <div className="border-b border-slate-200" />

      {/* Provider List */}
      <div className="flex-1 overflow-auto pt-3">
        {providers.sort().map((provider) => {
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

        {providers.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">No suites available</div>
        )}
      </div>
    </div>
  );
}
