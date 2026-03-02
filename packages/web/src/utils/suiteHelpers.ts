import type { Suite, TestRow } from "../types";

/**
 * 从 Suite.route_suite 中提取测试行信息
 */
export function getTestRows(suite: Suite | undefined): TestRow[] {
  if (!suite) return [];
  const tests = suite.route_suite.tests;
  if (!Array.isArray(tests)) return [];

  return tests
    .map((item) => {
      if (typeof item !== "object" || !item) return null;
      const obj = item as Record<string, unknown>;
      const name = typeof obj.name === "string" ? obj.name : "unknown";
      const tp = (obj.focus_param ?? {}) as Record<string, unknown>;
      const paramName = typeof tp.name === "string" ? tp.name : "baseline";
      const valueText = tp.value === undefined ? "-" : JSON.stringify(tp.value);
      const tags = Array.isArray(obj.tags)
        ? obj.tags.filter((tag): tag is string => typeof tag === "string")
        : [];
      return { name, paramName, valueText, tags };
    })
    .filter((it): it is TestRow => Boolean(it));
}

/**
 * 检查 suite name 是否是重复的默认名称
 */
export function isDuplicateName(suiteName: string, provider: string, endpoint: string): boolean {
  const normalizedName = suiteName.trim().toLowerCase();
  return (
    normalizedName === `${provider} ${endpoint}`.toLowerCase() ||
    normalizedName === endpoint.toLowerCase()
  );
}
