import React, { createContext, useContext, useState } from "react";
import { useBatches, useRuns, useSettings, useSuites } from "../hooks";
import type { PageKey, RunMode } from "../types";

interface AppContextValue {
  // Page state
  page: PageKey;
  setPage: (page: PageKey) => void;
  notice: string;
  setNotice: (notice: string) => void;
  runMode: RunMode;
  setRunMode: (mode: RunMode) => void;

  // Suites
  suites: ReturnType<typeof useSuites>;

  // Runs (legacy, kept for backward compatibility)
  runs: ReturnType<typeof useRuns>;

  // Batches (new)
  batches: ReturnType<typeof useBatches>;

  // Settings
  settings: ReturnType<typeof useSettings>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState<PageKey>("testing");
  const [notice, setNotice] = useState<string>("");
  const [runMode, setRunMode] = useState<RunMode>("real");

  const suites = useSuites();
  const runs = useRuns();
  const batches = useBatches();
  const settings = useSettings();

  const value: AppContextValue = {
    page,
    setPage,
    notice,
    setNotice,
    runMode,
    setRunMode,
    suites,
    runs,
    batches,
    settings,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
}
