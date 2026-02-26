import { useMemo } from "react";
import { useAppContext } from "../context";
import { TomlEditor, ProviderSummary } from "../components";

interface ProviderConfig {
  name: string;
  apiKey?: string;
  baseUrl?: string;
}

// Simple TOML parser for provider configs
function parseProvidersFromToml(toml: string): ProviderConfig[] {
  const providers: ProviderConfig[] = [];
  const lines = toml.split("\n");
  let currentProvider: string | null = null;
  let currentConfig: Partial<ProviderConfig> = {};

  for (const line of lines) {
    const trimmed = line.trim();

    // Match [provider.xxx] section
    const providerMatch = trimmed.match(/^\[provider\.([^\]]+)\]$/);
    if (providerMatch) {
      // Save previous provider
      if (currentProvider) {
        providers.push({
          name: currentProvider,
          ...currentConfig,
        });
      }
      currentProvider = providerMatch[1];
      currentConfig = {};
      continue;
    }

    // Match key = "value" in current section
    if (currentProvider) {
      const apiKeyMatch = trimmed.match(/^api_key\s*=\s*"([^"]*)"/);
      if (apiKeyMatch) {
        currentConfig.apiKey = apiKeyMatch[1];
        continue;
      }

      const baseUrlMatch = trimmed.match(/^base_url\s*=\s*"([^"]*)"/);
      if (baseUrlMatch) {
        currentConfig.baseUrl = baseUrlMatch[1];
        continue;
      }
    }
  }

  // Save last provider
  if (currentProvider) {
    providers.push({
      name: currentProvider,
      ...currentConfig,
    });
  }

  return providers;
}

export function SettingsPage() {
  const { setNotice, settings } = useAppContext();
  const { toml, loadToml, saveToml } = settings;

  // Parse providers from TOML content
  const providers = useMemo(() => {
    if (!toml?.content) return [];
    return parseProvidersFromToml(toml.content);
  }, [toml]);

  const handleLoad = async () => {
    await loadToml();
    setNotice("TOML loaded.");
  };

  const handleSave = async (content: string) => {
    await saveToml(content);
    setNotice("TOML saved.");
  };

  return (
    <div className="min-h-[calc(100vh-57px)] bg-slate-50">
      <div className="mx-auto max-w-4xl p-4">
        {/* Page Header */}
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">
            Edit runtime TOML config for providers and report behavior.
          </p>
        </div>

        {/* TOML Editor */}
        <div className="mb-4">
          <TomlEditor
            filePath={toml?.path ?? null}
            content={toml?.content ?? ""}
            onLoad={handleLoad}
            onSave={handleSave}
          />
        </div>

        {/* Provider Summary */}
        <ProviderSummary providers={providers} />
      </div>
    </div>
  );
}
