import { useState, useEffect, useCallback, useMemo } from "react";
import JSON5 from "json5";
import type { Suite, SuiteVersion } from "../../types";
import { Json5Editor } from "../UI";

interface SuiteEditorProps {
  suite: Suite | null;
  versions: SuiteVersion[];
  selectedVersionId: string | null;
  onSelectVersion: (versionId: string) => void;
  onUpdateMeta: (name: string, status: "active" | "archived") => Promise<void>;
  onDeleteSuite: () => Promise<void>;
  onSaveVersion: (rawJson5: string) => Promise<void>;
}

interface ValidationError {
  line?: number;
  message: string;
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
  const [validationError, setValidationError] = useState<ValidationError | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [activeTab, setActiveTab] = useState<"editor" | "meta">("editor");

  // Get selected version
  const selectedVersion = versions.find((v) => v.id === selectedVersionId);

  // Check if content has changes
  const hasChanges = useMemo(() => {
    if (!selectedVersion) return rawJson5.trim().length > 0;
    return rawJson5 !== selectedVersion.raw_json5;
  }, [rawJson5, selectedVersion]);

  // Update form when suite changes
  useEffect(() => {
    if (suite) {
      setName(suite.name);
      setStatus(suite.status as "active" | "archived");
    }
  }, [suite]);

  // Update editor when version changes
  useEffect(() => {
    if (selectedVersion) {
      setRawJson5(selectedVersion.raw_json5);
      setValidationError(null);
    }
  }, [selectedVersion]);

  // Validate JSON5 content
  const validateJson5 = useCallback((content: string): ValidationError | null => {
    if (!content.trim()) {
      return { message: "Content cannot be empty" };
    }

    try {
      const parsed = JSON5.parse(content);

      // Validate required fields
      if (typeof parsed !== "object" || parsed === null) {
        return { message: "Content must be a JSON object" };
      }

      if (!parsed.provider) {
        return { message: "Missing required field: provider" };
      }

      if (!parsed.endpoint) {
        return { message: "Missing required field: endpoint" };
      }

      if (!Array.isArray(parsed.tests)) {
        return { message: "Missing or invalid field: tests (must be an array)" };
      }

      return null;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Invalid JSON5";
      // Try to extract line number from error message
      const lineMatch = errorMessage.match(/at line (\d+)/);
      return {
        line: lineMatch ? parseInt(lineMatch[1], 10) : undefined,
        message: errorMessage,
      };
    }
  }, []);

  // Handle content change with validation
  const handleContentChange = useCallback(
    (value: string) => {
      setRawJson5(value);
      const error = validateJson5(value);
      setValidationError(error);
    },
    [validateJson5]
  );

  // Handle update meta
  const handleUpdateMeta = async () => {
    setIsSaving(true);
    try {
      await onUpdateMeta(name, status);
    } finally {
      setIsSaving(false);
    }
  };

  // Handle delete suite
  const handleDeleteSuite = async () => {
    setIsSaving(true);
    try {
      await onDeleteSuite();
      setShowDeleteConfirm(false);
    } finally {
      setIsSaving(false);
    }
  };

  // Handle save version
  const handleSaveVersion = async () => {
    // Validate before saving
    const error = validateJson5(rawJson5);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsSaving(true);
    try {
      await onSaveVersion(rawJson5);
    } finally {
      setIsSaving(false);
    }
  };

  // Format JSON5 content
  const handleFormat = useCallback(() => {
    try {
      const parsed = JSON5.parse(rawJson5);
      const formatted = JSON5.stringify(parsed, null, 2);
      setRawJson5(formatted);
      setValidationError(null);
    } catch {
      // Keep original content if parsing fails
    }
  }, [rawJson5]);

  if (!suite) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-slate-200 bg-white p-8">
        <div className="text-center">
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
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="mt-2 text-sm text-slate-500">Select a suite to edit</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-200 bg-white overflow-hidden">
      {/* Header - Provider & Endpoint */}
      <div className="flex-shrink-0 border-b border-slate-100 px-3 py-2 bg-slate-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">
              {suite.provider}
            </span>
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-600">
              {suite.endpoint}
            </code>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                suite.status === "active"
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {suite.status}
            </span>
          </div>
        </div>
      </div>

      {/* Version Selector */}
      <div className="flex-shrink-0 border-b border-slate-100 px-3 py-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-600">Version:</span>
            <div className="relative">
              <select
                value={selectedVersionId ?? ""}
                onChange={(e) => onSelectVersion(e.target.value)}
                className="appearance-none rounded border border-slate-200 bg-white pl-2 pr-6 py-1 text-xs font-medium focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400 cursor-pointer"
              >
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    v{version.version}
                  </option>
                ))}
              </select>
              <svg
                className="absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400 pointer-events-none"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </div>
            {selectedVersion && (
              <span className="text-xs text-slate-500">
                {new Date(selectedVersion.created_at).toLocaleString()}
              </span>
            )}
          </div>
          {hasChanges && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700">
              unsaved changes
            </span>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex-shrink-0 border-b border-slate-100">
        <div className="flex">
          <button
            onClick={() => setActiveTab("editor")}
            className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === "editor"
                ? "border-slate-600 text-slate-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            JSON5 Editor
          </button>
          <button
            onClick={() => setActiveTab("meta")}
            className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
              activeTab === "meta"
                ? "border-slate-600 text-slate-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            Metadata
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === "editor" ? (
          <div className="h-full flex flex-col">
            {/* Editor Toolbar */}
            <div className="flex-shrink-0 px-3 py-1.5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleFormat}
                  className="rounded border border-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                  title="Format JSON5"
                >
                  Format
                </button>
              </div>
              {validationError && (
                <div className="flex items-center gap-1 text-red-500">
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span className="text-xs">{validationError.message}</span>
                </div>
              )}
            </div>
            {/* Monaco Editor */}
            <div className="flex-1 min-h-0">
              <Json5Editor
                value={rawJson5}
                onChange={handleContentChange}
                height="100%"
                error={null}
              />
            </div>
          </div>
        ) : (
          <div className="p-3 space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Suite Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded border border-slate-200 px-2 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as "active" | "archived")}
                className="w-full rounded border border-slate-200 px-2 py-1.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <div className="pt-3 border-t border-slate-200">
              <button
                onClick={() => void handleUpdateMeta()}
                disabled={isSaving || (name === suite.name && status === suite.status)}
                className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 transition-colors"
              >
                {isSaving ? "Saving..." : "Save Metadata"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex-shrink-0 border-t border-slate-100 px-3 py-2 bg-slate-50">
        <div className="flex items-center justify-between">
          <div>
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-600">Are you sure?</span>
                <button
                  onClick={() => void handleDeleteSuite()}
                  disabled={isSaving}
                  className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  Yes, Delete
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isSaving}
                  className="rounded border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isSaving}
                className="rounded border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                Delete Suite
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => void handleSaveVersion()}
              disabled={isSaving || !hasChanges || validationError !== null}
              className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 transition-colors"
            >
              {isSaving ? "Saving..." : "Save New Version"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
