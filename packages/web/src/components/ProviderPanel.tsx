import type { Suite, TestSelectionMap } from "../types";
import { getTestRows, isDuplicateName } from "../utils";
import { SuiteCard } from "./SuiteCard";

interface ProviderPanelProps {
  provider: string;
  suites: Suite[];
  selectedSuiteIds: Set<string>;
  selectedTestsBySuite: TestSelectionMap;
  expandedSuites: Set<string>;
  expanded: boolean;
  onToggleSuite: (suiteId: string) => void;
  onToggleSuitePanel: (suiteId: string) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onTogglePanel: () => void;
}

export function ProviderPanel({
  provider,
  suites,
  selectedSuiteIds,
  selectedTestsBySuite,
  expandedSuites,
  expanded,
  onToggleSuite,
  onToggleSuitePanel,
  onToggleTest,
  onTogglePanel,
}: ProviderPanelProps) {
  const selectedRouteCount = suites.filter((s) => selectedSuiteIds.has(s.suite_id)).length;

  return (
    <div className="rounded-xl border border-slate-300 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <strong className="text-2xl font-semibold leading-none text-slate-900">{provider}</strong>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>
            {selectedRouteCount}/{suites.length} routes
          </span>
          <button
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs"
            onClick={onTogglePanel}
          >
            {expanded ? "▾" : "▸"}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-2 flex flex-col">
          {suites.map((suite) => {
            const tests = getTestRows(suite);
            const selectedTests = selectedTestsBySuite[suite.suite_id] ?? new Set<string>();
            const testsExpanded = expandedSuites.has(suite.suite_id);
            const suiteName = suite.suite_name || suite.model_id;
            const endpoint = suite.endpoint;
            const duplicateName = isDuplicateName(suiteName, suite.provider_id, endpoint);

            return (
              <SuiteCard
                key={suite.suite_id}
                suite={suite}
                tests={tests}
                selectedTests={selectedTests}
                selectedSuiteIds={selectedSuiteIds}
                testsExpanded={testsExpanded}
                duplicateName={duplicateName}
                onToggleSuite={onToggleSuite}
                onToggleSuitePanel={onToggleSuitePanel}
                onToggleTest={onToggleTest}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
