interface ProviderConfig {
  name: string;
  apiKey?: string;
  baseUrl?: string;
}

interface ProviderSummaryProps {
  providers: ProviderConfig[];
}

function maskApiKey(key: string | undefined): string {
  if (!key) return "not set";
  if (key.length <= 8) return "****";
  return `${key.slice(0, 7)}****${key.slice(-4)}`;
}

export function ProviderSummary({ providers }: ProviderSummaryProps) {
  if (providers.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-center">
        <svg
          className="mx-auto h-12 w-12 text-slate-300"
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
        <p className="mt-1 text-xs text-slate-400">Add provider config in TOML to see summary</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      {/* Header */}
      <div className="border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-900">Provider Summary</h3>
        <p className="text-xs text-slate-500">Parsed from TOML configuration</p>
      </div>

      {/* Provider List */}
      <div className="divide-y divide-slate-100">
        {providers.map((provider) => (
          <div key={provider.name} className="px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-700">
                {provider.name}
              </span>
            </div>
            <div className="grid grid-cols-[100px_1fr] gap-1 text-sm">
              <span className="text-slate-500">API Key:</span>
              <code className="font-mono text-xs text-slate-600">
                {maskApiKey(provider.apiKey)}
              </code>

              {provider.baseUrl && (
                <>
                  <span className="text-slate-500">Base URL:</span>
                  <code className="font-mono text-xs text-slate-600">{provider.baseUrl}</code>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
