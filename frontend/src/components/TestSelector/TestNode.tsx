import { Checkbox } from "../UI";

interface TestNodeProps {
  testName: string;
  paramName: string;
  valueText: string;
  isSelected: boolean;
  isHighlighted?: boolean;
  onToggle: (checked: boolean) => void;
}

export function TestNode({
  testName,
  paramName,
  valueText,
  isSelected,
  isHighlighted = false,
  onToggle,
}: TestNodeProps) {
  return (
    <div
      className={`group flex items-center gap-2 px-2 py-1.5 transition-colors hover:bg-slate-50 ${
        isHighlighted ? "bg-yellow-50" : ""
      }`}
      style={{ paddingLeft: "32px" }}
    >
      <Checkbox checked={isSelected} onChange={(e) => onToggle(e.target.checked)} />

      <div className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-slate-700" title={testName}>
          {paramName}
        </span>
      </div>

      {valueText && (
        <span
          className="max-w-[120px] truncate rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500"
          title={valueText}
        >
          {valueText}
        </span>
      )}
    </div>
  );
}
