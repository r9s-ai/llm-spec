import { Modal } from "../UI";
import type { TestResult } from "./TestResultList";

interface ErrorDetailModalProps {
  test: TestResult | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ErrorDetailModal({ test, isOpen, onClose }: ErrorDetailModalProps) {
  if (!test) return null;

  const handleCopyResponse = () => {
    if (test.responseBody) {
      navigator.clipboard.writeText(JSON.stringify(test.responseBody, null, 2));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Error: ${test.name}`} width="max-w-3xl">
      <div className="space-y-4">
        {/* Error Info */}
        <div className="grid grid-cols-2 gap-3">
          {test.errorType && (
            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-500">Error Type</span>
              <p className="mt-1 text-sm font-semibold text-slate-900">{test.errorType}</p>
            </div>
          )}
          {test.statusCode && (
            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-500">Status Code</span>
              <p className="mt-1 text-sm font-semibold text-slate-900">{test.statusCode}</p>
            </div>
          )}
          {test.duration !== undefined && (
            <div className="rounded-lg bg-slate-50 p-3">
              <span className="text-xs font-medium text-slate-500">Duration</span>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {test.duration < 1000
                  ? `${test.duration}ms`
                  : `${(test.duration / 1000).toFixed(1)}s`}
              </p>
            </div>
          )}
        </div>

        {/* Error Message */}
        {test.errorMessage && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <span className="text-xs font-medium text-red-600">Error Message</span>
            <p className="mt-1 whitespace-pre-wrap text-sm text-red-800">{test.errorMessage}</p>
          </div>
        )}

        {/* Response Body */}
        {test.responseBody && (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Response Body</span>
              <button
                onClick={handleCopyResponse}
                className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Copy
              </button>
            </div>
            <pre className="max-h-[300px] overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-100">
              {JSON.stringify(test.responseBody, null, 2)}
            </pre>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
}
