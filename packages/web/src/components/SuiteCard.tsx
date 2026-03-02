import type { Suite, TestRow } from "../types";

interface SuiteCardProps {
  suite: Suite;
  tests: TestRow[];
  selectedTests: Set<string>;
  selectedSuiteIds: Set<string>;
  testsExpanded: boolean;
  duplicateName: boolean;
  onToggleSuite: (suiteId: string) => void;
  onToggleSuitePanel: (suiteId: string) => void;
  onToggleTest: (suiteId: string, testName: string, checked: boolean) => void;
}

export function SuiteCard({
  suite,
  tests,
  selectedTests,
  selectedSuiteIds,
  testsExpanded,
  duplicateName,
  onToggleSuite,
  onToggleSuitePanel,
  onToggleTest,
}: SuiteCardProps) {
  const route = String(suite.route_suite.route ?? "");
  const endpoint = String(suite.route_suite.endpoint ?? "");
  const suiteName = String(suite.route_suite.suite_name ?? suite.model_name);

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
          <strong className="truncate">{route}</strong>
        </label>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">
            {selectedTests.size}/{tests.length} selected
          </span>
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
          {suiteName} · {suite.model_name} · {endpoint}
        </div>
      )}

      {testsExpanded ? (
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
      ) : null}
    </div>
  );
}
