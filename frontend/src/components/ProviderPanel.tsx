import type { Suite, TestSelectionMap, VersionsMap } from "../types";
import { getTestRows, getVersionById, isDuplicateName } from "../utils";
import { SuiteCard } from "./SuiteCard";

interface ProviderPanelProps {
  provider: string;
  suites: Suite[];
  versionsBySuite: VersionsMap;
  selectedSuiteIds: Set<string>;
  selectedVersionBySuite: Record<string, string>;
  selectedTestsBySuite: TestSelectionMap;
  expandedSuites: Set<string>;
  expanded: boolean;
  onToggleSuite: (suiteId: string) => void;
  onToggleSuitePanel: (suiteId: string) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onSelectVersion: (suiteId: string, versionId: string) => void;
  onTogglePanel: () => void;
}

export function ProviderPanel({
  provider,
  suites,
  versionsBySuite,
  selectedSuiteIds,
  selectedVersionBySuite,
  selectedTestsBySuite,
  expandedSuites,
  expanded,
  onToggleSuite,
  onToggleSuitePanel,
  onToggleTest,
  onSelectVersion,
  onTogglePanel,
}: ProviderPanelProps) {
  const selectedRouteCount = suites.filter((s) => selectedSuiteIds.has(s.id)).length;

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
            const versions = versionsBySuite[suite.id] ?? [];
            const selectedVersionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
            const version = getVersionById(versionsBySuite, suite.id, selectedVersionId);
            const tests = getTestRows(version);
            const selectedTests = selectedTestsBySuite[suite.id] ?? new Set<string>();
            const testsExpanded = expandedSuites.has(suite.id);
            const duplicateName = isDuplicateName(suite.name, suite.provider, suite.endpoint);

            return (
              <SuiteCard
                key={suite.id}
                suite={suite}
                versions={versions}
                version={version}
                tests={tests}
                selectedTests={selectedTests}
                selectedSuiteIds={selectedSuiteIds}
                selectedVersionId={selectedVersionId}
                testsExpanded={testsExpanded}
                duplicateName={duplicateName}
                onToggleSuite={onToggleSuite}
                onToggleSuitePanel={onToggleSuitePanel}
                onToggleTest={onToggleTest}
                onSelectVersion={onSelectVersion}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
