import { useState, useMemo } from "react";
import type { ProviderConfig, ProviderConfigUpsert, ApiType } from "../../types";

interface ProviderConfigCardProps {
  config: ProviderConfig | null;
  provider: string;
  onSave: (provider: string, input: ProviderConfigUpsert) => Promise<void>;
  onDelete?: (provider: string) => Promise<void>;
  isSaving?: boolean;
  isDeleting?: boolean;
}

const API_TYPES: { value: ApiType; label: string; color: string }[] = [
  { value: "openai", label: "OpenAI", color: "bg-green-100 text-green-700" },
  { value: "anthropic", label: "Anthropic", color: "bg-orange-100 text-orange-700" },
  { value: "gemini", label: "Google Gemini", color: "bg-blue-100 text-blue-700" },
  { value: "xai", label: "xAI", color: "bg-purple-100 text-purple-700" },
];

const API_TYPE_DEFAULTS: Record<ApiType, { baseUrl: string }> = {
  openai: { baseUrl: "https://api.openai.com" },
  anthropic: { baseUrl: "https://api.anthropic.com" },
  gemini: { baseUrl: "https://generativelanguage.googleapis.com" },
  xai: { baseUrl: "https://api.x.ai" },
};

export function ProviderConfigCard({
  config,
  provider,
  onSave,
  onDelete,
  isSaving = false,
  isDeleting = false,
}: ProviderConfigCardProps) {
  const [showApiKey, setShowApiKey] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isEditingApiKey, setIsEditingApiKey] = useState(false);

  // Form state - directly editable
  const [apiType, setApiType] = useState<ApiType>((config?.api_type as ApiType) ?? "openai");
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? API_TYPE_DEFAULTS.openai.baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [timeout, setTimeoutValue] = useState(config?.timeout ?? 30);
  const [error, setError] = useState<string | null>(null);

  const isConfigured = config !== null;

  // Get API type color for badge
  const apiTypeColor = useMemo(() => {
    const typeInfo = API_TYPES.find((t) => t.value === apiType);
    return typeInfo?.color ?? "bg-slate-100 text-slate-700";
  }, [apiType]);

  // Handle API type change - save immediately
  const handleApiTypeChange = async (newType: ApiType) => {
    setApiType(newType);
    // Update base URL to default for the new type
    setBaseUrl(API_TYPE_DEFAULTS[newType].baseUrl);

    if (isConfigured) {
      // Save immediately if already configured (without changing api_key)
      try {
        await onSave(provider, {
          api_type: newType,
          base_url: API_TYPE_DEFAULTS[newType].baseUrl,
          timeout,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save");
      }
    }
  };

  // Handle base URL change - save on blur
  const handleBaseUrlBlur = async () => {
    if (!baseUrl.trim()) return;
    if (isConfigured && baseUrl !== config?.base_url) {
      try {
        await onSave(provider, {
          api_type: apiType,
          base_url: baseUrl,
          timeout,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save");
      }
    }
  };

  // Handle timeout change - save on blur
  const handleTimeoutBlur = async () => {
    if (isConfigured && timeout !== config?.timeout) {
      try {
        await onSave(provider, {
          api_type: apiType,
          base_url: baseUrl,
          timeout,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save");
      }
    }
  };

  // Handle API key update
  const handleApiKeyUpdate = async () => {
    if (!apiKey.trim()) {
      setIsEditingApiKey(false);
      return;
    }
    try {
      await onSave(provider, {
        api_type: apiType,
        base_url: baseUrl,
        timeout,
        api_key: apiKey,
      });
      setIsEditingApiKey(false);
      setApiKey("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!onDelete) return;
    try {
      await onDelete(provider);
      setShowDeleteConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  // Handle save for new provider
  const handleSaveNew = async () => {
    if (!baseUrl.trim()) {
      setError("Base URL is required");
      return;
    }
    if (!apiKey.trim()) {
      setError("API Key is required");
      return;
    }
    try {
      await onSave(provider, {
        api_type: apiType,
        base_url: baseUrl,
        timeout,
        api_key: apiKey,
      });
      setApiKey("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900 text-sm">{provider}</span>
          {isConfigured ? (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              Configured
            </span>
          ) : (
            <span className="text-xs text-slate-500">Not configured</span>
          )}
        </div>
        {isConfigured &&
          onDelete &&
          (showDeleteConfirm ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Delete?</span>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="text-xs text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
              >
                {isDeleting ? "Deleting..." : "Yes"}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="text-xs text-slate-500 hover:text-slate-700"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="text-xs text-slate-400 hover:text-red-500 transition-colors"
              title="Delete configuration"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          ))}
      </div>

      {/* Content */}
      <div className="p-3 space-y-3">
        {error && (
          <div className="rounded bg-red-50 border border-red-200 px-2.5 py-2 text-xs text-red-600">
            {error}
            <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-600">
              ×
            </button>
          </div>
        )}

        {/* API Type Selector */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">API Type</label>
          <div className="flex flex-wrap gap-1.5">
            {API_TYPES.map((type) => (
              <button
                key={type.value}
                onClick={() => handleApiTypeChange(type.value)}
                disabled={isSaving}
                className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
                  apiType === type.value
                    ? `${type.color} border-current`
                    : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                } ${isSaving ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {/* Base URL */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Base URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            onBlur={handleBaseUrlBlur}
            disabled={isSaving}
            className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50 disabled:bg-slate-50"
            placeholder="https://api.example.com"
          />
        </div>

        {/* Timeout */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Timeout (seconds)</label>
          <input
            type="number"
            value={timeout}
            onChange={(e) => setTimeoutValue(Number(e.target.value))}
            onBlur={handleTimeoutBlur}
            disabled={isSaving}
            min={1}
            max={600}
            className="w-24 rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50 disabled:bg-slate-50"
          />
        </div>

        {/* API Key */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">API Key</label>
          {isConfigured ? (
            isEditingApiKey ? (
              <div className="space-y-2">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={isSaving}
                  className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50"
                  placeholder="Enter new API key"
                />
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1.5 text-xs text-slate-500">
                    <input
                      type="checkbox"
                      checked={showApiKey}
                      onChange={(e) => setShowApiKey(e.target.checked)}
                      className="rounded border-slate-300"
                    />
                    Show
                  </label>
                  <button
                    onClick={handleApiKeyUpdate}
                    disabled={isSaving || !apiKey.trim()}
                    className="text-xs text-slate-600 hover:text-slate-800 disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingApiKey(false);
                      setApiKey("");
                    }}
                    className="text-xs text-slate-400 hover:text-slate-600"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">••••••••••••••••</span>
                <button
                  onClick={() => setIsEditingApiKey(true)}
                  className="text-xs text-slate-500 hover:text-slate-700"
                >
                  Update
                </button>
              </div>
            )
          ) : (
            <div className="space-y-2">
              <div className="relative">
                <input
                  type={showApiKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={isSaving}
                  className="w-full rounded border border-slate-200 px-2.5 py-1.5 pr-16 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 disabled:opacity-50"
                  placeholder="Enter API key"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                >
                  {showApiKey ? "Hide" : "Show"}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Save button for new provider */}
        {!isConfigured && (
          <div className="pt-2 border-t border-slate-100">
            <button
              onClick={handleSaveNew}
              disabled={isSaving || !baseUrl.trim() || !apiKey.trim()}
              className="w-full rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSaving ? "Saving..." : "Save Configuration"}
            </button>
          </div>
        )}

        {/* Status indicator */}
        {isConfigured && (
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
            <span className={`text-xs px-2 py-0.5 rounded ${apiTypeColor}`}>{apiType}</span>
            <span className="text-xs text-slate-400">
              Updated: {new Date(config.updated_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
