import { Badge } from "../UI";

interface TestResultItemProps {
  name: string;
  status: "pass" | "fail" | "skip";
  duration?: number;
  errorMessage?: string;
  onClick?: () => void;
}

export function TestResultItem({
  name,
  status,
  duration,
  errorMessage,
  onClick,
}: TestResultItemProps) {
  const statusVariant = status === "pass" ? "success" : status === "fail" ? "error" : "default";
  const statusText = status === "pass" ? "✓" : status === "fail" ? "✗" : "○";

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
        onClick ? "cursor-pointer hover:bg-slate-50" : ""
      } ${status === "fail" ? "border-red-200 bg-red-50/50" : "border-slate-100 bg-white"}`}
      onClick={onClick}
    >
      <Badge variant={statusVariant}>{statusText}</Badge>

      <div className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-slate-700" title={name}>
          {name}
        </span>
        {errorMessage && (
          <span className="mt-0.5 block truncate text-xs text-red-600" title={errorMessage}>
            {errorMessage}
          </span>
        )}
      </div>

      {duration !== undefined && (
        <span className="text-xs text-slate-400">
          {duration < 1000 ? `${duration}ms` : `${(duration / 1000).toFixed(1)}s`}
        </span>
      )}
    </div>
  );
}
