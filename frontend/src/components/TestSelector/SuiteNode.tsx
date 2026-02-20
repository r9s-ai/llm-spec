import { useMemo } from "react";
import { Checkbox } from "../UI";
import { TestNode } from "./TestNode";
import type { Suite, SuiteVersion, TestRow } from "../../types";

interface SuiteNodeProps {
  suite: Suite;
  version: SuiteVersion | undefined;
  tests: TestRow[];
  selectedTests: Set<string>;
  isExpanded: boolean;
  searchQuery: string;
  onToggleExpanded: () => void;
  onToggleTests: (testNames: string[], checked: boolean) => void;
  onToggleTest: (testName: string, checked: boolean) => void;
}

export function SuiteNode({
  suite,
  tests,
  selectedTests,
  isExpanded,
  searchQuery,
  onToggleExpanded,
  onToggleTests,
  onToggleTest,
}: SuiteNodeProps) {
  const selectedCount = tests.filter((t) => selectedTests.has(t.name)).length;
  const isAllSelected = selectedCount === tests.length && tests.length > 0;
  const isIndeterminate = selectedCount > 0 && selectedCount < tests.length;

  const filteredTests = useMemo(() => {
    if (!searchQuery) return tests;
    const query = searchQuery.toLowerCase();
    return tests.filter(
      (t) => t.name.toLowerCase().includes(query) || t.paramName.toLowerCase().includes(query)
    );
  }, [tests, searchQuery]);

  const handleCheckboxChange = (checked: boolean) => {
    onToggleTests(
      tests.map((t) => t.name),
      checked
    );
  };

  if (searchQuery && filteredTests.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      {/* Suite Header */}
      <div className="flex items-center gap-2 px-3 py-2 transition-colors hover:bg-slate-50">
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

        {/* Suite Info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900" title={suite.endpoint}>
              {suite.endpoint}
            </span>
          </div>
          <span className="text-xs text-slate-500">{suite.name}</span>
        </div>

        {/* Count Badge */}
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
            {selectedCount}/{tests.length}
          </span>
        </div>
      </div>

      {/* Tests List */}
      {isExpanded && filteredTests.length > 0 && (
        <div className="border-t border-slate-100 py-1">
          {filteredTests.map((test) => (
            <TestNode
              key={test.name}
              testName={test.name}
              paramName={test.paramName}
              valueText={test.valueText}
              isSelected={selectedTests.has(test.name)}
              isHighlighted={
                !!searchQuery && test.name.toLowerCase().includes(searchQuery.toLowerCase())
              }
              onToggle={(checked) => onToggleTest(test.name, checked)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
