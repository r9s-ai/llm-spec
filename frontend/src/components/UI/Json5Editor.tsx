import { useRef } from "react";
import Editor, { type OnMount, type OnChange } from "@monaco-editor/react";

interface Json5EditorProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  height?: string | number;
  error?: string | null;
  onValidate?: (isValid: boolean, errors: string[]) => void;
}

export function Json5Editor({
  value,
  onChange,
  readOnly = false,
  height = "100%",
  error,
}: Json5EditorProps) {
  const editorRef = useRef<unknown>(null);

  const handleEditorDidMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const handleChange: OnChange = (value) => {
    onChange(value ?? "");
  };

  return (
    <div className="relative h-full w-full">
      <Editor
        height={height}
        defaultLanguage="json"
        language="json"
        value={value}
        onChange={handleChange}
        onMount={handleEditorDidMount}
        theme="vs-light"
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: "on",
          folding: true,
          foldingStrategy: "indentation",
          automaticLayout: true,
          scrollBeyondLastLine: false,
          wordWrap: "on",
          tabSize: 2,
          formatOnPaste: true,
          formatOnType: true,
          renderWhitespace: "selection",
          scrollbar: {
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
          },
          padding: { top: 8, bottom: 8 },
        }}
      />
      {error && (
        <div className="absolute bottom-0 left-0 right-0 bg-red-50 border-t border-red-200 px-3 py-2">
          <div className="flex items-start gap-2">
            <svg
              className="h-4 w-4 flex-shrink-0 text-red-500 mt-0.5"
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
            <span className="text-xs text-red-600">{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
