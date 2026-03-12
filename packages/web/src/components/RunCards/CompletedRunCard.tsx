import { useMemo } from "react";
import { TestResultTable } from "../ResultPanel/TestResultTable";
import type { RunJob, RunSummary, TestResultRow } from "../../types";

interface RunResultData {
  version?: string;
  run_id?: string;
  cases?: TestResultRow[];
}

interface CompletedRunCardProps {
  run: RunJob;
  summary?: RunSummary;
  result?: RunResultData;
  onRetryFailedTest?: (run: RunJob, runCaseId: string, testName: string) => Promise<void> | void;
}

function calculateDuration(start: string | null, end: string | null): string {
  if (!start || !end) return "";
  const startDate = new Date(start);
  const endDate = new Date(end);
  const diffMs = endDate.getTime() - startDate.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);

  if (diffMins > 0) {
    const remainingSecs = diffSecs % 60;
    return `${diffMins}m ${remainingSecs}s`;
  }
  return `${diffSecs}s`;
}

export function CompletedRunCard({ run, summary, result, onRetryFailedTest }: CompletedRunCardProps) {
  const duration = calculateDuration(run.started_at, run.finished_at);

  // Extract tests from task result cases
  const tests = useMemo((): TestResultRow[] => {
    if (!result?.cases || !Array.isArray(result.cases)) return [];
    return result.cases;
  }, [result]);

  // Get summary from run progress
  const resultSummary = useMemo((): RunSummary | undefined => {
    if (summary) return summary;
    return {
      total: run.progress_total,
      passed: run.progress_passed,
      failed: run.progress_failed,
    };
  }, [run.progress_failed, run.progress_passed, run.progress_total, summary]);

  return (
    <div className="border-b border-slate-100 last:border-b-0">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 bg-slate-50 px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-semibold text-slate-900">
                {run.route ?? run.endpoint}
              </h4>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  <span className="font-medium text-slate-700">
                    {resultSummary?.passed ?? run.progress_passed}
                  </span>
                  <span className="text-slate-500">passed</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  <span className="font-medium text-slate-700">
                    {resultSummary?.failed ?? run.progress_failed}
                  </span>
                  <span className="text-slate-500">failed</span>
                </span>
                <span className="text-slate-400">
                  {resultSummary?.total ?? run.progress_total} tests
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="text-right">{duration && <p className="text-xs text-slate-500">{duration}</p>}</div>
      </div>

      {/* Test Results Table */}
      {tests.length > 0 && (
        <div className="p-2">
          <TestResultTable
            tests={tests}
            onRetryFailedTest={
              onRetryFailedTest
                ? (runCaseId, testName) => onRetryFailedTest(run, runCaseId, testName)
                : undefined
            }
          />
        </div>
      )}

      {/* No tests message */}
      {tests.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          No test results available
        </div>
      )}

      {/* Error Message */}
      {run.error_message && (
        <div className="px-4 py-2 border-t border-slate-100 bg-red-50/50">
          <p className="text-xs text-red-700">{run.error_message}</p>
        </div>
      )}
    </div>
  );
}
