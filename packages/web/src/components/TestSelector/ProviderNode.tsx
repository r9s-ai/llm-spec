import { useMemo, useState, useCallback } from "react";
import { Checkbox } from "../UI";
import { ModelNode } from "./ModelNode";
import type { Suite, TestSelectionMap } from "../../types";
import { getTestRows } from "../../utils";

interface ProviderNodeProps {
  provider: string;
  suites: Suite[];
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
  selectedTestsBySuite,
  expandedSuites,
  isExpanded,
  searchQuery,
  onToggleExpanded,
  onToggleSuiteExpanded,
  onToggleTests,
  onToggleTest,
}: ProviderNodeProps) {
  const { totalTests, selectedTests, isAllSelected, isIndeterminate } = useMemo(() => {
    let total = 0;
    let selected = 0;

    suites.forEach((suite) => {
      const tests = getTestRows(suite);
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
  }, [suites, selectedTestsBySuite]);

  const handleCheckboxChange = (checked: boolean) => {
    suites.forEach((suite) => {
      const tests = getTestRows(suite);
      onToggleTests(
        suite.id,
        tests.map((t) => t.name),
        checked
      );
    });
  };

  const filteredSuites = useMemo(() => {
    if (!searchQuery) return suites;
    return suites.filter((suite) => {
      const tests = getTestRows(suite);
      const query = searchQuery.toLowerCase();
      const route = String(suite.route_suite.route ?? "").toLowerCase();
      const endpoint = String(suite.route_suite.endpoint ?? "").toLowerCase();
      const suiteName = String(suite.route_suite.suite_name ?? "").toLowerCase();
      return (
        route.includes(query) ||
        endpoint.includes(query) ||
        suiteName.includes(query) ||
        tests.some(
          (t) =>
            t.name.toLowerCase().includes(query) ||
            t.paramName.toLowerCase().includes(query) ||
            t.tags.some((tag) => tag.toLowerCase().includes(query))
        )
      );
    });
  }, [suites, searchQuery]);

  const suitesByModel = useMemo(() => {
    const grouped: Record<string, Suite[]> = {};
    filteredSuites.forEach((suite) => {
      if (!grouped[suite.model_name]) {
        grouped[suite.model_name] = [];
      }
      grouped[suite.model_name].push(suite);
    });
    return grouped;
  }, [filteredSuites]);

  const modelNames = useMemo(() => Object.keys(suitesByModel).sort(), [suitesByModel]);
  const uniqueRouteCount = useMemo(
    () => new Set(suites.map((suite) => String(suite.route_suite.route ?? ""))).size,
    [suites]
  );

  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set<string>());

  const effectiveExpandedModels = useMemo(() => {
    if (searchQuery) {
      return new Set(modelNames);
    }

    return new Set(Array.from(expandedModels).filter((name) => modelNames.includes(name)));
  }, [expandedModels, searchQuery, modelNames]);

  const handleToggleModelExpanded = useCallback(
    (model: string) => {
      if (searchQuery) return;
      setExpandedModels((prev) => {
        const next = new Set(prev);
        if (next.has(model)) next.delete(model);
        else next.add(model);
        return next;
      });
    },
    [searchQuery]
  );

  if (modelNames.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white mb-1.5 overflow-hidden">
      <div className="flex items-center gap-1.5 px-2 py-1.5 bg-slate-50 border-b border-slate-100">
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

        <Checkbox
          checked={isAllSelected}
          indeterminate={isIndeterminate}
          onChange={(e) => handleCheckboxChange(e.target.checked)}
        />

        <span className="text-base font-bold text-slate-900">{provider}</span>

        <span
          className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${
            isIndeterminate || isAllSelected
              ? "bg-violet-100 text-violet-700"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {selectedTests}/{totalTests}
        </span>

        <span className="ml-auto text-xs text-slate-400">
          {modelNames.length} models · {uniqueRouteCount} routes
        </span>
      </div>

      {isExpanded && (
        <div className="space-y-0.5 p-1">
          {modelNames.map((model) => (
            <ModelNode
              key={`${provider}:${model}`}
              model={model}
              suites={suitesByModel[model] ?? []}
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
