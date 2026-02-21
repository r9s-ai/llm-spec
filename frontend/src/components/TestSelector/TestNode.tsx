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
      className={`group flex items-center gap-1 px-1.5 py-0.5 hover:bg-slate-50 ${
        isHighlighted ? "bg-yellow-50" : ""
      }`}
      style={{ paddingLeft: "24px" }}
    >
      <Checkbox checked={isSelected} onChange={(e) => onToggle(e.target.checked)} />

      {/* Test name - allow more space */}
      <span
        className="min-w-0 flex-1 truncate text-xs text-slate-600"
        title={`${testName} - ${paramName}`}
      >
        {paramName}
      </span>

      {/* Value badge - compact */}
      {valueText && (
        <span
          className="max-w-[80px] shrink-0 truncate rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-500"
          title={valueText}
        >
          {valueText}
        </span>
      )}
    </div>
  );
}
