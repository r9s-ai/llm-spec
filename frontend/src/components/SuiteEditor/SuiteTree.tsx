import { useState, useMemo, useCallback } from "react";
import type { Suite } from "../../types";

interface SuiteTreeProps {
  suites: Suite[];
  selectedSuiteId: string | null;
  searchQuery: string;
  onSelectSuite: (suiteId: string) => void;
  onSearchChange: (query: string) => void;
  onCreateSuite: () => void;
}

export function SuiteTree({
  suites,
  selectedSuiteId,
  searchQuery,
  onSelectSuite,
  onSearchChange,
  onCreateSuite,
}: SuiteTreeProps) {
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set());

  // Group suites by provider
  const suitesByProvider = useMemo(() => {
    const grouped: Record<string, Suite[]> = {};
    suites.forEach((suite) => {
      if (!grouped[suite.provider]) {
        grouped[suite.provider] = [];
      }
      grouped[suite.provider].push(suite);
    });
    return grouped;
  }, [suites]);

  // Filter suites by search query
  const filteredSuitesByProvider = useMemo(() => {
    if (!searchQuery) return suitesByProvider;

    const filtered: Record<string, Suite[]> = {};
    const query = searchQuery.toLowerCase();

    Object.entries(suitesByProvider).forEach(([provider, providerSuites]) => {
      const matchingSuites = providerSuites.filter(
        (suite) =>
          suite.name.toLowerCase().includes(query) ||
          suite.endpoint.toLowerCase().includes(query) ||
          provider.toLowerCase().includes(query)
      );
      if (matchingSuites.length > 0) {
        filtered[provider] = matchingSuites;
      }
    });

    return filtered;
  }, [suitesByProvider, searchQuery]);

  const providers = Object.keys(filteredSuitesByProvider).sort();

  const toggleProvider = useCallback((provider: string) => {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) {
        next.delete(provider);
      } else {
        next.add(provider);
      }
      return next;
    });
  }, []);

  // Auto-expand all when searching
  const handleSearchChange = useCallback(
    (value: string) => {
      onSearchChange(value);
      if (value) {
        setExpandedProviders(new Set(providers));
      }
    },
    [onSearchChange, providers]
  );

  // Expand all providers
  const expandAll = useCallback(() => {
    setExpandedProviders(new Set(providers));
  }, [providers]);

  // Collapse all providers
  const collapseAll = useCallback(() => {
    setExpandedProviders(new Set());
  }, []);

  // Count total suites
  const totalSuites = suites.length;
  const filteredCount = Object.values(filteredSuitesByProvider).flat().length;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex-shrink-0 pb-2 border-b border-slate-200 mb-2">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-bold text-slate-900">Test Suites</h2>
          <span className="text-xs text-slate-500">{totalSuites} total</span>
        </div>
        {/* Search */}
        <div className="relative">
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
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search suites..."
            className="h-8 w-full rounded border border-slate-200 py-1.5 pl-8 pr-3 text-sm placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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

      {/* Expand/Collapse Actions */}
      <div className="flex-shrink-0 flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <button onClick={expandAll} className="text-xs text-slate-600 hover:text-slate-800">
            Expand all
          </button>
          <span className="text-slate-300">|</span>
          <button onClick={collapseAll} className="text-xs text-slate-600 hover:text-slate-800">
            Collapse all
          </button>
        </div>
        {searchQuery && (
          <span className="text-xs text-slate-500">
            {filteredCount} result{filteredCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Provider List */}
      <div className="flex-1 space-y-1 overflow-auto">
        {providers.map((provider) => {
          const providerSuites = filteredSuitesByProvider[provider] ?? [];
          const isExpanded = expandedProviders.has(provider);

          return (
            <div
              key={provider}
              className="rounded border border-slate-200 bg-white overflow-hidden"
            >
              {/* Provider Header */}
              <div
                className="flex items-center gap-2 px-2.5 py-1.5 cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => toggleProvider(provider)}
              >
                <svg
                  className={`h-3.5 w-3.5 text-slate-400 transition-transform ${
                    isExpanded ? "rotate-90" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
                <span className="text-sm font-medium text-slate-900">{provider}</span>
                <span className="ml-auto text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                  {providerSuites.length}
                </span>
              </div>

              {/* Suite List */}
              {isExpanded && (
                <div className="border-t border-slate-100">
                  {providerSuites.map((suite) => (
                    <div
                      key={suite.id}
                      className={`flex items-center gap-2 px-2.5 py-1.5 cursor-pointer transition-colors ${
                        suite.id === selectedSuiteId
                          ? "bg-slate-100 border-l-2 border-slate-600"
                          : "hover:bg-slate-50 border-l-2 border-transparent"
                      }`}
                      onClick={() => onSelectSuite(suite.id)}
                    >
                      <div className="min-w-0 flex-1">
                        <div
                          className="truncate text-sm font-medium text-slate-900"
                          title={suite.name}
                        >
                          {suite.name}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <code className="truncate text-xs text-slate-500" title={suite.endpoint}>
                            {suite.endpoint}
                          </code>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                            suite.status === "active"
                              ? "bg-green-100 text-green-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {suite.status}
                        </span>
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-medium text-slate-700">
                          v{suite.latest_version}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {providers.length === 0 && (
          <div className="py-8 text-center">
            <svg
              className="mx-auto h-10 w-10 text-slate-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="mt-2 text-sm text-slate-500">
              {searchQuery ? "No matching suites" : "No suites available"}
            </p>
            {!searchQuery && (
              <button
                onClick={onCreateSuite}
                className="mt-1 text-sm text-slate-600 hover:text-slate-800 underline"
              >
                Create your first suite
              </button>
            )}
          </div>
        )}
      </div>

      {/* Create Button */}
      <div className="flex-shrink-0 pt-2 border-t border-slate-200 mt-2">
        <button
          onClick={onCreateSuite}
          className="flex w-full items-center justify-center gap-1.5 rounded bg-slate-700 py-2 text-sm font-medium text-white hover:bg-slate-800 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Suite
        </button>
      </div>
    </div>
  );
}
