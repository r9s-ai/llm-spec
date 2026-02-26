import { useState } from "react";
import { Badge } from "../UI";
import { ActiveRunCard } from "./ActiveRunCard";
import { CompletedRunCard } from "./CompletedRunCard";
import { ProgressBar } from "./ProgressBar";
import type { RunBatchWithRuns, RunEvent, RunSummary } from "../../types";
import * as api from "../../api";

interface TaskCardProps {
  batch: RunBatchWithRuns;
  eventsByRunId: Record<string, RunEvent[]>;
  resultsByRunId: Record<string, Record<string, unknown>>;
  onDelete: (batchId: string) => void;
  onUpdate?: (batch: RunBatchWithRuns) => void;
}

function formatRelativeTime(dateStr: string | null): string {
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
  batch,
  eventsByRunId,
  resultsByRunId,
  onDelete,
  onUpdate,
}: TaskCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(batch.name);
  const [isSavingName, setIsSavingName] = useState(false);

  const isRunning = batch.status === "running";
  const isCompleted = batch.status === "completed";
  const isFailed = batch.status === "cancelled" || batch.failed_runs > 0;

  // Calculate overall progress
  const totalTests = batch.runs.reduce((sum, run) => sum + run.progress_total, 0);
  const doneTests = batch.runs.reduce((sum, run) => sum + run.progress_done, 0);
  const passedTests = batch.runs.reduce((sum, run) => sum + run.progress_passed, 0);
  const failedTests = batch.runs.reduce((sum, run) => sum + run.progress_failed, 0);
  const progress = totalTests > 0 ? Math.round((doneTests / totalTests) * 100) : 0;

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await onDelete(batch.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleStartEditName = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditedName(batch.name);
    setIsEditingName(true);
  };

  const handleSaveName = async () => {
    if (isSavingName || !editedName.trim()) return;
    setIsSavingName(true);
    try {
      const updatedBatch = await api.updateBatch(batch.id, editedName.trim());
      if (onUpdate) {
        onUpdate({ ...batch, name: updatedBatch.name });
      }
      setIsEditingName(false);
    } catch (error) {
      console.error("Failed to update batch name:", error);
      setEditedName(batch.name);
    } finally {
      setIsSavingName(false);
    }
  };

  const handleCancelEditName = () => {
    setEditedName(batch.name);
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
        className="flex items-center justify-between gap-4 px-5 py-4 bg-gradient-to-r from-slate-50 to-slate-100 cursor-pointer hover:from-slate-100 hover:to-slate-150 transition-colors border-b border-slate-200"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-4">
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

          <div>
            <div className="flex items-center gap-3">
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
                  {batch.name}
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
              <Badge
                variant={isRunning ? "running" : isCompleted && !isFailed ? "success" : "error"}
              >
                {isRunning ? "Running" : isCompleted && !isFailed ? "Completed" : "Failed"}
              </Badge>
              <span className="text-xs text-slate-400 bg-slate-200 px-2 py-0.5 rounded">
                {batch.mode}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
              <span>
                {batch.runs.length} route{batch.runs.length !== 1 ? "s" : ""}
              </span>
              <span>·</span>
              <span>
                {formatDate(batch.created_at)} {formatTime(batch.started_at)}
              </span>
              <span>·</span>
              <span className="text-slate-400">{formatRelativeTime(batch.created_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Stats Pills */}
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

          {/* Progress indicator for running batches */}
          {isRunning && (
            <div className="w-24">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-violet-600">{progress}%</span>
              </div>
              <ProgressBar progress={progress} variant="running" />
            </div>
          )}

          {/* Delete button (icon only) */}
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

          {/* Expand/Collapse icon */}
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

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-slate-100">
          {/* Route Cards */}
          <div className="divide-y divide-slate-100">
            {batch.runs.map((run) => {
              const events = eventsByRunId[run.id] ?? [];
              const result = resultsByRunId[run.id];
              const summary = result?.summary as RunSummary | undefined;

              if (run.status === "running" || run.status === "queued") {
                return <ActiveRunCard key={run.id} run={run} events={events} />;
              } else {
                return (
                  <CompletedRunCard key={run.id} run={run} summary={summary} result={result} />
                );
              }
            })}
          </div>

          {/* Footer with task ID */}
          <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
            <span className="text-xs text-slate-400">Task ID: {batch.id.slice(0, 8)}...</span>
          </div>
        </div>
      )}
    </div>
  );
}
