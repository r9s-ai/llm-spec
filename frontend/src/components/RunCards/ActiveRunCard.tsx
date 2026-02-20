import type { RunJob, RunEvent } from "../../types";
import { ProgressBar } from "./ProgressBar";
import { Badge } from "../UI";

interface ActiveRunCardProps {
  run: RunJob;
  events: RunEvent[];
}

export function ActiveRunCard({ run, events }: ActiveRunCardProps) {
  const progress =
    run.progress_total > 0 ? Math.round((run.progress_done / run.progress_total) * 100) : 0;

  const latestEvents = events.slice(0, 3);

  return (
    <div className="border-b border-slate-100 p-4 last:border-b-0">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Badge variant="running">
              <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
              Running
            </Badge>
            <span className="text-xs text-slate-500">{run.mode}</span>
          </div>
          <h4 className="mt-1 truncate font-semibold text-slate-900">
            {run.provider} {run.endpoint}
          </h4>
          <p className="truncate text-xs text-slate-500">{run.id}</p>
        </div>
      </div>

      {/* Progress */}
      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-slate-600">{progress}% complete</span>
          <span className="text-slate-500">
            {run.progress_done}/{run.progress_total} tests
          </span>
        </div>
        <ProgressBar progress={progress} variant="running" />
      </div>

      {/* Stats */}
      <div className="mt-3 flex gap-3 text-xs">
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-slate-600">{run.progress_passed} passed</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-red-500" />
          <span className="text-slate-600">{run.progress_failed} failed</span>
        </div>
      </div>

      {/* Latest Events */}
      {latestEvents.length > 0 && (
        <div className="mt-3 rounded-lg bg-slate-50 p-2">
          <p className="mb-1 text-xs font-medium text-slate-500">Latest events:</p>
          <div className="space-y-1">
            {latestEvents.map((event) => (
              <div
                key={event.id}
                className="flex items-center justify-between text-xs text-slate-600"
              >
                <span className="truncate">{event.event_type}</span>
                <span className="text-slate-400">#{event.seq}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
