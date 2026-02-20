import { useCallback, useEffect, useMemo, useState } from "react";
import { getSuites, listVersions } from "../api";
import type { Suite, SuiteVersion, TestSelectionMap, VersionsMap } from "../types";

export function useSuites() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [versionsBySuite, setVersionsBySuite] = useState<VersionsMap>({});
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set<string>());
  const [selectedSuiteIds, setSelectedSuiteIds] = useState<Set<string>>(new Set<string>());
  const [selectedVersionBySuite, setSelectedVersionBySuite] = useState<Record<string, string>>({});
  const [selectedTestsBySuite, setSelectedTestsBySuite] = useState<TestSelectionMap>({});
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set<string>());
  const [expandedSuites, setExpandedSuites] = useState<Set<string>>(new Set<string>());

  // Derived data
  const providers = useMemo(
    () => Array.from(new Set(suites.map((s) => s.provider))).sort(),
    [suites]
  );

  const visibleSuites = useMemo(
    () => suites.filter((suite) => selectedProviders.has(suite.provider)),
    [selectedProviders, suites]
  );

  const visibleSuiteIds = useMemo(() => new Set(visibleSuites.map((s) => s.id)), [visibleSuites]);

  const selectedTestCount = useMemo(
    () => Object.values(selectedTestsBySuite).reduce((acc, bucket) => acc + bucket.size, 0),
    [selectedTestsBySuite]
  );

  const getSuiteById = useCallback(
    (suiteId: string) => suites.find((s) => s.id === suiteId),
    [suites]
  );

  // Load data
  const loadSuites = useCallback(async (): Promise<void> => {
    const nextSuites = await getSuites();
    const versionsEntries = await Promise.all(
      nextSuites.map(async (suite) => [suite.id, await listVersions(suite.id)] as const)
    );
    const nextVersionsBySuite = Object.fromEntries(versionsEntries) as VersionsMap;

    setSuites(nextSuites);
    setVersionsBySuite(nextVersionsBySuite);

    setSelectedSuiteId((prev) => {
      if (!nextSuites.length) return null;
      if (prev && nextSuites.some((s) => s.id === prev)) return prev;
      return nextSuites[0].id;
    });

    setSelectedProviders((prev) => {
      if (prev.size > 0) return prev;
      return new Set(nextSuites.map((s) => s.provider));
    });

    setExpandedProviders((prev) => {
      if (prev.size > 0) return prev;
      const first = nextSuites[0]?.provider;
      return first ? new Set([first]) : prev;
    });

    setSelectedVersionBySuite((prev) => {
      const next = { ...prev };
      nextSuites.forEach((suite) => {
        const versions = nextVersionsBySuite[suite.id] ?? [];
        if (!versions.length) return;
        const exists = versions.some((v) => v.id === next[suite.id]);
        if (!exists) next[suite.id] = versions[0].id;
      });
      return next;
    });

    setSelectedSuiteIds((prev) => {
      const valid = new Set(nextSuites.map((s) => s.id));
      return new Set(Array.from(prev).filter((id) => valid.has(id)));
    });

    setSelectedTestsBySuite((prev) => {
      const valid = new Set(nextSuites.map((s) => s.id));
      const next: TestSelectionMap = {};
      Object.entries(prev).forEach(([suiteId, bucket]) => {
        if (valid.has(suiteId)) next[suiteId] = new Set(bucket);
      });
      return next;
    });
  }, []);

  // Refresh versions for a single suite
  const refreshVersions = useCallback(async (suiteId: string): Promise<SuiteVersion[]> => {
    const versions = await listVersions(suiteId);
    setVersionsBySuite((prev) => ({ ...prev, [suiteId]: versions }));
    return versions;
  }, []);

  // Provider operations
  const toggleProvider = useCallback((provider: string): void => {
    setSelectedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) next.delete(provider);
      else next.add(provider);
      return next;
    });
    setExpandedProviders((prev) => {
      if (prev.has(provider)) return prev;
      return new Set(prev).add(provider);
    });
  }, []);

  const selectAllProviders = useCallback((): void => {
    setSelectedProviders(new Set(providers));
    setExpandedProviders(new Set(providers));
  }, [providers]);

  const clearAllProviders = useCallback((): void => {
    setSelectedProviders(new Set());
    setSelectedSuiteIds(new Set());
  }, []);

  const toggleProviderPanel = useCallback((provider: string): void => {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) next.delete(provider);
      else next.add(provider);
      return next;
    });
  }, []);

  // Suite operations
  const toggleSuite = useCallback((suiteId: string): void => {
    setSelectedSuiteIds((prev) => {
      const next = new Set(prev);
      if (next.has(suiteId)) next.delete(suiteId);
      else next.add(suiteId);
      return next;
    });
  }, []);

  const toggleSuitePanel = useCallback((suiteId: string): void => {
    setExpandedSuites((prev) => {
      const next = new Set(prev);
      if (next.has(suiteId)) next.delete(suiteId);
      else next.add(suiteId);
      return next;
    });
  }, []);

  // Test operations
  const toggleTest = useCallback((suiteId: string, testName: string, checked: boolean): void => {
    setSelectedTestsBySuite((prev) => {
      const next = { ...prev };
      const bucket = new Set(next[suiteId] ?? []);
      if (checked) bucket.add(testName);
      else bucket.delete(testName);
      next[suiteId] = bucket;
      return next;
    });
  }, []);

  // Version selection
  const selectVersion = useCallback((suiteId: string, versionId: string): void => {
    setSelectedVersionBySuite((prev) => ({ ...prev, [suiteId]: versionId }));
  }, []);

  // Initial load
  useEffect(() => {
    const init = async () => {
      await loadSuites();
    };
    void init();
  }, [loadSuites]);

  return {
    // State
    suites,
    versionsBySuite,
    selectedSuiteId,
    selectedProviders,
    selectedSuiteIds,
    selectedVersionBySuite,
    selectedTestsBySuite,
    expandedProviders,
    expandedSuites,

    // Derived data
    providers,
    visibleSuites,
    visibleSuiteIds,
    selectedTestCount,

    // Methods
    getSuiteById,
    loadSuites,
    refreshVersions,
    setSelectedSuiteId,
    toggleProvider,
    selectAllProviders,
    clearAllProviders,
    toggleProviderPanel,
    toggleSuite,
    toggleSuitePanel,
    toggleTest,
    selectVersion,
    setSelectedSuiteIds,
    setSelectedTestsBySuite,
    setSelectedVersionBySuite,
  };
}
