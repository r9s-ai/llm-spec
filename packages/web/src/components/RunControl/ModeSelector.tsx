import type { RunMode } from "../../types";

interface ModeSelectorProps {
  mode: RunMode;
  onChange: (mode: RunMode) => void;
  disabled?: boolean;
}

export function ModeSelector({ mode, onChange, disabled = false }: ModeSelectorProps) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-1">
      <button
        onClick={() => onChange("real")}
        disabled={disabled}
        className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all ${
          mode === "real"
            ? "bg-white text-slate-900 shadow-sm"
            : "text-slate-500 hover:text-slate-700"
        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <span className="flex items-center justify-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-green-500" />
          Real
        </span>
      </button>
      <button
        onClick={() => onChange("mock")}
        disabled={disabled}
        className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all ${
          mode === "mock"
            ? "bg-white text-slate-900 shadow-sm"
            : "text-slate-500 hover:text-slate-700"
        } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <span className="flex items-center justify-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          Mock
        </span>
      </button>
    </div>
  );
}
