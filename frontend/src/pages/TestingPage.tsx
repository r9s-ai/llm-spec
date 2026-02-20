import { useMemo, useCallback } from "react";
import { TestSelector, ActiveRunCard, CompletedRunCard } from "../components";
import { useAppContext } from "../context";
import type { RunSummary } from "../types";

export function TestingPage() {
  const { runMode, setRunMode, setNotice, suites, runs } = useAppContext();
  const {
    providers,
    suites: suiteList,
    versionsBySuite,
    selectedVersionBySuite,
    selectedTestsBySuite,
    expandedProviders,
    expandedSuites,
    selectedTestCount,
    toggleProvider,
    toggleProviderPanel,
    toggleSuitePanel,
    toggleTest,
    selectAllProviders,
    clearAllProviders,
  } = suites;

  const { runEventsById, runResultById, startBatchRun, runs: runList } = runs;

  // Check if any run is currently active
  const isRunning = useMemo(
    () => runList.some((run) => run.status === "running" || run.status === "pending"),
    [runList]
  );

  // Separate active and completed runs
  const { activeRuns, completedRuns } = useMemo(() => {
    const active: typeof runList = [];
    const completed: typeof runList = [];
    runList.forEach((run) => {
      if (run.status === "running" || run.status === "pending") {
        active.push(run);
      } else {
        completed.push(run);
      }
    });
    return { activeRuns: active, completedRuns: completed };
  }, [runList]);

  // Handle batch run
  const handleStartBatchRun = useCallback(async () => {
    const selectedSuiteIds = new Set<string>();
    suiteList.forEach((suite) => {
      const tests = selectedTestsBySuite[suite.id];
      if (tests && tests.size > 0) {
        selectedSuiteIds.add(suite.id);
      }
    });

    await startBatchRun(
      selectedSuiteIds,
      selectedVersionBySuite,
      selectedTestsBySuite,
      runMode,
      setNotice
    );
  }, [suiteList, selectedTestsBySuite, selectedVersionBySuite, runMode, startBatchRun, setNotice]);

  // Toggle tests for a suite
  const handleToggleTests = useCallback(
    (suiteId: string, testNames: string[], checked: boolean) => {
      testNames.forEach((testName) => {
        toggleTest(suiteId, testName, checked);
      });
    },
    [toggleTest]
  );

  // Select all tests
  const handleSelectAll = useCallback(() => {
    selectAllProviders();
    suiteList.forEach((suite) => {
      const versions = versionsBySuite[suite.id] ?? [];
      const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
      if (versionId) {
        // Get tests from version and select all
        const version = versions.find((v) => v.id === versionId);
        if (version?.parsed_json?.tests) {
          const tests = version.parsed_json.tests as Array<{ name: string }>;
          tests.forEach((test) => {
            toggleTest(suite.id, test.name, true);
          });
        }
      }
    });
  }, [selectAllProviders, suiteList, versionsBySuite, selectedVersionBySuite, toggleTest]);

  // Clear all selections
  const handleClearAll = useCallback(() => {
    clearAllProviders();
    suites.setSelectedTestsBySuite({});
  }, [clearAllProviders, suites]);

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Left Panel - Test Selector (with Run controls) */}
      <div className="w-[400px] flex-shrink-0 border-r border-slate-200 bg-slate-50">
        <div className="h-full overflow-auto p-4">
          <TestSelector
            providers={providers}
            suites={suiteList}
            versionsBySuite={versionsBySuite}
            selectedVersionBySuite={selectedVersionBySuite}
            selectedTestsBySuite={selectedTestsBySuite}
            expandedProviders={expandedProviders}
            expandedSuites={expandedSuites}
            selectedTestCount={selectedTestCount}
            runMode={runMode}
            isRunning={isRunning}
            onToggleProvider={toggleProvider}
            onToggleProviderExpanded={toggleProviderPanel}
            onToggleSuiteExpanded={toggleSuitePanel}
            onToggleTests={handleToggleTests}
            onToggleTest={toggleTest}
            onSelectAll={handleSelectAll}
            onClearAll={handleClearAll}
            onRunModeChange={setRunMode}
            onRun={() => void handleStartBatchRun()}
          />
        </div>
      </div>

      {/* Right Panel - Runs */}
      <div className="flex-1 overflow-auto bg-slate-50">
        <div className="p-4">
          {/* Active Runs */}
          {activeRuns.length > 0 && (
            <section className="mb-4">
              <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
                Active Runs
                <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-700">
                  {activeRuns.length}
                </span>
              </h3>
              <div className="border-l-2 border-violet-400 bg-white rounded-r-lg">
                {activeRuns.map((run) => (
                  <ActiveRunCard key={run.id} run={run} events={runEventsById[run.id] ?? []} />
                ))}
              </div>
            </section>
          )}

          {/* Completed Runs */}
          <section>
            <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-500">
              Completed Runs
              {completedRuns.length > 0 && (
                <span className="ml-2 rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
                  {completedRuns.length}
                </span>
              )}
            </h3>

            {completedRuns.length === 0 && activeRuns.length === 0 && (
              <div className="border-l-2 border-slate-300 bg-white rounded-r-lg p-8 text-center">
                <p className="text-sm text-slate-500">
                  No runs yet. Select tests and click Run to start.
                </p>
              </div>
            )}

            {completedRuns.length === 0 && activeRuns.length > 0 && (
              <div className="border-l-2 border-slate-300 bg-white rounded-r-lg p-6 text-center">
                <p className="text-sm text-slate-400">Waiting for active runs to complete...</p>
              </div>
            )}

            {completedRuns.length > 0 && (
              <div className="border-l-2 border-slate-300 bg-white rounded-r-lg">
                {completedRuns.map((run) => {
                  const summary = runResultById[run.id]?.summary as RunSummary | undefined;
                  const result = runResultById[run.id];
                  return (
                    <CompletedRunCard key={run.id} run={run} summary={summary} result={result} />
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
