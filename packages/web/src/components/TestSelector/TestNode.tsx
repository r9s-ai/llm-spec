import { Checkbox } from "../UI";

interface TestNodeProps {
  testName: string;
  tags: string[];
  isSelected: boolean;
  isHighlighted?: boolean;
  onToggle: (checked: boolean) => void;
}

export function TestNode({
  testName,
  tags,
  isSelected,
  isHighlighted = false,
  onToggle,
}: TestNodeProps) {
  const visibleTags = tags.slice(0, 2);
  const overflowTagCount = tags.length - visibleTags.length;

  return (
    <div
      className={`group flex items-center gap-1 px-1.5 py-0.5 hover:bg-slate-50 ${
        isHighlighted ? "bg-yellow-50" : ""
      }`}
      style={{ paddingLeft: "24px" }}
    >
      <Checkbox checked={isSelected} onChange={(e) => onToggle(e.target.checked)} />

      {/* Render expanded test identifier (e.g. name[variant_id]) */}
      <span
        className="min-w-0 flex-1 truncate text-xs text-slate-600"
        title={testName}
      >
        {testName}
      </span>

      {visibleTags.map((tag) => (
        <span
          key={`${testName}:${tag}`}
          className="max-w-[90px] shrink-0 truncate rounded bg-emerald-50 px-1 py-0.5 text-[10px] text-emerald-700"
          title={tag}
        >
          {tag}
        </span>
      ))}

      {overflowTagCount > 0 && (
        <span className="shrink-0 rounded bg-slate-100 px-1 py-0.5 text-[10px] text-slate-500">
          +{overflowTagCount}
        </span>
      )}
    </div>
  );
}
