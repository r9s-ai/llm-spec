import { useState, useMemo, useCallback } from "react";
import { createSuite, createVersion, deleteSuite, updateSuite } from "../api";
import { useAppContext } from "../context";
import { SuiteTree, SuiteEditor, CreateSuiteModal } from "../components";

export function SuitesPage() {
  const { setNotice, suites } = useAppContext();
  const {
    suites: suiteList,
    versionsBySuite,
    selectedSuiteId,
    selectedVersionBySuite,
    loadSuites,
    refreshVersions,
    setSelectedSuiteId,
    setSelectedVersionBySuite,
    setSelectedSuiteIds,
    setSelectedTestsBySuite,
    getSuiteById,
  } = suites;

  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

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

  // Handle create suite
  const handleCreateSuite = useCallback(
    async (provider: string, endpoint: string, name: string) => {
      const raw = `{
  provider: "${provider}",
  endpoint: "${endpoint}",
  schemas: {},
  base_params: {},
  tests: [{ name: "test_baseline", is_baseline: true }]
}`;

      await createSuite({ provider, endpoint, name, raw_json5: raw, created_by: "web-ui" });
      await loadSuites();
      setNotice("Suite created successfully.");
    },
    [loadSuites, setNotice]
  );

  // Handle update meta
  const handleUpdateMeta = useCallback(
    async (name: string, status: "active" | "archived") => {
      if (!selectedSuite) return;
      await updateSuite(selectedSuite.id, { name, status });
      await loadSuites();
      setNotice("Suite metadata updated.");
    },
    [selectedSuite, loadSuites, setNotice]
  );

  // Handle delete suite
  const handleDeleteSuite = useCallback(async () => {
    if (!selectedSuite) return;

    await deleteSuite(selectedSuite.id);
    await loadSuites();

    // Clear selection
    setSelectedSuiteId(null);
    setSelectedSuiteIds((prev) => {
      const next = new Set(prev);
      next.delete(selectedSuite.id);
      return next;
    });
    setSelectedTestsBySuite((prev) => {
      const next = { ...prev };
      delete next[selectedSuite.id];
      return next;
    });
    setSelectedVersionBySuite((prev) => {
      const next = { ...prev };
      delete next[selectedSuite.id];
      return next;
    });

    setNotice("Suite deleted.");
  }, [
    selectedSuite,
    loadSuites,
    setSelectedSuiteId,
    setSelectedSuiteIds,
    setSelectedTestsBySuite,
    setSelectedVersionBySuite,
    setNotice,
  ]);

  // Handle save new version
  const handleSaveVersion = useCallback(
    async (rawJson5: string) => {
      if (!selectedSuite) return;

      await createVersion(selectedSuite.id, { raw_json5: rawJson5, created_by: "web-ui" });
      const vers = await refreshVersions(selectedSuite.id);
      setSelectedVersionBySuite((prev) => ({ ...prev, [selectedSuite.id]: vers[0]?.id ?? "" }));
      await loadSuites();
      setNotice("New version saved.");
    },
    [selectedSuite, refreshVersions, setSelectedVersionBySuite, loadSuites, setNotice]
  );

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Left Panel - Suite Tree */}
      <div className="w-[320px] flex-shrink-0 border-r border-slate-200 bg-slate-50">
        <div className="h-full overflow-auto p-1.5">
          <SuiteTree
            suites={suiteList}
            selectedSuiteId={selectedSuiteId}
            searchQuery={searchQuery}
            onSelectSuite={handleSelectSuite}
            onSearchChange={setSearchQuery}
            onCreateSuite={() => setIsCreateModalOpen(true)}
          />
        </div>
      </div>

      {/* Right Panel - Suite Editor */}
      <div className="flex-1 flex flex-col bg-slate-50">
        <div className="flex-1 min-h-0 p-1.5">
          <SuiteEditor
            suite={selectedSuite}
            versions={versions}
            selectedVersionId={selectedVersionId}
            onSelectVersion={handleSelectVersion}
            onUpdateMeta={handleUpdateMeta}
            onDeleteSuite={handleDeleteSuite}
            onSaveVersion={handleSaveVersion}
          />
        </div>
      </div>

      {/* Create Suite Modal */}
      <CreateSuiteModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={handleCreateSuite}
      />
    </div>
  );
}
