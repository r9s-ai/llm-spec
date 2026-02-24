import { useState, useEffect } from "react";
import Editor, { type OnMount, type OnChange } from "@monaco-editor/react";

interface TomlEditorProps {
  filePath: string | null;
  content: string;
  onLoad: () => Promise<void>;
  onSave: (content: string) => Promise<void>;
}

export function TomlEditor({ filePath, content, onLoad, onSave }: TomlEditorProps) {
  const [editorContent, setEditorContent] = useState(content);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update editor content when prop changes
  useEffect(() => {
    setEditorContent(content);
    setHasChanges(false);
    setError(null);
  }, [content]);

  const handleLoad = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await onSave(editorContent);
      setHasChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  };

  const handleContentChange: OnChange = (value) => {
    setEditorContent(value ?? "");
    setHasChanges(value !== content);
  };

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    // Register TOML language if not already registered
    if (!monaco.languages.getLanguages().some((lang: { id: string }) => lang.id === "toml")) {
      monaco.languages.register({ id: "toml" });

      // Define TOML tokenization
      monaco.languages.setMonarchTokensProvider("toml", {
        tokenizer: {
          root: [
            [/#.*$/, "comment"],
            [/\[.*\]/, "type"],
            [/^\s*[a-zA-Z_][a-zA-Z0-9_]*(?=\s*=)/, "variable"],
            [/"/, "string", "@string_double"],
            [/'/, "string", "@string_single"],
            [/\d+/, "number"],
            [/true|false/, "keyword"],
          ],
          string_double: [
            [/[^\\"]+/, "string"],
            [/\\./, "string.escape"],
            [/"/, "string", "@pop"],
          ],
          string_single: [
            [/[^\\']+/, "string"],
            [/\\./, "string.escape"],
            [/'/, "string", "@pop"],
          ],
        },
      });
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 bg-slate-50">
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
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50 transition-colors"
          >
            {isLoading ? (
              <span className="flex items-center gap-1.5">
                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
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
                Loading...
              </span>
            ) : (
              "Reload"
            )}
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={isSaving || !hasChanges}
            className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {isSaving ? (
              <span className="flex items-center gap-1.5">
                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
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
                Saving...
              </span>
            ) : (
              "Save"
            )}
          </button>
        </div>
      </div>

      {/* Editor */}
      <div className="h-[400px]">
        <Editor
          height="100%"
          defaultLanguage="toml"
          language="toml"
          value={editorContent}
          onChange={handleContentChange}
          onMount={handleEditorDidMount}
          theme="vs-light"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            folding: true,
            automaticLayout: true,
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            renderWhitespace: "selection",
            scrollbar: {
              verticalScrollbarSize: 8,
              horizontalScrollbarSize: 8,
            },
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="border-t border-red-200 bg-red-50 px-4 py-2">
          <div className="flex items-center gap-2">
            <svg
              className="h-4 w-4 text-red-500"
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
            <span className="text-sm text-red-600">{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
