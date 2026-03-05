import type { Suite, TestRow } from "../types";

/**
 * 从 Suite.tests 中提取测试行信息
 */
export function getTestRows(suite: Suite | undefined): TestRow[] {
  if (!suite) return [];
  const tests = suite.tests;
  if (!Array.isArray(tests)) return [];

  return tests.map((t) => {
    const name = t.name;
    const paramName = t.focus_name ?? "baseline";
    const valueText = t.focus_value === undefined || t.focus_value === null ? "-" : JSON.stringify(t.focus_value);
    const tags = t.tags ?? [];
    return { name, paramName, valueText, tags };
  });
}

/**
 * 检查 suite name 是否是重复的默认名称
 */
export function isDuplicateName(suiteName: string, providerId: string, endpoint: string): boolean {
  const normalizedName = suiteName.trim().toLowerCase();
  return (
    normalizedName === `${providerId} ${endpoint}`.toLowerCase() ||
    normalizedName === endpoint.toLowerCase()
  );
}
