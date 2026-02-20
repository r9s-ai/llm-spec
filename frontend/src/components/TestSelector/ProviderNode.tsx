import { useMemo } from "react";
import { Checkbox } from "../UI";
import { SuiteNode } from "./SuiteNode";
import type { Suite, TestSelectionMap, VersionsMap } from "../../types";
import { getTestRows, getVersionById } from "../../utils";

interface ProviderNodeProps {
  provider: string;
  suites: Suite[];
  versionsBySuite: VersionsMap;
  selectedVersionBySuite: Record<string, string>;
  selectedTestsBySuite: TestSelectionMap;
  expandedSuites: Set<string>;
  isExpanded: boolean;
  searchQuery: string;
  onToggleExpanded: () => void;
  onToggleSuiteExpanded: (suiteId: string) => void;
  onToggleTests: (suiteId: string, testNames: string[], checked: boolean) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
}

export function ProviderNode({
  provider,
  suites,
  versionsBySuite,
  selectedVersionBySuite,
  selectedTestsBySuite,
  expandedSuites,
  isExpanded,
  searchQuery,
  onToggleExpanded,
  onToggleSuiteExpanded,
  onToggleTests,
  onToggleTest,
}: ProviderNodeProps) {
  // Calculate selection state for this provider
  const { totalTests, selectedTests, isAllSelected, isIndeterminate } = useMemo(() => {
    let total = 0;
    let selected = 0;

    suites.forEach((suite) => {
      const versions = versionsBySuite[suite.id] ?? [];
      const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
      const version = getVersionById(versionsBySuite, suite.id, versionId);
      const tests = getTestRows(version);
      total += tests.length;
      const suiteSelected = selectedTestsBySuite[suite.id] ?? new Set<string>();
      selected += tests.filter((t) => suiteSelected.has(t.name)).length;
    });

    return {
      totalTests: total,
      selectedTests: selected,
      isAllSelected: total > 0 && selected === total,
      isIndeterminate: selected > 0 && selected < total,
    };
  }, [suites, versionsBySuite, selectedVersionBySuite, selectedTestsBySuite]);

  const handleCheckboxChange = (checked: boolean) => {
    suites.forEach((suite) => {
      const versions = versionsBySuite[suite.id] ?? [];
      const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
      const version = getVersionById(versionsBySuite, suite.id, versionId);
      const tests = getTestRows(version);
      onToggleTests(
        suite.id,
        tests.map((t) => t.name),
        checked
      );
    });
  };

  // Filter suites by search query
  const filteredSuites = useMemo(() => {
    if (!searchQuery) return suites;
    return suites.filter((suite) => {
      const versions = versionsBySuite[suite.id] ?? [];
      const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
      const version = getVersionById(versionsBySuite, suite.id, versionId);
      const tests = getTestRows(version);
      const query = searchQuery.toLowerCase();
      return (
        suite.endpoint.toLowerCase().includes(query) ||
        suite.name.toLowerCase().includes(query) ||
        tests.some(
          (t) => t.name.toLowerCase().includes(query) || t.paramName.toLowerCase().includes(query)
        )
      );
    });
  }, [suites, versionsBySuite, selectedVersionBySuite, searchQuery]);

  if (searchQuery && filteredSuites.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white mb-2">
      {/* Provider Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 transition-colors hover:bg-slate-50">
        {/* Expand Button */}
        <button
          onClick={onToggleExpanded}
          className="flex h-6 w-6 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <svg
            className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        {/* Checkbox */}
        <Checkbox
          checked={isAllSelected}
          indeterminate={isIndeterminate}
          onChange={(e) => handleCheckboxChange(e.target.checked)}
        />

        {/* Provider Name */}
        <span className="text-base font-bold text-slate-900">{provider}</span>

        {/* Count Badge */}
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
          {selectedTests}/{totalTests}
        </span>

        {/* Suite Count */}
        <span className="ml-auto text-xs text-slate-500">{suites.length} routes</span>
      </div>

      {/* Suites List */}
      {isExpanded && filteredSuites.length > 0 && (
        <div className="space-y-1 border-t border-slate-100 p-2">
          {filteredSuites
            .sort((a, b) => a.endpoint.localeCompare(b.endpoint))
            .map((suite) => {
              const versions = versionsBySuite[suite.id] ?? [];
              const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
              const version = getVersionById(versionsBySuite, suite.id, versionId);
              const tests = getTestRows(version);
              const selectedTests = selectedTestsBySuite[suite.id] ?? new Set<string>();
              const isSuiteExpanded = expandedSuites.has(suite.id);

              return (
                <SuiteNode
                  key={suite.id}
                  suite={suite}
                  version={version}
                  tests={tests}
                  selectedTests={selectedTests}
                  isExpanded={isSuiteExpanded}
                  searchQuery={searchQuery}
                  onToggleExpanded={() => onToggleSuiteExpanded(suite.id)}
                  onToggleTests={(testNames, checked) =>
                    onToggleTests(suite.id, testNames, checked)
                  }
                  onToggleTest={(testName, checked) => onToggleTest(suite.id, testName, checked)}
                />
              );
            })}
        </div>
      )}
    </div>
  );
}
