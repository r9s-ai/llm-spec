import { useState, useMemo } from "react";
import { TestResultItem } from "./TestResultItem";

export interface TestResult {
  name: string;
  status: "pass" | "fail" | "skip";
  duration?: number;
  errorMessage?: string;
  errorType?: string;
  statusCode?: number;
  responseBody?: Record<string, unknown>;
}

interface TestResultListProps {
  tests: TestResult[];
  onTestClick?: (test: TestResult) => void;
}

type FilterType = "all" | "pass" | "fail";

export function TestResultList({ tests, onTestClick }: TestResultListProps) {
  const [filter, setFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTests = useMemo(() => {
    let result = tests;

    // Apply status filter
    if (filter !== "all") {
      result = result.filter((t) => t.status === filter);
    }

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((t) => t.name.toLowerCase().includes(query));
    }

    return result;
  }, [tests, filter, searchQuery]);

  const counts = useMemo(
    () => ({
      all: tests.length,
      pass: tests.filter((t) => t.status === "pass").length,
      fail: tests.filter((t) => t.status === "fail").length,
    }),
    [tests]
  );

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex items-center gap-2">
        <div className="flex rounded-lg bg-slate-100 p-1">
          {(["all", "pass", "fail"] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-all ${
                filter === f
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {f === "all" ? "All" : f === "pass" ? "Passed" : "Failed"}
              <span className="ml-1 rounded-full bg-slate-200 px-1.5 text-[10px]">{counts[f]}</span>
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1">
          <svg
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tests..."
            className="w-full rounded-lg border border-slate-200 py-1.5 pl-8 pr-3 text-xs placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          />
        </div>
      </div>

      {/* Test List */}
      <div className="max-h-[400px] space-y-1.5 overflow-auto">
        {filteredTests.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">
            {searchQuery ? "No tests match your search" : "No tests to display"}
          </p>
        ) : (
          filteredTests.map((test) => (
            <TestResultItem
              key={test.name}
              name={test.name}
              status={test.status}
              duration={test.duration}
              errorMessage={test.errorMessage}
              onClick={onTestClick ? () => onTestClick(test) : undefined}
            />
          ))
        )}
      </div>
    </div>
  );
}
