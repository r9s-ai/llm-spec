import { useCallback } from "react";
import { Header } from "./components";
import { AppProvider, useAppContext } from "./context";
import { TestingPage, SuitesPage, SettingsPage } from "./pages";
import type { PageKey } from "./types";

function AppContent(): JSX.Element {
  const { page, setPage, notice, settings } = useAppContext();

  const handleNavigate = useCallback(
    async (target: PageKey): Promise<void> => {
      setPage(target);
      if (target === "settings" && !settings.toml) {
        await settings.loadToml();
      }
    },
    [setPage, settings]
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <Header page={page} notice={notice} onNavigate={(p) => void handleNavigate(p)} />

      <main className="flex flex-col">
        {page === "testing" && <TestingPage />}
        {page === "suites" && (
          <div className="mx-auto w-full max-w-[1600px] px-4 py-4 xl:px-7">
            <SuitesPage />
          </div>
        )}
        {page === "settings" && (
          <div className="mx-auto w-full max-w-[1600px] px-4 py-4 xl:px-7">
            <SettingsPage />
          </div>
        )}
      </main>
    </div>
  );
}

export default function App(): JSX.Element {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
