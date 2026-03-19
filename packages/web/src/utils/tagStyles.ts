const TAG_CLASS_MAP: Record<string, string> = {
  baseline: "border-slate-300 bg-slate-100 text-slate-700",
  parameter: "border-blue-200 bg-blue-50 text-blue-700",
  scenario: "border-emerald-200 bg-emerald-50 text-emerald-700",
  edge: "border-amber-200 bg-amber-50 text-amber-700",
  compatibility: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
  streaming: "border-cyan-200 bg-cyan-50 text-cyan-700",
  tooling: "border-indigo-200 bg-indigo-50 text-indigo-700",
  multimodal: "border-rose-200 bg-rose-50 text-rose-700",
  "structured-output": "border-teal-200 bg-teal-50 text-teal-700",
  reasoning: "border-violet-200 bg-violet-50 text-violet-700",
};

const DEFAULT_TAG_CLASS = "border-slate-200 bg-slate-50 text-slate-600";

export function getTagClassName(tag: string): string {
  return TAG_CLASS_MAP[tag] ?? DEFAULT_TAG_CLASS;
}
