import { useCallback, useState } from "react";
import { flushSync } from "react-dom";
import {
  createTask,
  deleteTask,
  getTask,
  getTasks,
  getRunTaskResult,
  retryRunTest,
  streamRunEvents,
  updateTask,
} from "../api";
import type { RunEvent, RunJob, RunMode, TaskWithRuns, TestSelectionMap } from "../types";

export function useTasks() {
  const [tasks, setTasks] = useState<TaskWithRuns[]>([]);
  const [runEventsById, setRunEventsById] = useState<Record<string, RunEvent[]>>({});
  const [runResultById, setRunResultById] = useState<Record<string, Record<string, unknown>>>({});

  // Add or update a task
  const upsertTask = useCallback((task: TaskWithRuns): void => {
    setTasks((prev) => {
      const idx = prev.findIndex((t) => t.id === task.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = task;
        return next;
      }
      return [task, ...prev];
    });
  }, []);

  // Update a single run within a task
  const updateRunInTask = useCallback((taskId: string, run: RunJob): void => {
    setTasks((prev) => {
      const task = prev.find((t) => t.id === taskId);
      if (!task) return prev;

      const runIdx = task.runs.findIndex((r) => r.id === run.id);
      if (runIdx < 0) return prev;

      const newRuns = [...task.runs];
      newRuns[runIdx] = run;

      // Recalculate task stats
      const completedRuns = newRuns.filter(
        (r) => r.status === "success" || r.status === "failed" || r.status === "cancelled"
      ).length;
      const passedRuns = newRuns.filter((r) => r.status === "success").length;
      const failedRuns = newRuns.filter((r) => r.status === "failed").length;

      const updatedTask: TaskWithRuns = {
        ...task,
        runs: newRuns,
        completed_runs: completedRuns,
        passed_runs: passedRuns,
        failed_runs: failedRuns,
        status: completedRuns >= task.total_runs ? "completed" : "running",
      };

      const idx = prev.findIndex((t) => t.id === taskId);
      const next = [...prev];
      next[idx] = updatedTask;
      return next;
    });
  }, []);

  // Push event to run
  const pushEvent = useCallback((runId: string, event: RunEvent): void => {
    setRunEventsById((prev) => {
      const history = prev[runId] ?? [];
      return { ...prev, [runId]: [event, ...history].slice(0, 120) };
    });
  }, []);

  // Load run result
  const loadRunResult = useCallback(async (runId: string): Promise<void> => {
    try {
      const result = await getRunTaskResult(runId);
      setRunResultById((prev) => ({ ...prev, [runId]: result }));
    } catch {
      // Ignore errors
    }
  }, []);

  // Attach SSE stream to a run
  const attachRunStream = useCallback(
    (taskId: string, runId: string): void => {
      const source = streamRunEvents(runId, 0);

      const onDataEvent = async (raw: MessageEvent): Promise<void> => {
        const event = JSON.parse(raw.data) as RunEvent;
        pushEvent(runId, event);

        // Update run progress_total from run_started event
        if (event.event_type === "run_started") {
          const progressTotal = event.payload.progress_total as number | undefined;
          if (progressTotal !== undefined) {
            setTasks((prev) => {
              const task = prev.find((t) => t.id === taskId);
              if (!task) return prev;
              const runIdx = task.runs.findIndex((r) => r.id === runId);
              if (runIdx < 0) return prev;
              const newRuns = [...task.runs];
              newRuns[runIdx] = { ...newRuns[runIdx], progress_total: progressTotal };
              const idx = prev.findIndex((t) => t.id === taskId);
              const next = [...prev];
              next[idx] = { ...task, runs: newRuns };
              return next;
            });
          }
        }

        // Update run progress from test_finished event
        if (event.event_type === "test_finished") {
          const progressDone = event.payload.progress_done as number | undefined;
          const progressTotal = event.payload.progress_total as number | undefined;
          const progressPassed = event.payload.progress_passed as number | undefined;
          const progressFailed = event.payload.progress_failed as number | undefined;
          if (progressDone !== undefined) {
            setTasks((prev) => {
              const task = prev.find((t) => t.id === taskId);
              if (!task) return prev;
              const runIdx = task.runs.findIndex((r) => r.id === runId);
              if (runIdx < 0) return prev;
              const newRuns = [...task.runs];
              newRuns[runIdx] = {
                ...newRuns[runIdx],
                progress_done: progressDone,
                progress_total: progressTotal ?? newRuns[runIdx].progress_total,
                progress_passed: progressPassed ?? newRuns[runIdx].progress_passed,
                progress_failed: progressFailed ?? newRuns[runIdx].progress_failed,
              };
              const idx = prev.findIndex((t) => t.id === taskId);
              const next = [...prev];
              next[idx] = { ...task, runs: newRuns };
              return next;
            });
          }
        }
      };

      [
        "run_started",
        "test_started",
        "test_finished",
        "run_failed",
        "run_cancelled",
        "run_finished",
      ].forEach((name) => {
        source.addEventListener(name, (event) => {
          void onDataEvent(event as MessageEvent);
        });
      });

      source.addEventListener("run_finished", async (event) => {
        const runEvent = JSON.parse((event as MessageEvent).data);
        const status = runEvent?.payload?.status as string | undefined;

        source.close();

        // Load run result FIRST before updating task state
        try {
          const result = await getRunTaskResult(runId);
          flushSync(() => {
            setRunResultById((prev) => ({ ...prev, [runId]: result }));
          });
        } catch {
          // Ignore errors
        }

        // Now update the run status and task state
        if (status) {
          setTasks((prev) => {
            const task = prev.find((t) => t.id === taskId);
            if (!task) return prev;
            const runIdx = task.runs.findIndex((r) => r.id === runId);
            if (runIdx < 0) return prev;
            const newRuns = [...task.runs];
            newRuns[runIdx] = {
              ...newRuns[runIdx],
              status: status === "success" ? "success" : "failed",
              finished_at: new Date().toISOString(),
            };

            const completedRuns = newRuns.filter(
              (r) => r.status === "success" || r.status === "failed" || r.status === "cancelled"
            ).length;
            const allComplete = completedRuns >= newRuns.length;

            const idx = prev.findIndex((t) => t.id === taskId);
            const next = [...prev];
            next[idx] = {
              ...task,
              runs: newRuns,
              completed_runs: completedRuns,
              passed_runs: newRuns.filter((r) => r.status === "success").length,
              failed_runs: newRuns.filter((r) => r.status === "failed").length,
              status: allComplete ? "completed" : "running",
              finished_at: allComplete ? new Date().toISOString() : task.finished_at,
            };
            return next;
          });
        }
      });

      source.addEventListener("done", () => source.close());
      source.onerror = () => source.close();
    },
    [pushEvent]
  );

  // Start a new task run
  const startTaskRun = useCallback(
    async (
      suiteVersionIds: string[],
      mode: RunMode,
      selectedTestsBySuite: TestSelectionMap,
      onNotice: (msg: string) => void,
      maxConcurrent?: number
    ): Promise<void> => {
      if (suiteVersionIds.length === 0) {
        onNotice("Pick at least one model/route to run.");
        return;
      }

      onNotice(`Starting task with ${suiteVersionIds.length} run(s)...`);

      const selectedTestsBySuiteStr: Record<string, string[]> = {};
      for (const [suiteId, tests] of Object.entries(selectedTestsBySuite)) {
        if (tests.size > 0) {
          selectedTestsBySuiteStr[suiteId] = Array.from(tests);
        }
      }

      const task = await createTask({
        suite_version_ids: suiteVersionIds,
        mode,
        selected_tests_by_suite: selectedTestsBySuiteStr,
        max_concurrent: maxConcurrent,
      });

      upsertTask(task);

      setRunEventsById((prev) => {
        const next = { ...prev };
        for (const run of task.runs) {
          next[run.id] = [];
        }
        return next;
      });

      for (const run of task.runs) {
        attachRunStream(task.id, run.id);
      }

      onNotice("Task started.");
    },
    [upsertTask, attachRunStream]
  );

  // Load history tasks
  const loadHistory = useCallback(
    async (limit = 20): Promise<void> => {
      const taskList = await getTasks({ limit });
      const tasksWithRuns = await Promise.all(taskList.map((t) => getTask(t.id)));
      setTasks(tasksWithRuns);

      for (const task of tasksWithRuns) {
        for (const run of task.runs) {
          if (run.status === "success" || run.status === "failed") {
            await loadRunResult(run.id);
          }
        }
      }
    },
    [loadRunResult]
  );

  // Remove a task from local state (not from server)
  const removeTask = useCallback((taskId: string): void => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  }, []);

  // Delete a task from server
  const deleteTaskFromServer = useCallback(
    async (taskId: string): Promise<void> => {
      await deleteTask(taskId);
      removeTask(taskId);
    },
    [removeTask]
  );

  // Update task name
  const updateTaskName = useCallback(async (taskId: string, name: string): Promise<TaskWithRuns> => {
    const updated = await updateTask(taskId, name);
    setTasks((prev) => {
      const idx = prev.findIndex((t) => t.id === taskId);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], name: updated.name };
        return next;
      }
      return prev;
    });
    // Return a Task shape; caller usually just needs name.
    return getTask(taskId);
  }, []);

  const retryFailedTestInPlace = useCallback(
    async (run: RunJob, testName: string, onNotice: (msg: string) => void): Promise<void> => {
      onNotice(`Retrying ${testName}...`);
      const updatedRun = await retryRunTest(run.id, testName);
      const updatedResult = await getRunTaskResult(run.id);

      setRunResultById((prev) => ({ ...prev, [run.id]: updatedResult }));

      if (updatedRun.task_id) {
        updateRunInTask(updatedRun.task_id, updatedRun);
      } else {
        setTasks((prev) =>
          prev.map((task) => ({
            ...task,
            runs: task.runs.map((r) => (r.id === updatedRun.id ? updatedRun : r)),
          }))
        );
      }

      onNotice(`Retried ${testName}. Backend result updated.`);
    },
    [updateRunInTask]
  );

  return {
    // State
    tasks,
    runEventsById,
    runResultById,

    // Methods
    upsertTask,
    updateRunInTask,
    pushEvent,
    attachRunStream,
    startTaskRun,
    loadHistory,
    removeTask,
    deleteTaskFromServer,
    updateTaskName,
    retryFailedTestInPlace,
  };
}
