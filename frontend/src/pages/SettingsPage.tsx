import { useState, useEffect, useCallback } from "react";
import { useAppContext } from "../context";
import { ProviderConfigCard } from "../components";
import { getProviderConfigs, upsertProviderConfig, deleteProviderConfig } from "../api";
import type { ProviderConfig, ProviderConfigUpsert } from "../types";
import { Modal } from "../components/UI";

const KNOWN_PROVIDERS = ["openai", "anthropic", "gemini", "xai"];

export function SettingsPage() {
  const { setNotice } = useAppContext();

  const [providerConfigs, setProviderConfigs] = useState<ProviderConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [deletingProvider, setDeletingProvider] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newProviderName, setNewProviderName] = useState("");

  // Load provider configs
  const loadProviderConfigs = useCallback(async () => {
    setIsLoading(true);
    try {
      const configs = await getProviderConfigs();
      setProviderConfigs(configs);
    } catch (err) {
      console.error("Failed to load provider configs:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProviderConfigs();
  }, [loadProviderConfigs]);

  // Handle save provider config
  const handleSaveProvider = useCallback(
    async (provider: string, input: ProviderConfigUpsert) => {
      setSavingProvider(provider);
      try {
        await upsertProviderConfig(provider, input);
        await loadProviderConfigs();
        setNotice(`${provider} configuration saved.`);
      } finally {
        setSavingProvider(null);
      }
    },
    [loadProviderConfigs, setNotice]
  );

  // Handle delete provider config
  const handleDeleteProvider = useCallback(
    async (provider: string) => {
      setDeletingProvider(provider);
      try {
        await deleteProviderConfig(provider);
        await loadProviderConfigs();
        setNotice(`${provider} configuration deleted.`);
      } finally {
        setDeletingProvider(null);
      }
    },
    [loadProviderConfigs, setNotice]
  );

  // Handle add new provider
  const handleAddProvider = useCallback(() => {
    const name = newProviderName.trim().toLowerCase();
    if (!name) return;

    // Check if already exists
    if (providerConfigs.some((c) => c.provider === name)) {
      setNotice(`${name} already exists.`);
      return;
    }

    // Add to list (will show as unconfigured)
    setShowAddModal(false);
    setNewProviderName("");
    setNotice(`${name} added. Configure it below.`);
  }, [newProviderName, providerConfigs, setNotice]);

  // Get config for a provider
  const getProviderConfig = (provider: string): ProviderConfig | null => {
    return providerConfigs.find((c) => c.provider === provider) ?? null;
  };

  // Get all providers (known + custom)
  const allProviders = [
    ...new Set([...KNOWN_PROVIDERS, ...providerConfigs.map((c) => c.provider)]),
  ].sort();

  return (
    <div className="h-[calc(100vh-57px)] overflow-auto bg-slate-50">
      <div className="p-1.5 space-y-4">
        {/* Page Header */}
        <div className="border border-slate-200 rounded-lg bg-white p-4">
          <h1 className="text-lg font-bold text-slate-900">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage your LLM provider configurations. Changes are synced to the TOML file for CLI
            compatibility.
          </p>
        </div>

        {/* Info Banner */}
        <div className="rounded-lg bg-slate-100 border border-slate-200 p-3">
          <div className="flex items-start gap-3">
            <svg
              className="h-4 w-4 text-slate-500 flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="text-sm font-medium text-slate-700">
                Provider configurations are stored securely
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                API keys are encrypted and never exposed in API responses.
              </p>
            </div>
          </div>
        </div>

        {/* Provider Cards */}
        {isLoading ? (
          <div className="border border-slate-200 rounded-lg bg-white flex items-center justify-center py-12">
            <svg className="h-6 w-6 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Add Provider Button */}
            <div className="flex justify-end">
              <button
                onClick={() => setShowAddModal(true)}
                className="flex items-center gap-1.5 rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 transition-colors"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Add Provider
              </button>
            </div>

            {/* Provider List */}
            <div className="grid gap-2">
              {allProviders.map((provider) => (
                <ProviderConfigCard
                  key={provider}
                  provider={provider}
                  config={getProviderConfig(provider)}
                  onSave={handleSaveProvider}
                  onDelete={handleDeleteProvider}
                  isSaving={savingProvider === provider}
                  isDeleting={deletingProvider === provider}
                />
              ))}
            </div>

            {allProviders.length === 0 && (
              <div className="border border-slate-200 rounded-lg bg-white text-center py-8">
                <svg
                  className="mx-auto h-10 w-10 text-slate-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <p className="mt-2 text-sm text-slate-500">No providers configured</p>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="mt-1 text-sm text-slate-600 hover:text-slate-800 underline"
                >
                  Add your first provider
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add Provider Modal */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false);
          setNewProviderName("");
        }}
        title="Add New Provider"
        width="max-w-md"
      >
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Provider Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={newProviderName}
              onChange={(e) => setNewProviderName(e.target.value)}
              placeholder="e.g., openai, anthropic, custom-provider"
              className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
            />
            <p className="mt-1 text-xs text-slate-400">
              Use lowercase letters, numbers, and hyphens only.
            </p>
          </div>

          {/* Quick Select */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Quick Select</label>
            <div className="flex flex-wrap gap-1.5">
              {KNOWN_PROVIDERS.filter((p) => !providerConfigs.some((c) => c.provider === p)).map(
                (provider) => (
                  <button
                    key={provider}
                    onClick={() => setNewProviderName(provider)}
                    className="rounded bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                  >
                    {provider}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
            <button
              onClick={() => {
                setShowAddModal(false);
                setNewProviderName("");
              }}
              className="rounded border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              onClick={handleAddProvider}
              disabled={!newProviderName.trim()}
              className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              Add Provider
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
