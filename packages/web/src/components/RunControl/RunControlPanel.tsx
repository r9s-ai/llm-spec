import type { RunMode } from "../../types";
import { ModeSelector } from "./ModeSelector";
import { RunButton } from "./RunButton";

interface RunControlPanelProps {
  selectedCount: number;
  runMode: RunMode;
  isRunning: boolean;
  onModeChange: (mode: RunMode) => void;
  onRun: () => void;
}

export function RunControlPanel({
  selectedCount,
  runMode,
  isRunning,
  onModeChange,
  onRun,
}: RunControlPanelProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-bold text-slate-900">Run Control</h3>

      <div className="space-y-3">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-500">Mode</label>
          <ModeSelector mode={runMode} onChange={onModeChange} disabled={isRunning} />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-500">Action</label>
          <RunButton selectedCount={selectedCount} isRunning={isRunning} onRun={onRun} />
        </div>

        {selectedCount === 0 && (
          <p className="text-center text-xs text-slate-400">
            Select tests from the left panel to run
          </p>
        )}
      </div>
    </div>
  );
}
