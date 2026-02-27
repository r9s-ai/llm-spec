import { useMemo, useState, useCallback } from "react";
import { Checkbox } from "../UI";
import { ModelNode } from "./ModelNode";
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
          (t) =>
            t.name.toLowerCase().includes(query) ||
            t.paramName.toLowerCase().includes(query) ||
            t.tags.some((tag) => tag.toLowerCase().includes(query))
        )
      );
    });
  }, [suites, versionsBySuite, selectedVersionBySuite, searchQuery]);

  const suitesByModel = useMemo(() => {
    const grouped: Record<string, Suite[]> = {};
    filteredSuites.forEach((suite) => {
      if (!grouped[suite.model]) {
        grouped[suite.model] = [];
      }
      grouped[suite.model].push(suite);
    });
    return grouped;
  }, [filteredSuites]);

  const modelNames = useMemo(() => Object.keys(suitesByModel).sort(), [suitesByModel]);
  const uniqueRouteCount = useMemo(() => new Set(suites.map((suite) => suite.route)).size, [suites]);

  // Keep model expansion state local to each provider panel.
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set<string>());

  const effectiveExpandedModels = useMemo(() => {
    if (searchQuery) {
      return new Set(modelNames);
    }

    return new Set(Array.from(expandedModels).filter((name) => modelNames.includes(name)));
  }, [expandedModels, searchQuery, modelNames]);

  const handleToggleModelExpanded = useCallback((model: string) => {
    if (searchQuery) return;
    setExpandedModels((prev) => {
      const next = new Set(prev);
      if (next.has(model)) next.delete(model);
      else next.add(model);
      return next;
    });
  }, [searchQuery]);

  if (modelNames.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white mb-1.5 overflow-hidden">
      {/* Provider Header - Compact */}
      <div className="flex items-center gap-1.5 px-2 py-1.5 bg-slate-50 border-b border-slate-100">
        {/* Expand Button */}
        <button
          onClick={onToggleExpanded}
          className="flex h-5 w-5 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <svg
            className={`h-3.5 w-3.5 transition-transform ${isExpanded ? "rotate-90" : ""}`}
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

        {/* Provider Name - Large, black, bold */}
        <span className="text-base font-bold text-slate-900">{provider}</span>

        {/* Count Badge */}
        <span
          className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${
            isIndeterminate || isAllSelected
              ? "bg-violet-100 text-violet-700"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {selectedTests}/{totalTests}
        </span>

        {/* Model/Route Count */}
        <span className="ml-auto text-xs text-slate-400">
          {modelNames.length} models · {uniqueRouteCount} routes
        </span>
      </div>

      {/* Model List */}
      {isExpanded && (
        <div className="space-y-0.5 p-1">
          {modelNames.map((model) => (
            <ModelNode
              key={`${provider}:${model}`}
              model={model}
              suites={suitesByModel[model] ?? []}
              versionsBySuite={versionsBySuite}
              selectedVersionBySuite={selectedVersionBySuite}
              selectedTestsBySuite={selectedTestsBySuite}
              expandedSuites={expandedSuites}
              isExpanded={effectiveExpandedModels.has(model)}
              searchQuery={searchQuery}
              onToggleExpanded={() => handleToggleModelExpanded(model)}
              onToggleSuiteExpanded={onToggleSuiteExpanded}
              onToggleTests={onToggleTests}
              onToggleTest={onToggleTest}
            />
          ))}
        </div>
      )}
    </div>
  );
}
