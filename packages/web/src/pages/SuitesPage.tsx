import { useState, useMemo, useCallback } from "react";
import { useAppContext } from "../context";
import { SuiteTree, SuiteEditor } from "../components";

export function SuitesPage() {
  const { suites } = useAppContext();
  const {
    suites: suiteList,
    versionsBySuite,
    selectedSuiteId,
    selectedVersionBySuite,
    refreshVersions,
    setSelectedSuiteId,
    setSelectedVersionBySuite,
    getSuiteById,
  } = suites;

  const [searchQuery, setSearchQuery] = useState("");

  // Get selected suite
  const selectedSuite = useMemo(() => {
    if (!selectedSuiteId) return null;
    return getSuiteById(selectedSuiteId) ?? null;
  }, [getSuiteById, selectedSuiteId]);

  // Get versions for selected suite
  const versions = selectedSuite ? (versionsBySuite[selectedSuite.id] ?? []) : [];
  const selectedVersionId = selectedSuite
    ? (selectedVersionBySuite[selectedSuite.id] ?? null)
    : null;

  // Handle suite selection
  const handleSelectSuite = useCallback(
    async (suiteId: string) => {
      setSelectedSuiteId(suiteId);
      const vers = await refreshVersions(suiteId);
      if (vers[0]) {
        setSelectedVersionBySuite((prev) => ({ ...prev, [suiteId]: vers[0].id }));
      }
    },
    [refreshVersions, setSelectedSuiteId, setSelectedVersionBySuite]
  );

  // Handle version selection
  const handleSelectVersion = useCallback(
    (versionId: string) => {
      if (!selectedSuite) return;
      setSelectedVersionBySuite((prev) => ({
        ...prev,
        [selectedSuite.id]: versionId,
      }));
    },
    [selectedSuite, setSelectedVersionBySuite]
  );

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Left Panel - Suite Tree */}
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

      {/* Right Panel - Suite Editor */}
      <div className="flex-1 overflow-auto bg-slate-50">
        <div className="h-full p-4">
          <SuiteEditor
            suite={selectedSuite}
            versions={versions}
            selectedVersionId={selectedVersionId}
            onSelectVersion={handleSelectVersion}
          />
        </div>
      </div>
    </div>
  );
}
