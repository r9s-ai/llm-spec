import { useCallback, useState } from "react";
import { createRun, getRun, getRunEvents, getRunTaskResult, streamRunEvents } from "../api";
import type { RunEvent, RunJob, RunMode, TestSelectionMap } from "../types";

export function useRuns() {
  const [runs, setRuns] = useState<RunJob[]>([]);
  const [runEventsById, setRunEventsById] = useState<Record<string, RunEvent[]>>({});
  const [runResultById, setRunResultById] = useState<Record<string, Record<string, unknown>>>({});

  // Update or add a run
  const upsertRun = useCallback((run: RunJob): void => {
    setRuns((prev) => {
      const idx = prev.findIndex((r) => r.id === run.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = run;
        return next;
      }
      return [run, ...prev];
    });
  }, []);

  const pushEvent = useCallback((runId: string, event: RunEvent): void => {
    setRunEventsById((prev) => {
      const history = prev[runId] ?? [];
      return { ...prev, [runId]: [event, ...history].slice(0, 120) };
    });
  }, []);

  // finish run
  const finalizeRun = useCallback(
    async (runId: string, latestSeq: number): Promise<void> => {
      const [job, tailEvents] = await Promise.all([getRun(runId), getRunEvents(runId, latestSeq)]);
      upsertRun(job);
      if (tailEvents.length > 0) {
        setRunEventsById((prev) => {
          const existing = prev[runId] ?? [];
          const appended = [...tailEvents].reverse();
          return { ...prev, [runId]: [...appended, ...existing].slice(0, 120) };
        });
      }

      try {
        const result = await getRunTaskResult(runId);
        setRunResultById((prev) => ({ ...prev, [runId]: result }));
      } catch {
        // Ignore result loading failures for unfinished runs.
      }
    },
    [upsertRun]
  );

  // attach SSE stream
  const attachRunStream = useCallback(
    (runId: string): void => {
      let latestSeq = 0;
      const source = streamRunEvents(runId, 0);

      const onDataEvent = async (raw: MessageEvent): Promise<void> => {
        const event = JSON.parse(raw.data) as RunEvent;
        latestSeq = event.seq;
        pushEvent(runId, event);
        if (event.event_type.includes("finished") || event.event_type.includes("started")) {
          const run = await getRun(runId);
          upsertRun(run);
        }
      };

      ["run_started", "test_started", "test_finished", "run_failed", "run_cancelled"].forEach(
        (name) => {
          source.addEventListener(name, (event) => {
            void onDataEvent(event as MessageEvent);
          });
        }
      );

      const finalize = (): void => {
        source.close();
        void finalizeRun(runId, latestSeq);
      };

      source.addEventListener("run_finished", finalize);
      source.addEventListener("done", finalize);
      source.onerror = finalize;
    },
    [finalizeRun, pushEvent, upsertRun]
  );

  // batch run
  const startBatchRun = useCallback(
    async (
      selectedSuiteIds: Set<string>,
      selectedVersionBySuite: Record<string, string>,
      selectedTestsBySuite: TestSelectionMap,
      runMode: RunMode,
      onNotice: (msg: string) => void
    ): Promise<void> => {
      const suiteIds = Array.from(selectedSuiteIds);
      if (suiteIds.length === 0) {
        onNotice("Pick at least one route to run.");
        return;
      }

      onNotice(`Starting ${suiteIds.length} run(s)...`);

      for (const suiteId of suiteIds) {
        const versionId = selectedVersionBySuite[suiteId];
        if (!versionId) continue;

        const tests = selectedTestsBySuite[suiteId];
        const run = await createRun({
          suite_version_id: versionId,
          mode: runMode,
          selected_tests: tests && tests.size > 0 ? Array.from(tests) : undefined,
        });
        upsertRun(run);
        setRunEventsById((prev) => ({ ...prev, [run.id]: [] }));
        attachRunStream(run.id);
      }

      onNotice("Batch started.");
    },
    [attachRunStream, upsertRun]
  );

  return {
    // State
    runs,
    runEventsById,
    runResultById,

    // Methods
    upsertRun,
    pushEvent,
    finalizeRun,
    attachRunStream,
    startBatchRun,
  };
}
