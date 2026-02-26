interface ProgressBarProps {
  progress: number; // 0-100
  variant?: "default" | "success" | "error" | "running";
  size?: "sm" | "md";
}

const variantStyles = {
  default: "bg-slate-300",
  success: "bg-green-500",
  error: "bg-red-500",
  running: "bg-violet-500",
};

const sizeStyles = {
  sm: "h-1.5",
  md: "h-2.5",
};

export function ProgressBar({ progress, variant = "default", size = "md" }: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className={`w-full overflow-hidden rounded-full bg-slate-200 ${sizeStyles[size]}`}>
      <div
        className={`${variantStyles[variant]} ${sizeStyles[size]} rounded-full transition-all duration-300 ease-out`}
        style={{ width: `${clampedProgress}%` }}
      />
    </div>
  );
}
