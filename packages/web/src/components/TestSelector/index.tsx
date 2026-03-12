import { useState, useMemo, useCallback } from "react";
import { SearchInput } from "./SearchInput";
import { ModelNode } from "./ModelNode";
import type { Suite, TestSelectionMap, RunMode } from "../../types";
import { getTestRows } from "../../utils";

interface TestSelectorProps {
  providers: string[];
  suites: Suite[];
  selectedTestsBySuite: TestSelectionMap;
  selectedProviders: Set<string>;
  expandedSuites: Set<string>;
  selectedTestCount: number;
  runMode: RunMode;
  maxConcurrent: number;
  isRunning: boolean;
  isLoading: boolean;
  isRefreshingCache: boolean;
  onToggleSuiteExpanded: (suiteId: string) => void;
  onToggleTests: (suiteId: string, testNames: string[], checked: boolean) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onSelectProvider: (providerId: string) => void;
  onRunModeChange: (mode: RunMode) => void;
  onMaxConcurrentChange: (max: number) => void;
  onRefreshCache: () => void;
  onRun: () => void;
}

export function TestSelector({
  providers,
  suites,
  selectedTestsBySuite,
  expandedSuites,
  selectedTestCount,
  runMode,
  maxConcurrent,
  isRunning,
  isLoading,
  isRefreshingCache,
  onToggleSuiteExpanded,
  onToggleTests,
  onToggleTest,
  onSelectAll,
  onClearAll,
  onSelectProvider,
  onRunModeChange,
  onMaxConcurrentChange,
  onRefreshCache,
  onRun,
}: TestSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedModelGroups, setExpandedModelGroups] = useState<Set<string>>(new Set<string>());

  const suitesByProviderModel = useMemo(() => {
    const grouped: Record<string, { key: string; provider: string; model: string; suites: Suite[] }> =
      {};
    suites.forEach((suite) => {
      const key = `${suite.provider_id}:${suite.model_id}`;
      if (!grouped[key]) {
        grouped[key] = { key, provider: suite.provider_id, model: suite.model_id, suites: [] };
      }
      grouped[key].suites.push(suite);
    });
    return grouped;
  }, [suites]);

  const { modelCount } = useMemo(() => {
    const routeSet = new Set<string>();
    const modelSet = new Set<string>();
    suites.forEach((suite) => {
      routeSet.add(`${suite.provider_id}:${suite.route_id}`);
      modelSet.add(`${suite.provider_id}:${suite.model_id}`);
    });
    return { routeCount: routeSet.size, modelCount: modelSet.size };
  }, [suites]);
  const totalTestCount = useMemo(
    () => suites.reduce((sum, suite) => sum + getTestRows(suite).length, 0),
    [suites]
  );
  const isAllSelected = totalTestCount > 0 && selectedTestCount === totalTestCount;
  const providerSelectedCounts = useMemo(() => {
    const counts = new Map<string, number>();
    suites.forEach((suite) => {
      const bucket = selectedTestsBySuite[suite.suite_id];
      if (!bucket || bucket.size === 0) return;
      counts.set(suite.provider_id, (counts.get(suite.provider_id) ?? 0) + bucket.size);
    });
    return counts;
  }, [suites, selectedTestsBySuite]);

  const filteredGroups = useMemo(() => {
    const groups = Object.values(suitesByProviderModel);
    if (!searchQuery) return groups;
    const query = searchQuery.toLowerCase();

    return groups
      .map((group) => {
        if (
          group.provider.toLowerCase().includes(query) ||
          group.model.toLowerCase().includes(query)
        ) {
          return group;
        }

        const suitesMatching = group.suites.filter((suite) => {
          const tests = getTestRows(suite);
          const route = suite.route_id.toLowerCase();
          const endpoint = suite.endpoint.toLowerCase();
          const suiteName = suite.suite_name.toLowerCase();
          return (
            route.includes(query) ||
            endpoint.includes(query) ||
            suiteName.includes(query) ||
            tests.some(
              (t) =>
                t.name.toLowerCase().includes(query) ||
                t.paramName.toLowerCase().includes(query) ||
                t.tags.some((tag) => tag.toLowerCase().includes(query))
            )
          );
        });

        if (suitesMatching.length === 0) return null;
        return { ...group, suites: suitesMatching };
      })
      .filter((group): group is { key: string; provider: string; model: string; suites: Suite[] } =>
        Boolean(group)
      );
  }, [suitesByProviderModel, searchQuery]);

  const sortedGroups = useMemo(
    () =>
      filteredGroups.slice().sort(
        (a, b) =>
          a.provider.localeCompare(b.provider) || a.model.localeCompare(b.model)
      ),
    [filteredGroups]
  );

  const groupKeys = useMemo(() => sortedGroups.map((group) => group.key), [sortedGroups]);

  const effectiveExpandedGroups = useMemo(() => {
    if (searchQuery) return new Set(groupKeys);
    return new Set(Array.from(expandedModelGroups).filter((key) => groupKeys.includes(key)));
  }, [expandedModelGroups, searchQuery, groupKeys]);

  const handleToggleGroupExpanded = useCallback(
    (groupKey: string) => {
      if (searchQuery) return;
      setExpandedModelGroups((prev) => {
        const next = new Set(prev);
        if (next.has(groupKey)) next.delete(groupKey);
        else next.add(groupKey);
        return next;
      });
    },
    [searchQuery]
  );

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
  }, []);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex-shrink-0 space-y-1 pb-2">
        <div className="flex items-center gap-2">
          {/* Block C: stacked A + B */}
          <div className="flex-1 space-y-1">
            {/* Block A: mode + concurrent */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-0.5 rounded-lg bg-slate-100 p-0.5 flex-1">
                <button
                  onClick={() => onRunModeChange("real")}
                  disabled={isRunning}
                  className={`flex flex-1 items-center justify-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
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
                  className={`flex flex-1 items-center justify-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                    runMode === "mock"
                      ? "bg-white text-slate-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  } ${isRunning ? "cursor-not-allowed opacity-50" : ""}`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                  Mock
                </button>
              </div>

              <div className="ml-auto flex items-center gap-1">
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
            </div>

            {/* Block B: stats */}
            <div className="text-center text-xs font-mono tracking-wide text-slate-600">
              <span className="inline-block min-w-[3ch] text-right font-semibold text-slate-900 tabular-nums">
                {modelCount}
              </span>{" "}
              models ·{" "}
              <span className="inline-block min-w-[3ch] text-right font-semibold text-slate-900 tabular-nums">
                {selectedTestCount}
              </span>{" "}
              selected
            </div>
          </div>

          {/* Block D: Run button */}
          <button
            onClick={onRun}
            disabled={selectedTestCount === 0 || isRunning}
            className={`flex items-center justify-center gap-2 rounded-lg px-3 text-sm font-bold transition-all h-12 w-32 ${
              selectedTestCount > 0 && !isRunning
                ? "bg-violet-600 text-white shadow-lg shadow-violet-200 hover:bg-violet-700 active:scale-[0.98]"
                : "cursor-not-allowed bg-slate-200 text-slate-400"
            }`}
          >
            Run
          </button>
        </div>

        {/* Row 3: Search + Buttons (same height) */}
        <div className="flex items-center gap-1.5">
          <div className="flex-1">
            <SearchInput value={searchQuery} onChange={handleSearchChange} />
          </div>
          <button
            onClick={onRefreshCache}
            disabled={isRefreshingCache || isLoading}
            className={`h-8 w-8 rounded-lg border border-slate-200 text-xs font-medium flex items-center justify-center ${
              isRefreshingCache || isLoading
                ? "cursor-not-allowed text-slate-400"
                : "text-slate-600 hover:bg-slate-50"
            }`}
            title="Refresh Memory"
          >
            <svg
              className={`h-4 w-4 ${isRefreshingCache ? "animate-spin" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v6h6M20 20v-6h-6M5 19a9 9 0 0014-7M19 5a9 9 0 00-14 7"
              />
            </svg>
          </button>
          <button
            onClick={isAllSelected ? onClearAll : onSelectAll}
            className="h-8 rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {isAllSelected ? "Clear" : "All"}
          </button>
        </div>

        {/* Row 4: Provider buttons */}
        <div className="flex flex-wrap gap-1.5">
          {providers.map((provider) => {
            const isSelected = (providerSelectedCounts.get(provider) ?? 0) > 0;
            return (
              <button
                key={provider}
                onClick={() => onSelectProvider(provider)}
                className={`h-8 rounded-lg border px-2.5 text-xs font-medium transition-colors ${
                  isSelected
                    ? "border-violet-300 bg-violet-50 text-violet-700"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {provider}
              </button>
            );
          })}
        </div>
      </div>

      {/* Divider */}
      <div className="border-b border-slate-200" />

      {/* Provider List */}
      <div className="flex-1 overflow-auto pt-2 space-y-1.5">
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
          sortedGroups.map((group) => (
            <ModelNode
              key={group.key}
              model={`${group.provider}:${group.model}`}
              suites={group.suites}
              selectedTestsBySuite={selectedTestsBySuite}
              expandedSuites={expandedSuites}
              isExpanded={effectiveExpandedGroups.has(group.key)}
              searchQuery={searchQuery}
              onToggleExpanded={() => handleToggleGroupExpanded(group.key)}
              onToggleSuiteExpanded={onToggleSuiteExpanded}
              onToggleTests={onToggleTests}
              onToggleTest={onToggleTest}
            />
          ))}

        {!isLoading && sortedGroups.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">No suites available</div>
        )}
      </div>
    </div>
  );
}
