import { useMemo, useState } from "react";
import { Badge } from "../UI";
import { ActiveRunCard } from "./ActiveRunCard";
import { CompletedRunCard } from "./CompletedRunCard";
import { ProgressBar } from "./ProgressBar";
import type { RunEvent, RunJob, RunSummary, TaskWithRuns } from "../../types";
import * as api from "../../api";

interface TaskCardProps {
  task: TaskWithRuns;
  eventsByRunId: Record<string, RunEvent[]>;
  resultsByRunId: Record<string, Record<string, unknown>>;
  onDelete: (taskId: string) => void;
  onCancel?: (taskId: string) => Promise<void> | void;
  onUpdate?: (task: TaskWithRuns) => void;
  onRetryFailedTest?: (run: RunJob, runCaseId: string, testName: string) => Promise<void> | void;
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function TaskCard({
  task,
  eventsByRunId,
  resultsByRunId,
  onDelete,
  onCancel,
  onUpdate,
  onRetryFailedTest,
}: TaskCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(task.name);
  const [isSavingName, setIsSavingName] = useState(false);

  const isRunning = task.status === "running";
  const isCompleted = task.status === "completed";
  const isFailed = task.status === "cancelled" || task.failed_runs > 0;

  // Calculate overall progress
  const totalTests = task.runs.reduce((sum, run) => sum + run.progress_total, 0);
  const doneTests = task.runs.reduce((sum, run) => sum + run.progress_done, 0);
  const passedTests = task.runs.reduce((sum, run) => sum + run.progress_passed, 0);
  const failedTests = task.runs.reduce((sum, run) => sum + run.progress_failed, 0);
  const progress = totalTests > 0 ? Math.round((doneTests / totalTests) * 100) : 0;
  const modelCount = useMemo(
    () => new Set(task.runs.map((run) => `${run.provider}:${run.model ?? "unknown"}`)).size,
    [task.runs]
  );
  const routeCount = useMemo(
    () => new Set(task.runs.map((run) => `${run.provider}:${run.route ?? run.endpoint}`)).size,
    [task.runs]
  );

  const groupedRuns = useMemo(() => {
    const grouped = new Map<string, { provider: string; model: string; runs: typeof task.runs }>();
    for (const run of task.runs) {
      const modelKey = run.model ?? "unknown";
      const groupKey = `${run.provider}:${modelKey}`;
      if (!grouped.has(groupKey)) {
        grouped.set(groupKey, { provider: run.provider, model: modelKey, runs: [] });
      }
      grouped.get(groupKey)!.runs.push(run);
    }

    return Array.from(grouped.entries())
      .map(([groupKey, entry]) => {
        const modelTotal = entry.runs.reduce((sum, run) => sum + run.progress_total, 0);
        const modelDone = entry.runs.reduce((sum, run) => sum + run.progress_done, 0);
        const modelPassed = entry.runs.reduce((sum, run) => sum + run.progress_passed, 0);
        const modelFailed = entry.runs.reduce((sum, run) => sum + run.progress_failed, 0);
        return {
          key: groupKey,
          provider: entry.provider,
          model: entry.model,
          runs: [...entry.runs].sort((a, b) => {
            const routeA = a.route ?? a.endpoint;
            const routeB = b.route ?? b.endpoint;
            return routeA.localeCompare(routeB);
          }),
          summary: {
            total: modelTotal,
            done: modelDone,
            passed: modelPassed,
            failed: modelFailed,
          },
        };
      })
      .sort(
        (a, b) => a.provider.localeCompare(b.provider) || a.model.localeCompare(b.model)
      );
  }, [task]);

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await onDelete(task.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancel = async () => {
    if (!onCancel || isCancelling) return;
    setIsCancelling(true);
    try {
      await onCancel(task.id);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleStartEditName = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditedName(task.name);
    setIsEditingName(true);
  };

  const handleSaveName = async () => {
    if (isSavingName || !editedName.trim()) return;
    setIsSavingName(true);
    try {
      const updatedTask = await api.updateTask(task.id, editedName.trim());
      if (onUpdate) {
        onUpdate({ ...task, name: updatedTask.name });
      }
      setIsEditingName(false);
    } catch (error) {
      console.error("Failed to update task name:", error);
      setEditedName(task.name);
    } finally {
      setIsSavingName(false);
    }
  };

  const handleCancelEditName = () => {
    setEditedName(task.name);
    setIsEditingName(false);
  };

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      void handleSaveName();
    } else if (e.key === "Escape") {
      handleCancelEditName();
    }
    e.stopPropagation();
  };

  return (
    <div className="border border-slate-200 rounded-xl bg-white shadow-md overflow-hidden">
      {/* Header - More prominent */}
      <div
        className="grid grid-cols-[auto_1fr] gap-4 px-5 py-4 bg-gradient-to-r from-slate-50 to-slate-100 cursor-pointer hover:from-slate-100 hover:to-slate-150 transition-colors border-b border-slate-200"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Status Icon */}
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center ${
            isRunning ? "bg-violet-100" : isCompleted && !isFailed ? "bg-green-100" : "bg-red-100"
          }`}
        >
          {isRunning ? (
            <svg className="w-5 h-5 text-violet-600 animate-spin" fill="none" viewBox="0 0 24 24">
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
          ) : isCompleted && !isFailed ? (
            <svg
              className="w-5 h-5 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : (
            <svg
              className="w-5 h-5 text-red-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          )}
        </div>

        <div className="flex flex-col gap-3">
          {/* Block A: header row (left info + right stats/actions) */}
          <div className="flex w-full items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              {/* Editable Name */}
              {isEditingName ? (
                <input
                  type="text"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  onKeyDown={handleNameKeyDown}
                  onBlur={() => void handleSaveName()}
                  onClick={(e) => e.stopPropagation()}
                  disabled={isSavingName}
                  className="text-lg font-bold text-slate-900 bg-white border border-violet-300 rounded px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  autoFocus
                />
              ) : (
                <span
                  className="text-lg font-bold text-slate-900 hover:text-violet-600 cursor-pointer group"
                  onClick={handleStartEditName}
                  title="Click to edit name"
                >
                  {task.name}
                  <svg
                    className="inline-block w-4 h-4 ml-1 opacity-0 group-hover:opacity-50"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                    />
                  </svg>
                </span>
              )}
              {(isRunning || isFailed) && (
                <Badge variant={isRunning ? "running" : "error"}>
                  {isRunning ? "Running" : "Failed"}
                </Badge>
              )}
              <span className="text-xs text-slate-400 bg-slate-200 px-2 py-0.5 rounded">
                {task.mode}
              </span>
              <span className="text-sm text-slate-500">
                {modelCount} model{modelCount !== 1 ? "s" : ""} · {routeCount} route
                {routeCount !== 1 ? "s" : ""}
              </span>
              <span className="text-sm text-slate-500">
                {formatDate(task.created_at)} {formatTime(task.started_at)}
              </span>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 rounded-full">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  <span className="text-sm font-semibold text-green-700">{passedTests}</span>
                  <span className="text-xs text-green-600">passed</span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 rounded-full">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  <span className="text-sm font-semibold text-red-700">{failedTests}</span>
                  <span className="text-xs text-red-600">failed</span>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  void handleDelete();
                }}
                disabled={isDeleting || isRunning}
                className="w-8 h-8 rounded-full bg-slate-200 hover:bg-red-100 flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Delete task"
              >
                <svg
                  className={`w-4 h-4 ${isDeleting ? "text-slate-400 animate-spin" : "text-slate-600 hover:text-red-600"}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  {isDeleting ? (
                    <>
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
                    </>
                  ) : (
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  )}
                </svg>
              </button>
              <div
                className={`w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center transition-transform ${isExpanded ? "rotate-180" : ""}`}
              >
                <svg
                  className="w-4 h-4 text-slate-600"
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
            </div>
          </div>

          {/* Block B: progress + cancel (own row) */}
          <div className="flex w-full items-center justify-end gap-3">
            <div className="flex items-center gap-2">
              <span
                className={`text-[11px] font-medium ${isRunning ? "text-violet-600" : "text-slate-400"}`}
              >
                {progress}%
              </span>
              <div className="w-48">
                <ProgressBar progress={progress} variant={isRunning ? "running" : "default"} />
              </div>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (isRunning && onCancel) {
                  void handleCancel();
                }
              }}
              disabled={!isRunning || !onCancel || isCancelling}
              className={`h-7 w-7 rounded-full border flex items-center justify-center transition-colors disabled:cursor-not-allowed ${
                isRunning
                  ? "border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100"
                  : "border-slate-200 bg-slate-100 text-slate-400"
              }`}
              title="Cancel task"
            >
              {isCancelling ? (
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
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
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-slate-100">
          <div className="space-y-2 p-3 bg-slate-50/50">
            {groupedRuns.map((group) => (
              <div key={group.key} className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-xs">
                  <span className="text-base text-slate-800">
                    <span className="font-mono font-medium text-slate-700">
                      <span className="font-semibold capitalize">{group.provider}</span>
                    </span>
                    <span className="text-slate-400">:</span>
                    <span className="font-mono font-medium text-slate-700">
                      {group.model}
                    </span>
                  </span>
                  <span className="text-slate-500">
                    {group.summary.done}/{group.summary.total} ·{" "}
                    <span className="text-green-700">{group.summary.passed} pass</span> ·{" "}
                    <span className="text-red-700">{group.summary.failed} fail</span>
                  </span>
                </div>
                <div className="divide-y divide-slate-100">
                  {group.runs.map((run) => {
                    const events = eventsByRunId[run.id] ?? [];
                    const result = resultsByRunId[run.id];
                    const summary = result?.summary as RunSummary | undefined;

                    if (run.status === "running" || run.status === "queued") {
                      return <ActiveRunCard key={run.id} run={run} events={events} />;
                    }
                    return (
                      <CompletedRunCard
                        key={run.id}
                        run={run}
                        summary={summary}
                        result={result}
                        onRetryFailedTest={onRetryFailedTest}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Footer with task ID */}
          <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
            <span className="text-xs text-slate-400">Task ID: {task.id.slice(0, 8)}...</span>
          </div>
        </div>
      )}
    </div>
  );
}
