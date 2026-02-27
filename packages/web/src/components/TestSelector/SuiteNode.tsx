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
      (t) =>
        t.name.toLowerCase().includes(query) ||
        t.paramName.toLowerCase().includes(query) ||
        t.tags.some((tag) => tag.toLowerCase().includes(query))
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
    <div className="rounded-sm border border-slate-200/40 bg-white/80">
      {/* Route Header */}
      <div className="flex items-center gap-0.5 px-1 py-0.5 hover:bg-slate-50">
        {/* Expand Button */}
        <button
          onClick={onToggleExpanded}
          className="flex h-3.5 w-3.5 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <svg
            className={`h-2.5 w-2.5 transition-transform ${isExpanded ? "rotate-90" : ""}`}
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

        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-medium leading-tight text-slate-700" title={suite.route}>
            {suite.route}
          </div>
          <div className="truncate text-[10px] leading-tight text-slate-400" title={suite.endpoint}>
            {suite.endpoint}
          </div>
        </div>

        {/* Count Badge - Compact */}
        <span
          className={`shrink-0 rounded-sm px-1 text-[10px] font-medium leading-tight ${
            isAllSelected
              ? "bg-green-100 text-green-700"
              : isIndeterminate
                ? "bg-amber-100 text-amber-700"
                : "bg-slate-100 text-slate-500"
          }`}
        >
          {selectedCount}/{tests.length}
        </span>
      </div>

      {/* Tests List - Very compact */}
      {isExpanded && filteredTests.length > 0 && (
        <div className="border-t border-slate-100 py-0.5">
          {filteredTests.map((test) => (
            <TestNode
              key={test.name}
              testName={test.name}
              tags={test.tags}
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
