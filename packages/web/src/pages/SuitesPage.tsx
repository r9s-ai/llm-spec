import { useState, useMemo, useCallback } from "react";
import { useAppContext } from "../context";
import { SuiteTree, SuiteEditor } from "../components";

export function SuitesPage() {
  const { suites } = useAppContext();
  const { suites: suiteList, selectedSuiteId, setSelectedSuiteId, getSuiteById } = suites;

  const [searchQuery, setSearchQuery] = useState("");

  const selectedSuite = useMemo(() => {
    if (!selectedSuiteId) return null;
    return getSuiteById(selectedSuiteId) ?? null;
  }, [getSuiteById, selectedSuiteId]);

  const handleSelectSuite = useCallback(
    async (suiteId: string) => {
      setSelectedSuiteId(suiteId);
    },
    [setSelectedSuiteId]
  );

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <div className="w-[360px] flex-shrink-0 border-r border-slate-200 bg-slate-50">
        <div className="h-full overflow-auto p-4">
          <SuiteTree
            suites={suiteList}
            selectedSuiteId={selectedSuiteId}
            searchQuery={searchQuery}
            onSelectSuite={handleSelectSuite}
            onSearchChange={setSearchQuery}
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-slate-50">
        <div className="h-full p-4">
          <SuiteEditor suite={selectedSuite} />
        </div>
      </div>
    </div>
  );
}
