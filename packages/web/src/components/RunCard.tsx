import type { RunEvent, RunJob, RunSummary } from "../types";

interface RunCardProps {
  run: RunJob;
  events: RunEvent[];
  summary?: RunSummary;
}

export function RunCard({ run, events, summary }: RunCardProps) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <div className="text-sm font-bold">
        <strong>{run.provider}</strong> {run.endpoint}
      </div>
      <div className="mt-1 font-mono text-[11px] text-slate-500">{run.id}</div>

      <div className="mt-2 grid grid-cols-3 gap-1.5 text-xs">
        <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
          Status <b className="ml-1 text-slate-900">{run.status}</b>
        </span>
        <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
          Progress{" "}
          <b className="ml-1 text-slate-900">
            {run.progress_done}/{run.progress_total}
          </b>
        </span>
        <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
          Pass/Fail{" "}
          <b className="ml-1 text-slate-900">
            {run.progress_passed}/{run.progress_failed}
          </b>
        </span>
      </div>

      {summary && (
        <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-xs">
          <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
            Total <b className="ml-1 text-slate-900">{String(summary.total ?? "-")}</b>
          </span>
          <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
            Passed <b className="ml-1 text-slate-900">{String(summary.passed ?? "-")}</b>
          </span>
          <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
            Failed <b className="ml-1 text-slate-900">{String(summary.failed ?? "-")}</b>
          </span>
        </div>
      )}

      <div className="mt-2 max-h-28 overflow-auto rounded-lg border border-slate-200 bg-white">
        {events.slice(0, 8).map((event) => (
          <div
            key={event.id}
            className="flex items-center justify-between border-b border-slate-100 px-2 py-1.5 text-xs last:border-b-0"
          >
            <span>{event.event_type}</span>
            <small className="text-slate-500">#{event.seq}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
