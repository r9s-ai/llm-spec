import { Checkbox } from "../UI";
import { getTagClassName } from "../../utils";

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
  return (
    <div
      className={`group flex items-start gap-2 rounded-lg px-2.5 py-2 transition-colors hover:bg-slate-50 ${
        isHighlighted ? "bg-amber-50/80" : ""
      }`}
      style={{ paddingLeft: "28px" }}
    >
      <div className="pt-0.5">
        <Checkbox checked={isSelected} onChange={(e) => onToggle(e.target.checked)} />
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        <div
          className="text-sm font-medium leading-snug text-slate-700 break-words"
          title={testName}
        >
          {testName}
        </div>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={`${testName}:${tag}`}
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium leading-none ${getTagClassName(tag)}`}
                title={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
