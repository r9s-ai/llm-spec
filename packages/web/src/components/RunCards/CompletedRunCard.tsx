import { useMemo } from "react";
import { Badge } from "../UI";
import { TestResultTable } from "../ResultPanel/TestResultTable";
import type { RunJob, RunSummary } from "../../types";

interface TestResultRow {
  test_name: string;
  parameter?: {
    name: string;
    value: unknown;
    value_type: string;
  };
  request?: {
    http_status: number;
    latency_ms: number;
  };
  result?: {
    status: string;
    reason?: string;
  };
  validation?: {
    schema_ok: boolean;
    required_fields_ok: boolean;
    stream_rules_ok: boolean;
    missing_fields: string[];
    missing_events: string[];
  };
}

interface RunResultData {
  version?: string;
  run_id?: string;
  cases?: TestResultRow[];
}

interface CompletedRunCardProps {
  run: RunJob;
  summary?: RunSummary;
  result?: RunResultData;
  onRetryFailedTest?: (run: RunJob, testName: string) => Promise<void> | void;
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
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
  // Backend sets status to "success" or "failed" (not "finished")
  // success = all tests passed, failed = some tests failed or run error
  const isSuccess = run.status === "success";

  const statusVariant = isSuccess ? "success" : "error";
  const statusText = isSuccess ? "Success" : "Failed";

  const duration = calculateDuration(run.started_at, run.finished_at);
  const relativeTime = formatRelativeTime(run.finished_at);

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
          <Badge variant={statusVariant}>{statusText}</Badge>
          <div>
            <h4 className="font-semibold text-slate-900">
              {run.provider} / {run.model ?? "unknown"} / {run.route ?? run.endpoint}
            </h4>
            <p className="text-xs text-slate-500">
              {run.id} · {run.mode} · {run.endpoint}
            </p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-400">{relativeTime}</span>
          {duration && <p className="text-xs text-slate-500">{duration}</p>}
        </div>
      </div>

      {/* Stats Summary */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-slate-50 text-sm">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          <span className="font-medium text-slate-700">
            {resultSummary?.passed ?? run.progress_passed}
          </span>
          <span className="text-slate-500">passed</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          <span className="font-medium text-slate-700">
            {resultSummary?.failed ?? run.progress_failed}
          </span>
          <span className="text-slate-500">failed</span>
        </div>
        <div className="ml-auto text-xs text-slate-400">
          {resultSummary?.total ?? run.progress_total} tests
        </div>
      </div>

      {/* Test Results Table */}
      {tests.length > 0 && (
        <div className="p-2">
          <TestResultTable
            tests={tests}
            onRetryFailedTest={
              onRetryFailedTest
                ? (testName) => onRetryFailedTest(run, testName)
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
