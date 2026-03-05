/**
 * Shared formatting utilities used across multiple components.
 */

/** Format a latency value in milliseconds to a human-readable string. */
export function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Format an unknown value for display. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/** Format a date string as a relative time (e.g. "5m ago", "2h ago"). */
export function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

/** Return a Tailwind CSS class string for an HTTP status code badge. */
export function httpStatusClassName(status: number | undefined): string {
  if (status === 200) return "bg-green-100 text-green-700";
  if (status !== undefined && status >= 400) return "bg-red-100 text-red-700";
  return "bg-slate-100 text-slate-700";
}
