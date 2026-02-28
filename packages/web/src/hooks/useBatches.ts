import { useCallback, useState } from "react";
import { flushSync } from "react-dom";
import {
  createBatch,
  deleteBatch,
  getBatch,
  getBatches,
  getRunTaskResult,
  retryRunTest,
  streamRunEvents,
  updateBatch,
} from "../api";
import type {
  RunBatch,
  RunBatchWithRuns,
  RunEvent,
  RunJob,
  RunMode,
  TestSelectionMap,
} from "../types";

export function useBatches() {
  const [batches, setBatches] = useState<RunBatchWithRuns[]>([]);
  const [runEventsById, setRunEventsById] = useState<Record<string, RunEvent[]>>({});
  const [runResultById, setRunResultById] = useState<Record<string, Record<string, unknown>>>({});

  // Add or update a batch
  const upsertBatch = useCallback((batch: RunBatchWithRuns): void => {
    setBatches((prev) => {
      const idx = prev.findIndex((b) => b.id === batch.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = batch;
        return next;
      }
      return [batch, ...prev];
    });
  }, []);

  // Update a single run within a batch
  const updateRunInBatch = useCallback((batchId: string, run: RunJob): void => {
    setBatches((prev) => {
      const batch = prev.find((b) => b.id === batchId);
      if (!batch) return prev;

      const runIdx = batch.runs.findIndex((r) => r.id === run.id);
      if (runIdx < 0) return prev;

      const newRuns = [...batch.runs];
      newRuns[runIdx] = run;

      // Recalculate batch stats
      const completedRuns = newRuns.filter(
        (r) => r.status === "success" || r.status === "failed" || r.status === "cancelled"
      ).length;
      const passedRuns = newRuns.filter((r) => r.status === "success").length;
      const failedRuns = newRuns.filter((r) => r.status === "failed").length;

      const updatedBatch: RunBatchWithRuns = {
        ...batch,
        runs: newRuns,
        completed_runs: completedRuns,
        passed_runs: passedRuns,
        failed_runs: failedRuns,
        status: completedRuns >= batch.total_runs ? "completed" : "running",
      };

      const idx = prev.findIndex((b) => b.id === batchId);
      const next = [...prev];
      next[idx] = updatedBatch;
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
    (batchId: string, runId: string): void => {
      const source = streamRunEvents(runId, 0);

      const onDataEvent = async (raw: MessageEvent): Promise<void> => {
        const event = JSON.parse(raw.data) as RunEvent;
        pushEvent(runId, event);

        // Update run progress_total from run_started event
        if (event.event_type === "run_started") {
          const progressTotal = event.payload.progress_total as number | undefined;
          if (progressTotal !== undefined) {
            setBatches((prev) => {
              const batch = prev.find((b) => b.id === batchId);
              if (!batch) return prev;
              const runIdx = batch.runs.findIndex((r) => r.id === runId);
              if (runIdx < 0) return prev;
              const newRuns = [...batch.runs];
              newRuns[runIdx] = { ...newRuns[runIdx], progress_total: progressTotal };
              const idx = prev.findIndex((b) => b.id === batchId);
              const next = [...prev];
              next[idx] = { ...batch, runs: newRuns };
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
            setBatches((prev) => {
              const batch = prev.find((b) => b.id === batchId);
              if (!batch) return prev;
              const runIdx = batch.runs.findIndex((r) => r.id === runId);
              if (runIdx < 0) return prev;
              const newRuns = [...batch.runs];
              newRuns[runIdx] = {
                ...newRuns[runIdx],
                progress_done: progressDone,
                progress_total: progressTotal ?? newRuns[runIdx].progress_total,
                progress_passed: progressPassed ?? newRuns[runIdx].progress_passed,
                progress_failed: progressFailed ?? newRuns[runIdx].progress_failed,
              };
              const idx = prev.findIndex((b) => b.id === batchId);
              const next = [...prev];
              next[idx] = { ...batch, runs: newRuns };
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
        // Parse the run_finished event to get the status
        const runEvent = JSON.parse((event as MessageEvent).data);
        const status = runEvent?.payload?.status as string | undefined;

        source.close();

        // Load run result FIRST before updating batch state
        // Use flushSync to ensure the result is available immediately
        try {
          const result = await getRunTaskResult(runId);
          flushSync(() => {
            setRunResultById((prev) => ({ ...prev, [runId]: result }));
          });
        } catch {
          // Ignore errors
        }

        // Now update the run status and batch state
        if (status) {
          setBatches((prev) => {
            const batch = prev.find((b) => b.id === batchId);
            if (!batch) return prev;
            const runIdx = batch.runs.findIndex((r) => r.id === runId);
            if (runIdx < 0) return prev;
            const newRuns = [...batch.runs];
            newRuns[runIdx] = {
              ...newRuns[runIdx],
              status: status === "success" ? "success" : "failed",
              finished_at: new Date().toISOString(),
            };

            // Check if all runs are complete
            const completedRuns = newRuns.filter(
              (r) => r.status === "success" || r.status === "failed" || r.status === "cancelled"
            ).length;
            const allComplete = completedRuns >= newRuns.length;

            const idx = prev.findIndex((b) => b.id === batchId);
            const next = [...prev];
            next[idx] = {
              ...batch,
              runs: newRuns,
              completed_runs: completedRuns,
              passed_runs: newRuns.filter((r) => r.status === "success").length,
              failed_runs: newRuns.filter((r) => r.status === "failed").length,
              status: allComplete ? "completed" : "running",
              finished_at: allComplete ? new Date().toISOString() : batch.finished_at,
            };
            return next;
          });
        }
      });

      source.addEventListener("done", () => {
        source.close();
      });

      source.onerror = () => {
        source.close();
      };
    },
    [pushEvent]
  );

  // Start a new batch run
  const startBatchRun = useCallback(
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

      onNotice(`Starting batch with ${suiteVersionIds.length} run(s)...`);

      // Convert Set<string> to string[] for API
      const selectedTestsBySuiteStr: Record<string, string[]> = {};
      for (const [suiteId, tests] of Object.entries(selectedTestsBySuite)) {
        if (tests.size > 0) {
          selectedTestsBySuiteStr[suiteId] = Array.from(tests);
        }
      }

      const batch = await createBatch({
        suite_version_ids: suiteVersionIds,
        mode,
        selected_tests_by_suite: selectedTestsBySuiteStr,
        max_concurrent: maxConcurrent,
      });

      upsertBatch(batch);

      // Initialize event storage for each run
      setRunEventsById((prev) => {
        const next = { ...prev };
        for (const run of batch.runs) {
          next[run.id] = [];
        }
        return next;
      });

      // Attach SSE streams to all runs
      for (const run of batch.runs) {
        attachRunStream(batch.id, run.id);
      }

      onNotice("Batch started.");
    },
    [upsertBatch, attachRunStream]
  );

  // Load history batches
  const loadHistory = useCallback(
    async (limit = 20): Promise<void> => {
      const batchList = await getBatches({ limit });
      // Load full batch details with runs
      const batchesWithRuns = await Promise.all(batchList.map((batch) => getBatch(batch.id)));
      setBatches(batchesWithRuns);

      // Load results for completed runs
      for (const batch of batchesWithRuns) {
        for (const run of batch.runs) {
          if (run.status === "success" || run.status === "failed") {
            await loadRunResult(run.id);
          }
        }
      }
    },
    [loadRunResult]
  );

  // Remove a batch from local state (not from server)
  const removeBatch = useCallback((batchId: string): void => {
    setBatches((prev) => prev.filter((b) => b.id !== batchId));
  }, []);

  // Delete a batch from server
  const deleteBatchFromServer = useCallback(
    async (batchId: string): Promise<void> => {
      await deleteBatch(batchId);
      removeBatch(batchId);
    },
    [removeBatch]
  );

  // Update batch name
  const updateBatchName = useCallback(async (batchId: string, name: string): Promise<RunBatch> => {
    const updated = await updateBatch(batchId, name);
    // Update local state
    setBatches((prev) => {
      const idx = prev.findIndex((b) => b.id === batchId);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], name: updated.name };
        return next;
      }
      return prev;
    });
    return updated;
  }, []);

  const retryFailedTestInPlace = useCallback(
    async (run: RunJob, testName: string, onNotice: (msg: string) => void): Promise<void> => {
      onNotice(`Retrying ${testName}...`);
      const updatedRun = await retryRunTest(run.id, testName);
      const updatedResult = await getRunTaskResult(run.id);

      setRunResultById((prev) => ({ ...prev, [run.id]: updatedResult }));

      if (updatedRun.batch_id) {
        updateRunInBatch(updatedRun.batch_id, updatedRun);
      } else {
        setBatches((prev) =>
          prev.map((batch) => ({
            ...batch,
            runs: batch.runs.map((r) => (r.id === updatedRun.id ? updatedRun : r)),
          }))
        );
      }

      onNotice(`Retried ${testName}. Backend result updated.`);
    },
    [updateRunInBatch]
  );

  return {
    // State
    batches,
    runEventsById,
    runResultById,

    // Methods
    upsertBatch,
    updateRunInBatch,
    pushEvent,
    attachRunStream,
    startBatchRun,
    loadHistory,
    removeBatch,
    deleteBatchFromServer,
    updateBatchName,
    retryFailedTestInPlace,
  };
}
