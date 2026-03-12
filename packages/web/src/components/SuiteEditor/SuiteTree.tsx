import { useMemo } from "react";
import type { Suite } from "../../types";

interface SuiteTreeProps {
  suites: Suite[];
  selectedSuiteId: string | null;
  searchQuery: string;
  onSelectSuite: (suiteId: string) => void;
  onSearchChange: (query: string) => void;
}

export function SuiteTree({
  suites,
  selectedSuiteId,
  searchQuery,
  onSelectSuite,
  onSearchChange,
}: SuiteTreeProps) {
  // Filter suites by search query
  const filteredSuites = useMemo(() => {
    if (!searchQuery) return suites;
    const query = searchQuery.toLowerCase();
    return suites.filter(
      (suite) =>
        suite.suite_name.toLowerCase().includes(query) ||
        suite.endpoint.toLowerCase().includes(query) ||
        suite.route_id.toLowerCase().includes(query) ||
        suite.model_id.toLowerCase().includes(query) ||
        suite.provider_id.toLowerCase().includes(query)
    );
  }, [suites, searchQuery]);

  const sortedSuites = useMemo(
    () =>
      filteredSuites.slice().sort(
        (a, b) =>
          a.provider_id.localeCompare(b.provider_id) ||
          a.model_id.localeCompare(b.model_id) ||
          a.route_id.localeCompare(b.route_id)
      ),
    [filteredSuites]
  );

  const handleSearchChange = (value: string) => {
    onSearchChange(value);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Search */}
      <div className="flex-shrink-0 pb-3">
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
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
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search suites..."
            className="h-9 w-full rounded-lg border border-slate-200 py-2 pl-10 pr-4 text-sm placeholder:text-slate-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Suite List */}
      <div className="flex-1 space-y-2 overflow-auto">
        {sortedSuites.map((suite) => (
          <div
            key={suite.suite_id}
            className={`rounded-lg border px-3 py-2 transition-colors cursor-pointer ${
              suite.suite_id === selectedSuiteId
                ? "border-violet-200 bg-violet-50"
                : "border-slate-200 bg-white hover:bg-slate-50"
            }`}
            onClick={() => onSelectSuite(suite.suite_id)}
          >
            <div className="flex items-center gap-2">
              <span
                className="truncate text-sm font-medium text-slate-900"
                title={suite.suite_name || suite.model_id}
              >
                {suite.suite_name || suite.model_id}
              </span>
              <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                {suite.provider_id}:{suite.model_id}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span className="truncate" title={suite.endpoint}>
                {suite.endpoint}
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {suite.route_id}
              </span>
            </div>
          </div>
        ))}

        {sortedSuites.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">
            {searchQuery ? "No matching suites" : "No suites available"}
          </div>
        )}
      </div>
    </div>
  );
}
