import { useCallback, useState } from "react";
import { getTomlSettings, updateTomlSettings } from "../api";
import type { TomlSettings } from "../types";

export function useSettings() {
  const [toml, setToml] = useState<TomlSettings | null>(null);

  const loadToml = useCallback(async (): Promise<void> => {
    const config = await getTomlSettings();
    setToml(config);
  }, []);

  const saveToml = useCallback(async (content: string): Promise<TomlSettings> => {
    const saved = await updateTomlSettings(content);
    setToml(saved);
    return saved;
  }, []);

  return {
    toml,
    loadToml,
    saveToml,
  };
}
