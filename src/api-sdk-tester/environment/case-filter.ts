import type { TestCase } from '../cases/types';

export interface CaseFilterEnv {
  key: string;
  value: string;
}

interface CaseSelector {
  provider?: string;
  caseIdPattern: RegExp;
}

function resolveCaseFilterEnv(): CaseFilterEnv | undefined {
  const keys = ['TARGET_CASES', 'TEST_CASES', 'CASE_IDS'];
  for (const key of keys) {
    const value = process.env[key]?.trim();
    if (value) {
      return { key, value };
    }
  }
  return undefined;
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normalizeProviderSelector(raw: string): string {
  const normalized = raw.trim().toLowerCase();
  if (normalized === 'claude') {
    return 'anthropic';
  }
  if (normalized === 'claudeagent') {
    return 'claude-agent';
  }
  return normalized;
}

function buildCaseIdPattern(raw: string): RegExp {
  const source = raw.trim() || '*';
  const regexSource = escapeRegExp(source).replace(/\\\*/g, '.*').replace(/\\\?/g, '.');
  return new RegExp(`^${regexSource}$`);
}

function parseCaseSelectors(raw: string): CaseSelector[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const separatorIndex = item.indexOf(':');
      if (separatorIndex <= 0) {
        return {
          caseIdPattern: buildCaseIdPattern(item),
        };
      }

      const providerPart = normalizeProviderSelector(item.slice(0, separatorIndex));
      const casePart = item.slice(separatorIndex + 1).trim();
      return {
        provider: providerPart,
        caseIdPattern: buildCaseIdPattern(casePart),
      };
    });
}

function matchesProviderSelector(provider: string, selectorProvider: string): boolean {
  const normalizedProvider = provider.trim().toLowerCase();
  if (normalizedProvider === selectorProvider) {
    return true;
  }
  return normalizedProvider.startsWith(`${selectorProvider}(`);
}

export function applyCaseFilter(
  provider: string,
  cases: readonly TestCase[],
): {
  filteredCases: readonly TestCase[];
  filterEnv?: CaseFilterEnv;
} {
  const filterEnv = resolveCaseFilterEnv();
  if (!filterEnv) {
    return { filteredCases: cases };
  }

  const selectors = parseCaseSelectors(filterEnv.value);
  if (selectors.length === 0) {
    return { filteredCases: cases, filterEnv };
  }

  const filteredCases = cases.filter((testCase) =>
    selectors.some((selector) => {
      if (selector.provider && !matchesProviderSelector(provider, selector.provider)) {
        return false;
      }
      return selector.caseIdPattern.test(testCase.id);
    }),
  );

  return {
    filteredCases,
    filterEnv,
  };
}
