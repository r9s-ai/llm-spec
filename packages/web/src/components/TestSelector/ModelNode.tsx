import { useMemo } from "react";
import { Checkbox } from "../UI";
import { SuiteNode } from "./SuiteNode";
import type { Suite, TestSelectionMap, VersionsMap } from "../../types";
import { getTestRows, getVersionById } from "../../utils";

interface ModelNodeProps {
  model: string;
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

export function ModelNode({
  model,
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
}: ModelNodeProps) {
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

  const uniqueRouteCount = useMemo(() => new Set(suites.map((suite) => suite.route)).size, [suites]);

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

  return (
    <div className="rounded-md border border-slate-200/70 bg-white">
      <div className="flex items-center gap-1.5 border-b border-slate-100 bg-slate-50 px-2 py-1">
        <button
          onClick={onToggleExpanded}
          className="flex h-4 w-4 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <svg
            className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        <Checkbox
          checked={isAllSelected}
          indeterminate={isIndeterminate}
          onChange={(e) => handleCheckboxChange(e.target.checked)}
        />

        <span className="truncate text-sm font-semibold text-slate-800">{model}</span>

        <span
          className={`rounded-full px-1.5 py-0.5 text-[11px] font-medium ${
            isIndeterminate || isAllSelected
              ? "bg-violet-100 text-violet-700"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {selectedTests}/{totalTests}
        </span>

        <span className="ml-auto text-[11px] text-slate-400">{uniqueRouteCount} routes</span>
      </div>

      {isExpanded && (
        <div className="space-y-0.5 p-1">
          {suites
            .sort((a, b) => a.route.localeCompare(b.route) || a.endpoint.localeCompare(b.endpoint))
            .map((suite) => {
              const versions = versionsBySuite[suite.id] ?? [];
              const versionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
              const version = getVersionById(versionsBySuite, suite.id, versionId);
              const tests = getTestRows(version);
              const selectedTestsForSuite = selectedTestsBySuite[suite.id] ?? new Set<string>();
              const isSuiteExpanded = expandedSuites.has(suite.id);

              return (
                <SuiteNode
                  key={suite.id}
                  suite={suite}
                  version={version}
                  tests={tests}
                  selectedTests={selectedTestsForSuite}
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
