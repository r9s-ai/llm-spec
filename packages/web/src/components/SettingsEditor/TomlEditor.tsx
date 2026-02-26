import { useState, useEffect } from "react";

interface TomlEditorProps {
  filePath: string | null;
  content: string;
  onLoad: () => Promise<void>;
  onSave: (content: string) => Promise<void>;
}

const PLACEHOLDER = `# LLM Spec Configuration
[providers.openai]
api_key = "sk-..."
base_url = "https://api.openai.com"`;

export function TomlEditor({ filePath, content, onLoad, onSave }: TomlEditorProps) {
  const [editorContent, setEditorContent] = useState(content);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Update editor content when prop changes
  useEffect(() => {
    setEditorContent(content);
    setHasChanges(false);
  }, [content]);

  const handleLoad = async () => {
    setIsLoading(true);
    try {
      await onLoad();
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(editorContent);
      setHasChanges(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleContentChange = (value: string) => {
    setEditorContent(value);
    setHasChanges(value !== content);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <svg
            className="h-5 w-5 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="text-sm font-medium text-slate-700">{filePath || "llm-spec.toml"}</span>
          {hasChanges && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              unsaved
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => void handleLoad()}
            disabled={isLoading}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {isLoading ? "Loading..." : "Load"}
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={isSaving || !hasChanges}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Editor */}
      <div className="p-4">
        <textarea
          value={editorContent}
          onChange={(e) => handleContentChange(e.target.value)}
          className="min-h-[400px] w-full resize-y rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
          placeholder={PLACEHOLDER}
        />
      </div>
    </div>
  );
}
