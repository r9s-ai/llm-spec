import { useState, useMemo } from "react";
import { TestResultList, type TestResult } from "./TestResultList";
import { ErrorDetailModal } from "./ErrorDetailModal";

interface RunResultData {
  summary?: {
    total?: number;
    passed?: number;
    failed?: number;
  };
  tests?: TestResult[];
}

interface RunResultPanelProps {
  runId: string;
  provider: string;
  endpoint: string;
  result: RunResultData;
  onClose: () => void;
}

export function RunResultPanel({
  runId,
  provider,
  endpoint,
  result,
  onClose,
}: RunResultPanelProps) {
  const [selectedTest, setSelectedTest] = useState<TestResult | null>(null);

  const summary = useMemo(
    () => result.summary ?? { total: 0, passed: 0, failed: 0 },
    [result.summary]
  );
  const tests = result.tests ?? [];

  const passRate = useMemo(() => {
    if (!summary.total || summary.total === 0) return 0;
    return Math.round(((summary.passed ?? 0) / summary.total) * 100);
  }, [summary]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h3 className="font-bold text-slate-900">
            {provider} {endpoint}
          </h3>
          <p className="text-xs text-slate-500">{runId}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Summary */}
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-600">Pass Rate</span>
          <span className="text-lg font-bold text-slate-900">{passRate}%</span>
        </div>
        <div className="flex gap-3">
          <div className="flex-1 rounded-lg bg-slate-50 p-3 text-center">
            <div className="text-2xl font-bold text-slate-900">{summary.total ?? 0}</div>
            <div className="text-xs text-slate-500">Total</div>
          </div>
          <div className="flex-1 rounded-lg bg-green-50 p-3 text-center">
            <div className="text-2xl font-bold text-green-600">{summary.passed ?? 0}</div>
            <div className="text-xs text-green-600">Passed</div>
          </div>
          <div className="flex-1 rounded-lg bg-red-50 p-3 text-center">
            <div className="text-2xl font-bold text-red-600">{summary.failed ?? 0}</div>
            <div className="text-xs text-red-600">Failed</div>
          </div>
        </div>
      </div>

      {/* Test List */}
      <div className="p-4">
        <h4 className="mb-3 text-sm font-bold text-slate-700">Test Results</h4>
        <TestResultList tests={tests} onTestClick={setSelectedTest} />
      </div>

      {/* Error Detail Modal */}
      <ErrorDetailModal
        test={selectedTest}
        isOpen={selectedTest !== null}
        onClose={() => setSelectedTest(null)}
      />
    </div>
  );
}
