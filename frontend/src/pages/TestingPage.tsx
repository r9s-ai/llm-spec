import { useMemo, useCallback, useEffect } from "react";
import { TestSelector, TaskCard } from "../components";
import { useAppContext } from "../context";

export function TestingPage() {
  const { runMode, setRunMode, setNotice, suites, batches } = useAppContext();
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

  const {
    batches: batchList,
    runEventsById,
    runResultById,
    startBatchRun,
    loadHistory,
    deleteBatchFromServer,
    upsertBatch,
  } = batches;

  // Load history on mount
  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // Check if any batch is currently running
  const isRunning = useMemo(
    () => batchList.some((batch) => batch.status === "running"),
    [batchList]
  );

  // Separate active and completed batches
  const { activeBatches, completedBatches } = useMemo(() => {
    const active: typeof batchList = [];
    const completed: typeof batchList = [];
    batchList.forEach((batch) => {
      if (batch.status === "running") {
        active.push(batch);
      } else {
        completed.push(batch);
      }
    });
    return { activeBatches: active, completedBatches: completed };
  }, [batchList]);

  // Handle batch run
  const handleStartBatchRun = useCallback(async () => {
    // Collect selected suite version IDs
    const selectedSuiteVersionIds: string[] = [];
    suiteList.forEach((suite) => {
      const tests = selectedTestsBySuite[suite.id];
      if (tests && tests.size > 0) {
        const versionId = selectedVersionBySuite[suite.id];
        if (versionId) {
          selectedSuiteVersionIds.push(versionId);
        }
      }
    });

    await startBatchRun(selectedSuiteVersionIds, runMode, selectedTestsBySuite, setNotice);
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

  // Handle delete batch
  const handleDeleteBatch = useCallback(
    async (batchId: string) => {
      await deleteBatchFromServer(batchId);
    },
    [deleteBatchFromServer]
  );

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

      {/* Right Panel - Task Cards */}
      <div className="flex-1 overflow-auto bg-slate-50">
        <div className="p-4 space-y-4">
          {/* Empty State */}
          {batchList.length === 0 && (
            <div className="border border-slate-200 rounded-lg bg-white p-8 text-center">
              <p className="text-sm text-slate-500">
                No tasks yet. Select routes and click Run to start.
              </p>
            </div>
          )}

          {/* Active Batches */}
          {activeBatches.map((batch) => (
            <TaskCard
              key={batch.id}
              batch={batch}
              eventsByRunId={runEventsById}
              resultsByRunId={runResultById}
              onDelete={handleDeleteBatch}
              onUpdate={upsertBatch}
            />
          ))}

          {/* Completed Batches */}
          {completedBatches.map((batch) => (
            <TaskCard
              key={batch.id}
              batch={batch}
              eventsByRunId={runEventsById}
              resultsByRunId={runResultById}
              onDelete={handleDeleteBatch}
              onUpdate={upsertBatch}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
