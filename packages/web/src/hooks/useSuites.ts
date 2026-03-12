import { useCallback, useEffect, useMemo, useState } from "react";
import { getSuites, refreshSuiteRegistryCache } from "../api";
import type { Suite, TestSelectionMap } from "../types";

export function useSuites() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);
  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set<string>());
  const [selectedSuiteIds, setSelectedSuiteIds] = useState<Set<string>>(new Set<string>());
  const [selectedTestsBySuite, setSelectedTestsBySuite] = useState<TestSelectionMap>({});
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set<string>());
  const [expandedSuites, setExpandedSuites] = useState<Set<string>>(new Set<string>());
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshingRegistryCache, setIsRefreshingRegistryCache] = useState(false);

  const providers = useMemo(
    () => Array.from(new Set(suites.map((s) => s.provider_id))).sort(),
    [suites]
  );

  const visibleSuites = useMemo(
    () => suites.filter((suite) => selectedProviders.has(suite.provider_id)),
    [selectedProviders, suites]
  );

  const visibleSuiteIds = useMemo(() => new Set(visibleSuites.map((s) => s.suite_id)), [visibleSuites]);

  const selectedTestCount = useMemo(
    () => Object.values(selectedTestsBySuite).reduce((acc, bucket) => acc + bucket.size, 0),
    [selectedTestsBySuite]
  );

  const getSuiteById = useCallback(
    (suiteId: string) => suites.find((s) => s.suite_id === suiteId),
    [suites]
  );

  const loadSuites = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const nextSuites = await getSuites();
      setSuites(nextSuites);

      setSelectedSuiteId((prev) => {
        if (!nextSuites.length) return null;
        if (prev && nextSuites.some((s) => s.suite_id === prev)) return prev;
        return nextSuites[0].suite_id;
      });

      setSelectedProviders((prev) => {
        if (prev.size > 0) return prev;
        return new Set(nextSuites.map((s) => s.provider_id));
      });

      setExpandedProviders((prev) => {
        if (prev.size > 0) return prev;
        const first = nextSuites[0]?.provider;
        return first ? new Set([first]) : prev;
      });

      setSelectedSuiteIds((prev) => {
        const valid = new Set(nextSuites.map((s) => s.suite_id));
        return new Set(Array.from(prev).filter((id) => valid.has(id)));
      });

      setSelectedTestsBySuite((prev) => {
        const valid = new Set(nextSuites.map((s) => s.suite_id));
        const next: TestSelectionMap = {};
        Object.entries(prev).forEach(([suiteId, bucket]) => {
          if (valid.has(suiteId)) next[suiteId] = new Set(bucket);
        });
        return next;
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshRegistryCache = useCallback(async (): Promise<{
    status: string;
    suite_count: number;
    version_count: number;
  }> => {
    setIsRefreshingRegistryCache(true);
    try {
      const result = await refreshSuiteRegistryCache();
      await loadSuites();
      return result;
    } finally {
      setIsRefreshingRegistryCache(false);
    }
  }, [loadSuites]);

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

  useEffect(() => {
    void loadSuites();
  }, [loadSuites]);

  return {
    suites,
    selectedSuiteId,
    selectedProviders,
    selectedSuiteIds,
    selectedTestsBySuite,
    expandedProviders,
    expandedSuites,
    isLoading,
    isRefreshingRegistryCache,
    providers,
    visibleSuites,
    visibleSuiteIds,
    selectedTestCount,
    getSuiteById,
    loadSuites,
    refreshRegistryCache,
    setSelectedSuiteId,
    setSelectedProviders,
    toggleProvider,
    selectAllProviders,
    clearAllProviders,
    toggleProviderPanel,
    toggleSuite,
    toggleSuitePanel,
    toggleTest,
    setSelectedSuiteIds,
    setSelectedTestsBySuite,
  };
}
