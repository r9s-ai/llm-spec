import { useMemo, useState } from "react";

interface CreateSuiteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (
    provider: string,
    route: string,
    model: string,
    endpoint: string,
    name: string
  ) => Promise<void>;
  existingProviders: string[];
}

const COMMON_ENDPOINTS = [
  "/v1/chat/completions",
  "/v1/embeddings",
  "/v1/audio/speech",
  "/v1/audio/transcriptions",
  "/v1/images/generations",
  "/v1/messages",
  "/v1beta/models/{model}:generateContent",
];

export function CreateSuiteModal({
  isOpen,
  onClose,
  onCreate,
  existingProviders,
}: CreateSuiteModalProps) {
  const [provider, setProvider] = useState("openai");
  const [route, setRoute] = useState("chat_completions");
  const [model, setModel] = useState("gpt-4o-mini");
  const [endpoint, setEndpoint] = useState("/v1/chat/completions");
  const [name, setName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [showCustomEndpoint, setShowCustomEndpoint] = useState(false);

  const autoName = useMemo(() => `${provider} ${route} (${model})`, [provider, route, model]);

  const allProviders = useMemo(() => {
    const providers = new Set(existingProviders);
    providers.add("openai");
    providers.add("anthropic");
    providers.add("gemini");
    providers.add("xai");
    return Array.from(providers).sort();
  }, [existingProviders]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await onCreate(provider, route, model, endpoint, name || autoName);
      setProvider("openai");
      setRoute("chat_completions");
      setModel("gpt-4o-mini");
      setEndpoint("/v1/chat/completions");
      setName("");
      setShowCustomEndpoint(false);
      onClose();
    } finally {
      setIsCreating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-slate-900">Create New Suite</h2>
        <p className="mt-1 text-sm text-slate-500">
          Create a provider/route/model suite entry.
        </p>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Provider <span className="text-red-500">*</span>
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            >
              {allProviders.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              Route <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={route}
              onChange={(e) => setRoute(e.target.value)}
              placeholder="chat_completions"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              Model <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o-mini"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              Endpoint <span className="text-red-500">*</span>
            </label>
            <div className="mt-1 space-y-2">
              {!showCustomEndpoint ? (
                <>
                  <select
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  >
                    {COMMON_ENDPOINTS.map((ep) => (
                      <option key={ep} value={ep}>
                        {ep}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setShowCustomEndpoint(true)}
                    className="text-xs text-violet-600 hover:text-violet-700"
                  >
                    Or enter custom endpoint...
                  </button>
                </>
              ) : (
                <>
                  <input
                    type="text"
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    placeholder="/v1/your/endpoint"
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setShowCustomEndpoint(false);
                      setEndpoint(COMMON_ENDPOINTS[0]);
                    }}
                    className="text-xs text-violet-600 hover:text-violet-700"
                  >
                    Use predefined endpoint
                  </button>
                </>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={autoName}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            />
            <p className="mt-1 text-xs text-slate-400">Leave empty to use: {autoName}</p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating || !provider || !route || !model || !endpoint}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {isCreating ? "Creating..." : "Create Suite"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
