import { useState, useEffect, useMemo } from "react";
import { Modal } from "../UI";
import { getProviderConfigs } from "../../api";
import type { ProviderConfig } from "../../types";

interface CreateSuiteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (provider: string, endpoint: string, name: string) => Promise<void>;
}

const COMMON_ENDPOINTS = [
  { value: "/v1/chat/completions", label: "Chat Completions (OpenAI)" },
  { value: "/v1/embeddings", label: "Embeddings (OpenAI)" },
  { value: "/v1/audio/speech", label: "Text-to-Speech (OpenAI)" },
  { value: "/v1/audio/transcriptions", label: "Transcriptions (OpenAI)" },
  { value: "/v1/images/generations", label: "Image Generations (OpenAI)" },
  { value: "/v1/messages", label: "Messages (Anthropic)" },
  { value: "/v1beta/models/{model}:generateContent", label: "Generate Content (Gemini)" },
];

const PROVIDER_COLORS: Record<string, string> = {
  openai: "bg-green-100 text-green-700 border-green-200",
  anthropic: "bg-orange-100 text-orange-700 border-orange-200",
  gemini: "bg-blue-100 text-blue-700 border-blue-200",
  xai: "bg-purple-100 text-purple-700 border-purple-200",
};

export function CreateSuiteModal({ isOpen, onClose, onCreate }: CreateSuiteModalProps) {
  const [provider, setProvider] = useState("");
  const [endpoint, setEndpoint] = useState("/v1/chat/completions");
  const [name, setName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [showCustomEndpoint, setShowCustomEndpoint] = useState(false);
  const [customEndpoint, setCustomEndpoint] = useState("");
  const [providerConfigs, setProviderConfigs] = useState<ProviderConfig[]>([]);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);

  // Load provider configs
  useEffect(() => {
    if (isOpen) {
      setIsLoadingProviders(true);
      getProviderConfigs()
        .then((configs) => {
          setProviderConfigs(configs);
          // Auto-select first configured provider
          if (configs.length > 0 && !provider) {
            setProvider(configs[0].provider);
          }
        })
        .catch(console.error)
        .finally(() => setIsLoadingProviders(false));
    }
  }, [isOpen, provider]);

  // Auto-generate name
  const autoName = useMemo(() => {
    if (!provider) return "";
    const endpointPart = endpoint.split("/").pop() || endpoint;
    return `${provider} ${endpointPart}`;
  }, [provider, endpoint]);

  // Get provider color
  const getProviderColor = (p: string): string => {
    return PROVIDER_COLORS[p] ?? "bg-slate-100 text-slate-700 border-slate-200";
  };

  // Get configured providers
  const configuredProviders = useMemo(() => {
    return providerConfigs.map((c) => c.provider).sort();
  }, [providerConfigs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      const finalEndpoint = showCustomEndpoint ? customEndpoint : endpoint;
      await onCreate(provider, finalEndpoint, name || autoName);
      // Reset form
      setProvider(configuredProviders[0] ?? "");
      setEndpoint("/v1/chat/completions");
      setName("");
      setShowCustomEndpoint(false);
      setCustomEndpoint("");
      onClose();
    } finally {
      setIsCreating(false);
    }
  };

  const handleClose = () => {
    if (!isCreating) {
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create New Suite">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Provider Selection */}
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1.5">
            Provider <span className="text-red-500">*</span>
          </label>
          {isLoadingProviders ? (
            <div className="flex items-center justify-center py-4">
              <svg className="h-5 w-5 animate-spin text-slate-400" fill="none" viewBox="0 0 24 24">
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
          ) : configuredProviders.length === 0 ? (
            <div className="rounded bg-amber-50 border border-amber-200 p-3">
              <div className="flex items-start gap-2">
                <svg
                  className="h-4 w-4 text-amber-500 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <div>
                  <p className="text-sm font-medium text-amber-800">No providers configured</p>
                  <p className="text-xs text-amber-600 mt-0.5">
                    Please configure a provider in Settings before creating a suite.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-1.5">
              {configuredProviders.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setProvider(p)}
                  className={`flex items-center justify-center gap-2 rounded border px-2.5 py-1.5 text-sm font-medium transition-all ${
                    provider === p
                      ? "border-slate-500 bg-slate-100"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-medium ${getProviderColor(p)}`}
                  >
                    {p}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Endpoint Selection */}
        {configuredProviders.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1.5">
              Endpoint <span className="text-red-500">*</span>
            </label>
            {!showCustomEndpoint ? (
              <div className="space-y-1.5">
                <select
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                >
                  {COMMON_ENDPOINTS.map((ep) => (
                    <option key={ep.value} value={ep.value}>
                      {ep.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setShowCustomEndpoint(true)}
                  className="text-xs text-slate-600 hover:text-slate-800 flex items-center gap-1"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  Use custom endpoint
                </button>
              </div>
            ) : (
              <div className="space-y-1.5">
                <input
                  type="text"
                  value={customEndpoint}
                  onChange={(e) => setCustomEndpoint(e.target.value)}
                  placeholder="/v1/your/endpoint"
                  className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm font-mono focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                />
                <button
                  type="button"
                  onClick={() => {
                    setShowCustomEndpoint(false);
                    setCustomEndpoint("");
                  }}
                  className="text-xs text-slate-500 hover:text-slate-600"
                >
                  ← Back to predefined endpoints
                </button>
              </div>
            )}
          </div>
        )}

        {/* Name */}
        {configuredProviders.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1.5">Suite Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={autoName}
              className="w-full rounded border border-slate-200 px-2.5 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
            />
            <p className="mt-1 text-xs text-slate-400">
              Leave empty to use auto-generated name: <span className="font-mono">{autoName}</span>
            </p>
          </div>
        )}

        {/* Preview */}
        {configuredProviders.length > 0 && provider && (
          <div className="rounded bg-slate-50 p-2.5">
            <p className="text-xs font-medium text-slate-500 mb-1.5">Preview</p>
            <div className="flex items-center gap-2">
              <span
                className={`rounded px-1.5 py-0.5 text-xs font-medium ${getProviderColor(provider)}`}
              >
                {provider}
              </span>
              <code className="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-mono text-slate-600">
                {showCustomEndpoint ? customEndpoint || "?" : endpoint}
              </code>
            </div>
            <p className="mt-1.5 text-sm font-medium text-slate-700">{name || autoName}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
          <button
            type="button"
            onClick={handleClose}
            disabled={isCreating}
            className="rounded border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          {configuredProviders.length > 0 && (
            <button
              type="submit"
              disabled={
                isCreating || !provider || (!showCustomEndpoint ? !endpoint : !customEndpoint)
              }
              className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 transition-colors"
            >
              {isCreating ? (
                <span className="flex items-center gap-2">
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
                  Creating...
                </span>
              ) : (
                "Create Suite"
              )}
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
