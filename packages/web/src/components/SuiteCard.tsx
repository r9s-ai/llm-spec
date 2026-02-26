import type { Suite, SuiteVersion, TestRow } from "../types";

interface SuiteCardProps {
  suite: Suite;
  versions: SuiteVersion[];
  version: SuiteVersion | undefined;
  tests: TestRow[];
  selectedTests: Set<string>;
  selectedSuiteIds: Set<string>;
  selectedVersionId: string | undefined;
  testsExpanded: boolean;
  duplicateName: boolean;
  onToggleSuite: (suiteId: string) => void;
  onToggleSuitePanel: (suiteId: string) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
  onSelectVersion: (suiteId: string, versionId: string) => void;
}

export function SuiteCard({
  suite,
  versions,
  tests,
  selectedTests,
  selectedSuiteIds,
  selectedVersionId,
  testsExpanded,
  duplicateName,
  onToggleSuite,
  onToggleSuitePanel,
  onToggleTest,
  onSelectVersion,
}: SuiteCardProps) {
  return (
    <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <label className="inline-flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold leading-5 text-slate-900">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 accent-violet-600"
            checked={selectedSuiteIds.has(suite.id)}
            onChange={() => onToggleSuite(suite.id)}
          />
          <strong className="truncate">{suite.route}</strong>
        </label>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">
            {selectedTests.size}/{tests.length} selected
          </span>
          <select
            className="h-8 w-24 rounded-lg border border-slate-300 bg-white px-2 text-xs font-medium text-slate-700"
            value={selectedVersionId ?? ""}
            onChange={(e) => onSelectVersion(suite.id, e.target.value)}
          >
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version}
              </option>
            ))}
          </select>
          <button
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs"
            onClick={() => onToggleSuitePanel(suite.id)}
          >
            {testsExpanded ? "▾" : "▸"}
          </button>
        </div>
      </div>

      {!duplicateName && (
        <div className="my-1 text-xs font-medium text-slate-500">
          {suite.name} · {suite.model} · {suite.endpoint}
        </div>
      )}

      {testsExpanded ? (
        <>
          <div className="flex flex-wrap gap-2">
            {tests.length ? (
              tests.map((test) => (
                <label
                  key={`${suite.id}:${test.name}`}
                  title={test.valueText}
                  className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-900"
                >
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 accent-violet-600"
                    checked={selectedTests.has(test.name)}
                    onChange={(e) => onToggleTest(suite.id, test.name, e.target.checked)}
                  />
                  {test.paramName}
                </label>
              ))
            ) : (
              <span className="text-xs text-slate-500">No test cases.</span>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
