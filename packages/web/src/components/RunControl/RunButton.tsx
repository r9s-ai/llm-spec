interface RunButtonProps {
  selectedCount: number;
  isRunning: boolean;
  onRun: () => void;
}

export function RunButton({ selectedCount, isRunning, onRun }: RunButtonProps) {
  return (
    <button
      onClick={onRun}
      disabled={selectedCount === 0 || isRunning}
      className={`flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold transition-all ${
        selectedCount > 0 && !isRunning
          ? "bg-violet-600 text-white shadow-lg shadow-violet-200 hover:bg-violet-700 active:scale-[0.98]"
          : "cursor-not-allowed bg-slate-200 text-slate-400"
      }`}
    >
      {isRunning ? (
        <>
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
          Running...
        </>
      ) : (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          Run {selectedCount} test{selectedCount !== 1 ? "s" : ""}
        </>
      )}
    </button>
  );
}
