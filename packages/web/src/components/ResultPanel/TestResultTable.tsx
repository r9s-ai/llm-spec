import { useState, Fragment } from "react";

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

interface TestResultTableProps {
  tests: TestResultRow[];
}

export function TestResultTable({ tests }: TestResultTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (testName: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(testName)) {
        next.delete(testName);
      } else {
        next.add(testName);
      }
      return next;
    });
  };

  const formatLatency = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return JSON.stringify(value);
  };

  const isFailed = (test: TestResultRow): boolean => {
    return test.result?.status === "fail";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
            <th className="w-10 px-2 py-2">Status</th>
            <th className="px-2 py-2">Test Name</th>
            <th className="px-2 py-2">Param</th>
            <th className="px-2 py-2">Value</th>
            <th className="px-2 py-2 text-center">Code</th>
            <th className="px-2 py-2">Validation</th>
            <th className="px-2 py-2 text-right">Time</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tests.map((test) => {
            const failed = isFailed(test);
            const expanded = expandedRows.has(test.test_name);

            return (
              <Fragment key={test.test_name}>
                <tr
                  className={`transition-colors hover:bg-slate-50 ${failed ? "bg-red-50/50" : ""}`}
                >
                  {/* Status */}
                  <td className="px-2 py-2">
                    {failed ? (
                      <span className="text-red-500 font-bold">✗</span>
                    ) : (
                      <span className="text-green-500 font-bold">✓</span>
                    )}
                  </td>

                  {/* Test Name */}
                  <td className="px-2 py-2 font-medium text-slate-900">{test.test_name}</td>

                  {/* Param Name */}
                  <td className="px-2 py-2 text-slate-600">{test.parameter?.name ?? "-"}</td>

                  {/* Param Value */}
                  <td className="px-2 py-2 text-slate-600">
                    <span
                      className="truncate max-w-[120px] block"
                      title={formatValue(test.parameter?.value)}
                    >
                      {formatValue(test.parameter?.value)}
                    </span>
                  </td>

                  {/* HTTP Status Code */}
                  <td className="px-2 py-2 text-center">
                    <span
                      className={`inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium ${
                        test.request?.http_status === 200
                          ? "bg-green-100 text-green-700"
                          : test.request?.http_status && test.request.http_status >= 400
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {test.request?.http_status ?? "-"}
                    </span>
                  </td>

                  {/* Validation Result */}
                  <td className="px-2 py-2">
                    {failed ? (
                      <button
                        onClick={() => toggleRow(test.test_name)}
                        className="flex items-center gap-1 text-red-600 hover:text-red-700"
                      >
                        <span className="font-medium">Failed</span>
                        <svg
                          className={`h-4 w-4 transition-transform ${expanded ? "rotate-180" : ""}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                      </button>
                    ) : (
                      <span className="text-green-600 font-medium">OK</span>
                    )}
                  </td>

                  {/* Latency */}
                  <td className="px-2 py-2 text-right text-slate-500">
                    {test.request?.latency_ms ? formatLatency(test.request.latency_ms) : "-"}
                  </td>
                </tr>

                {/* Expanded Error Details */}
                {failed && expanded && (
                  <tr className="bg-red-50/30">
                    <td colSpan={7} className="px-4 py-3">
                      <div className="space-y-2 text-xs">
                        {/* Reason */}
                        {test.result?.reason && (
                          <div>
                            <span className="font-medium text-red-700">Reason: </span>
                            <span className="text-red-600">{test.result.reason}</span>
                          </div>
                        )}

                        {/* Missing Fields */}
                        {test.validation?.missing_fields &&
                          test.validation.missing_fields.length > 0 && (
                            <div>
                              <span className="font-medium text-red-700">Missing Fields: </span>
                              <span className="text-red-600">
                                {test.validation.missing_fields.join(", ")}
                              </span>
                            </div>
                          )}

                        {/* Missing Events (for streaming tests) */}
                        {test.validation?.missing_events &&
                          test.validation.missing_events.length > 0 && (
                            <div>
                              <span className="font-medium text-red-700">Missing Events: </span>
                              <span className="text-red-600">
                                {test.validation.missing_events.join(", ")}
                              </span>
                            </div>
                          )}

                        {/* Validation Details */}
                        <div className="flex gap-4 text-slate-600">
                          <span>Schema: {test.validation?.schema_ok ? "✓" : "✗"}</span>
                          <span>
                            Required Fields: {test.validation?.required_fields_ok ? "✓" : "✗"}
                          </span>
                          {test.validation?.stream_rules_ok !== undefined && (
                            <span>Stream Rules: {test.validation.stream_rules_ok ? "✓" : "✗"}</span>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>

      {tests.length === 0 && (
        <div className="py-8 text-center text-sm text-slate-400">No test results available</div>
      )}
    </div>
  );
}
