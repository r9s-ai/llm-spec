import { useState, useEffect } from "react";
import type { Suite, SuiteVersion } from "../../types";

interface SuiteEditorProps {
  suite: Suite | null;
  versions: SuiteVersion[];
  selectedVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
  onUpdateMeta: (name: string, status: "active" | "archived") => Promise<void>;
  onDeleteSuite: () => Promise<void>;
  onSaveVersion: (rawJson5: string) => Promise<void>;
}

export function SuiteEditor({
  suite,
  versions,
  selectedVersionId,
  onSelectVersion,
  onUpdateMeta,
  onDeleteSuite,
  onSaveVersion,
}: SuiteEditorProps) {
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"active" | "archived">("active");
  const [rawJson5, setRawJson5] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Update form when suite changes
  useEffect(() => {
    if (suite) {
      setName(suite.name);
      setStatus(suite.status as "active" | "archived");
    }
  }, [suite]);

  // Update editor when version changes
  const selectedVersion = versions.find((v) => v.id === selectedVersionId);
  useEffect(() => {
    if (selectedVersion) {
      setRawJson5(selectedVersion.raw_json5);
    }
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
          <p className="mt-2 text-sm text-slate-500">Select a suite to edit</p>
        </div>
      </div>
    );
  }

  const handleUpdateMeta = async () => {
    setIsSaving(true);
    try {
      await onUpdateMeta(name, status);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSuite = async () => {
    if (!window.confirm(`Delete suite "${suite.name}"? This cannot be undone.`)) return;
    setIsSaving(true);
    try {
      await onDeleteSuite();
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveVersion = async () => {
    setIsSaving(true);
    try {
      await onSaveVersion(rawJson5);
    } finally {
      setIsSaving(false);
    }
  };

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

      {/* Meta Editor */}
      <div className="flex-shrink-0 border-b border-slate-100 px-4 py-3">
        <div className="grid grid-cols-[100px_1fr] gap-3">
          <label className="flex items-center text-sm font-medium text-slate-600">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          />

          <label className="flex items-center text-sm font-medium text-slate-600">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as "active" | "archived")}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          >
            <option value="active">active</option>
            <option value="archived">archived</option>
          </select>
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

      {/* JSON5 Editor */}
      <div className="flex-1 min-h-0 p-4">
        <textarea
          value={rawJson5}
          onChange={(e) => setRawJson5(e.target.value)}
          className="h-full w-full resize-none rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          placeholder="Enter JSON5 content..."
        />
      </div>

      {/* Action Buttons */}
      <div className="flex-shrink-0 border-t border-slate-100 px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => void handleDeleteSuite()}
            disabled={isSaving}
            className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Delete
          </button>
          <button
            onClick={() => void handleUpdateMeta()}
            disabled={isSaving || (name === suite.name && status === suite.status)}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            Update Meta
          </button>
          <button
            onClick={() => void handleSaveVersion()}
            disabled={isSaving || !rawJson5.trim()}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            Save New Version
          </button>
        </div>
      </div>
    </div>
  );
}
