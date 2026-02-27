import { useMemo } from "react";
import type { Suite, SuiteVersion } from "../../types";

interface SuiteEditorProps {
  suite: Suite | null;
  versions: SuiteVersion[];
  selectedVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
}

export function SuiteEditor({
  suite,
  versions,
  selectedVersionId,
  onSelectVersion,
}: SuiteEditorProps) {
  // Find selected version
  const selectedVersion = versions.find((v) => v.id === selectedVersionId);

  // Calculate rawJson5 directly from selected version using useMemo
  // This avoids calling setState within useEffect
  const rawJson5 = useMemo(() => {
    return selectedVersion?.raw_json5 ?? "";
  }, [selectedVersion]);

  if (!suite) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl border border-slate-200 bg-white p-8">
        <div className="text-center">
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
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="mt-2 text-sm text-slate-500">Select a suite to view</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white">
      {/* Header - Provider & Endpoint */}
      <div className="flex-shrink-0 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-700">
            {suite.provider}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-700">
            {suite.route}
          </span>
          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700">
            {suite.model}
          </span>
          <code className="rounded bg-slate-100 px-2 py-1 text-xs font-mono text-slate-600">
            {suite.endpoint}
          </code>
        </div>
      </div>

      {/* Metadata */}
      <div className="flex-shrink-0 border-b border-slate-100 px-4 py-3">
        <div className="grid grid-cols-[100px_1fr] gap-3">
          <span className="flex items-center text-sm font-medium text-slate-600">Name</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-800">
            {suite.name}
          </span>
          <span className="flex items-center text-sm font-medium text-slate-600">Status</span>
          <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-800">
            {suite.status}
          </span>
        </div>
      </div>

      {/* Version Selector */}
      <div className="flex-shrink-0 border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-600">Versions:</span>
          <div className="flex flex-wrap gap-1.5">
            {versions.map((version) => (
              <button
                key={version.id}
                onClick={() => onSelectVersion(version.id)}
                className={`rounded-full px-2.5 py-1 text-xs font-bold transition-colors ${
                  version.id === selectedVersionId
                    ? "bg-violet-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                v{version.version}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* JSON5 Viewer */}
      <div className="flex-1 min-h-0 p-4">
        <textarea
          value={rawJson5}
          readOnly
          className="h-full w-full resize-none rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          placeholder="No JSON5 content for this version."
        />
      </div>
    </div>
  );
}
