import { useState, useMemo } from "react";
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

  const toggleProvider = (provider: string) => {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) {
        next.delete(provider);
      } else {
        next.add(provider);
      }
      return next;
    });
  };

  // Auto-expand all when searching
  const handleSearchChange = (value: string) => {
    onSearchChange(value);
    if (value) {
      setExpandedProviders(new Set(providers));
    }
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

      {/* Provider List */}
      <div className="flex-1 space-y-2 overflow-auto">
        {providers.map((provider) => {
          const providerSuites = filteredSuitesByProvider[provider] ?? [];
          const isExpanded = expandedProviders.has(provider);

          return (
            <div key={provider} className="rounded-xl border border-slate-200 bg-white">
              {/* Provider Header */}
              <div
                className="flex items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-slate-50"
                onClick={() => toggleProvider(provider)}
              >
                <svg
                  className={`h-4 w-4 text-slate-400 transition-transform ${
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
                <span className="text-sm font-bold text-slate-900">{provider}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {providerSuites.length} suites
                </span>
              </div>

              {/* Suite List */}
              {isExpanded && (
                <div className="border-t border-slate-100">
                  {providerSuites.map((suite) => (
                    <div
                      key={suite.id}
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors ${
                        suite.id === selectedSuiteId
                          ? "bg-violet-50 border-l-2 border-violet-500"
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
                        <div className="truncate text-xs text-slate-500" title={suite.endpoint}>
                          {suite.endpoint}
                        </div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                        v{suite.latest_version}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {providers.length === 0 && (
          <div className="py-8 text-center text-sm text-slate-500">
            {searchQuery ? "No matching suites" : "No suites available"}
          </div>
        )}
      </div>
    </div>
  );
}
