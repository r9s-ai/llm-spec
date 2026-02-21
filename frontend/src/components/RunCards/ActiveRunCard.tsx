import type { RunJob, RunEvent } from "../../types";

interface TestResultRow {
  test_name: string;
  status: "pending" | "running" | "pass" | "fail";
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

interface ActiveRunCardProps {
  run: RunJob;
  events: RunEvent[];
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function ActiveRunCard({ run, events }: ActiveRunCardProps) {
  // Build test results from events
  const testResults: TestResultRow[] = [];
  const runningTests = new Set<string>();

  // Process events in order
  for (const event of events) {
    if (event.event_type === "test_started") {
      const testName = (event.payload.test_name as string) || "Unknown";
      runningTests.add(testName);
    } else if (event.event_type === "test_finished") {
      const testName = (event.payload.test_name as string) || "Unknown";
      const status = (event.payload.status as string) || "fail";
      const testResult = event.payload.test_result as Record<string, unknown> | undefined;

      runningTests.delete(testName);

      testResults.push({
        test_name: testName,
        status: status === "pass" ? "pass" : "fail",
        parameter: testResult?.parameter as TestResultRow["parameter"],
        request: testResult?.request as TestResultRow["request"],
        result: testResult?.result as TestResultRow["result"],
        validation: testResult?.validation as TestResultRow["validation"],
      });
    }
  }

  // Add running tests
  for (const testName of runningTests) {
    testResults.push({
      test_name: testName,
      status: "running",
    });
  }

  // Add pending tests (we don't know the names until they start)
  const completedCount = run.progress_done;
  const totalCount = run.progress_total;
  const pendingCount = totalCount - completedCount - runningTests.size;

  // Show pending tests as placeholder rows
  for (let i = 0; i < pendingCount; i++) {
    testResults.push({
      test_name: `Test ${completedCount + runningTests.size + i + 1}`,
      status: "pending",
    });
  }

  return (
    <div className="border-b border-slate-100 last:border-b-0">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 bg-slate-50">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
              Running
            </span>
            <span className="text-xs text-slate-500">{run.mode}</span>
          </div>
          <h4 className="mt-1 truncate text-sm font-semibold text-slate-900">
            {run.provider} {run.endpoint}
          </h4>
        </div>
        <div className="text-right text-xs text-slate-500">
          <span className="font-medium text-violet-600">
            {run.progress_done}/{run.progress_total}
          </span>{" "}
          tests
        </div>
      </div>

      {/* Test Results Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase tracking-wider bg-slate-50">
              <th className="w-10 px-3 py-2">Status</th>
              <th className="px-3 py-2">Test Name</th>
              <th className="px-3 py-2">Param</th>
              <th className="px-3 py-2">Value</th>
              <th className="px-3 py-2 text-center">Code</th>
              <th className="px-3 py-2">Validation</th>
              <th className="px-3 py-2 text-right">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {testResults.map((test, idx) => (
              <tr
                key={`${test.test_name}-${idx}`}
                className={`transition-colors hover:bg-slate-50 ${
                  test.status === "fail" ? "bg-red-50/50" : ""
                }`}
              >
                {/* Status */}
                <td className="px-3 py-2">
                  {test.status === "pending" && <span className="text-slate-300">○</span>}
                  {test.status === "running" && (
                    <svg
                      className="w-4 h-4 text-violet-500 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                  )}
                  {test.status === "pass" && <span className="text-green-500 font-bold">✓</span>}
                  {test.status === "fail" && <span className="text-red-500 font-bold">✗</span>}
                </td>

                {/* Test Name */}
                <td
                  className={`px-3 py-2 font-medium ${
                    test.status === "pending" ? "text-slate-400" : "text-slate-900"
                  }`}
                >
                  {test.test_name}
                </td>

                {/* Param Name */}
                <td
                  className={`px-3 py-2 ${
                    test.status === "pending" ? "text-slate-300" : "text-slate-600"
                  }`}
                >
                  {test.parameter?.name ?? "-"}
                </td>

                {/* Param Value */}
                <td
                  className={`px-3 py-2 ${
                    test.status === "pending" ? "text-slate-300" : "text-slate-600"
                  }`}
                >
                  <span
                    className="truncate max-w-[120px] block"
                    title={formatValue(test.parameter?.value)}
                  >
                    {formatValue(test.parameter?.value)}
                  </span>
                </td>

                {/* HTTP Status Code */}
                <td className="px-3 py-2 text-center">
                  {test.request?.http_status ? (
                    <span
                      className={`inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium ${
                        test.request.http_status === 200
                          ? "bg-green-100 text-green-700"
                          : test.request.http_status >= 400
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {test.request.http_status}
                    </span>
                  ) : (
                    <span className="text-slate-300">-</span>
                  )}
                </td>

                {/* Validation Result */}
                <td className="px-3 py-2">
                  {test.status === "pending" && <span className="text-slate-300">-</span>}
                  {test.status === "running" && (
                    <span className="text-violet-500 text-xs">Testing...</span>
                  )}
                  {test.status === "pass" && (
                    <span className="text-green-600 font-medium text-xs">OK</span>
                  )}
                  {test.status === "fail" && (
                    <span className="text-red-600 font-medium text-xs">Failed</span>
                  )}
                </td>

                {/* Latency */}
                <td className="px-3 py-2 text-right text-slate-500">
                  {test.request?.latency_ms ? formatLatency(test.request.latency_ms) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {testResults.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-400">
            Waiting for tests to start...
          </div>
        )}
      </div>
    </div>
  );
}
