import type { SuiteVersion, TestRow, VersionsMap } from "../types";

/**
 * 从 SuiteVersion 中提取测试行信息
 */
export function getTestRows(version: SuiteVersion | undefined): TestRow[] {
  if (!version) return [];
  const tests = version.parsed_json.tests;
  if (!Array.isArray(tests)) return [];

  return tests
    .map((item) => {
      if (typeof item !== "object" || !item) return null;
      const obj = item as Record<string, unknown>;
      const name = typeof obj.name === "string" ? obj.name : "unknown";
      const tp = (obj.focus_param ?? {}) as Record<string, unknown>;
      const paramName = typeof tp.name === "string" ? tp.name : "baseline";
      const valueText = tp.value === undefined ? "-" : JSON.stringify(tp.value);
      return { name, paramName, valueText };
    })
    .filter((it): it is TestRow => Boolean(it));
}

/**
 * 根据 versionId 获取对应的 SuiteVersion
 */
export function getVersionById(
  versionsBySuite: VersionsMap,
  suiteId: string,
  versionId?: string
): SuiteVersion | undefined {
  const versions = versionsBySuite[suiteId] ?? [];
  if (versions.length === 0) return undefined;
  if (!versionId) return versions[0];
  return versions.find((v) => v.id === versionId) ?? versions[0];
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
