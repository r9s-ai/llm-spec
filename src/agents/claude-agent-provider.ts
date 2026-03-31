import type { ProviderSummary } from '../types';
import {
  buildClaudeAgentCases,
  CLAUDE_AGENT_PARAMS,
  getClaudeAgentCaseHttpTrace,
  resetClaudeAgentCaseHttpTraces,
} from '../api-sdk-tester/cases/anthropic';
import type { ClaudeAgentProviderConfig } from '../api-sdk-tester/runtime-config';
import {
  createSetupSkippedSummary,
  executeProviderCases,
  setCurrentProvider,
} from '../api-sdk-tester/shared';

export async function runClaudeAgentCases(
  config: ClaudeAgentProviderConfig,
  failFast: boolean,
  concurrency: number = 1,
): Promise<ProviderSummary> {
  setCurrentProvider('claude-agent');
  resetClaudeAgentCaseHttpTraces();

  if (!config.apiKey) {
    return createSetupSkippedSummary(
      'claude-agent',
      'agent',
      config.apiBaseUrl,
      CLAUDE_AGENT_PARAMS,
      'missing API key (set CLAUDE_AGENT_API_KEY, ANTHROPIC_API_KEY, or API_KEY)',
    );
  }

  const cases = buildClaudeAgentCases({ config });

  return executeProviderCases(
    'claude-agent',
    'agent',
    config.apiBaseUrl,
    CLAUDE_AGENT_PARAMS,
    cases,
    failFast,
    concurrency,
  ).then((summary) => ({
    ...summary,
    caseResults: summary.caseResults.map((result) => ({
      ...result,
      httpTrace: getClaudeAgentCaseHttpTrace(result.id),
    })),
  }));
}
