import { useMemo, useCallback, useEffect, useState } from "react";
import { TestSelector, TaskCard } from "../components";
import { useAppContext } from "../context";
import type { RunJob } from "../types";

export function TestingPage() {
  const { runMode, setRunMode, setNotice, suites, tasks } = useAppContext();
  const [maxConcurrent, setMaxConcurrent] = useState(5);
  const {
    providers,
    suites: suiteList,
    selectedTestsBySuite,
    expandedProviders,
    expandedSuites,
    selectedTestCount,
    isLoading,
    isRefreshingRegistryCache,
    refreshRegistryCache,
    toggleProvider,
    toggleProviderPanel,
    toggleSuitePanel,
    toggleTest,
    selectAllProviders,
    clearAllProviders,
  } = suites;

  const {
    tasks: taskList,
    runEventsById,
    runResultById,
    startTaskRun,
    loadHistory,
    deleteTaskFromServer,
    upsertTask,
  } = tasks;

  // Load history on mount
  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // Check if any task is currently running
  const isRunning = useMemo(
    () => taskList.some((task) => task.status === "running"),
    [taskList]
  );

  // Separate active and completed tasks
  const { activeTasks, completedTasks } = useMemo(() => {
    const active: typeof taskList = [];
    const completed: typeof taskList = [];
    taskList.forEach((task) => {
      if (task.status === "running") {
        active.push(task);
      } else {
        completed.push(task);
      }
    });
    return { activeTasks: active, completedTasks: completed };
  }, [taskList]);

  // Handle task run
  const handleStartTaskRun = useCallback(async () => {
    // Collect selected model-suite IDs
    const selectedModelSuiteIds: string[] = [];
    suiteList.forEach((suite) => {
      const tests = selectedTestsBySuite[suite.id];
      if (tests && tests.size > 0) {
        selectedModelSuiteIds.push(suite.id);
      }
    });

    await startTaskRun(
      selectedModelSuiteIds,
      runMode,
      selectedTestsBySuite,
      setNotice,
      maxConcurrent
    );
  }, [
    suiteList,
    selectedTestsBySuite,
    runMode,
    startTaskRun,
    setNotice,
    maxConcurrent,
  ]);

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
      const tests = suite.route_suite.tests;
      if (Array.isArray(tests)) {
        tests.forEach((test) => {
          const row = test as { name?: unknown };
          if (typeof row.name === "string") {
            toggleTest(suite.id, row.name, true);
          }
        });
      }
    });
  }, [selectAllProviders, suiteList, toggleTest]);

  // Clear all selections
  const handleClearAll = useCallback(() => {
    clearAllProviders();
    suites.setSelectedTestsBySuite({});
  }, [clearAllProviders, suites]);

  // Handle delete task
  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      await deleteTaskFromServer(taskId);
    },
    [deleteTaskFromServer]
  );

  const handleRefreshMemory = useCallback(async () => {
    const result = await refreshRegistryCache();
    setNotice(`Registry refreshed: ${result.suite_count} suites / ${result.version_count} versions.`);
  }, [refreshRegistryCache, setNotice]);

  const handleRetryFailedTest = useCallback(
    async (run: RunJob, testName: string): Promise<void> => {
      await tasks.retryFailedTestInPlace(run, testName, setNotice);
    },
    [tasks, setNotice]
  );

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Left Panel - Test Selector (with Run controls) */}
      <div className="w-[500px] flex-shrink-0 border-r border-slate-200 bg-slate-50">
        <div className="h-full overflow-auto p-1.5">
          <TestSelector
            providers={providers}
            suites={suiteList}
            selectedTestsBySuite={selectedTestsBySuite}
            expandedProviders={expandedProviders}
            expandedSuites={expandedSuites}
            selectedTestCount={selectedTestCount}
            runMode={runMode}
            isRunning={isRunning}
            isLoading={isLoading}
            isRefreshingCache={isRefreshingRegistryCache}
            maxConcurrent={maxConcurrent}
            onToggleProvider={toggleProvider}
            onToggleProviderExpanded={toggleProviderPanel}
            onToggleSuiteExpanded={toggleSuitePanel}
            onToggleTests={handleToggleTests}
            onToggleTest={toggleTest}
            onSelectAll={handleSelectAll}
            onClearAll={handleClearAll}
            onRunModeChange={setRunMode}
            onMaxConcurrentChange={setMaxConcurrent}
            onRefreshCache={() => void handleRefreshMemory()}
            onRun={() => void handleStartTaskRun()}
          />
        </div>
      </div>

      {/* Right Panel - Task Cards */}
      <div className="flex-1 overflow-auto bg-slate-50">
        <div className="p-1.5 space-y-4">
          {/* Empty State */}
          {taskList.length === 0 && (
            <div className="border border-slate-200 rounded-lg bg-white p-8 text-center">
              <p className="text-sm text-slate-500">
                No tasks yet. Select routes and click Run to start.
              </p>
            </div>
          )}

          {/* Active Tasks */}
          {activeTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              eventsByRunId={runEventsById}
              resultsByRunId={runResultById}
              onDelete={handleDeleteTask}
              onUpdate={upsertTask}
              onRetryFailedTest={handleRetryFailedTest}
            />
          ))}

          {/* Completed Tasks */}
          {completedTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              eventsByRunId={runEventsById}
              resultsByRunId={runResultById}
              onDelete={handleDeleteTask}
              onUpdate={upsertTask}
              onRetryFailedTest={handleRetryFailedTest}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
