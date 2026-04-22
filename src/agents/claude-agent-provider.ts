import type { ProviderSummary } from '../types';
import {
  buildClaudeAgentCases,
  CLAUDE_AGENT_PARAMS,
  getClaudeAgentCaseHttpTrace,
  resetClaudeAgentCaseHttpTraces,
} from '../api-sdk-tester/cases/anthropic';
import { startClaudeAgentReverseProxy } from '../api-sdk-tester/claude-agent-reverse-proxy';
import type { ClaudeAgentProviderConfig } from '../api-sdk-tester/environment';
import {
  setCurrentProvider,
} from '../api-sdk-tester/environment';
import { createSetupSkippedSummary, executeProviderCases } from '../api-sdk-tester/cases/runtime';

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

  const proxy = await startClaudeAgentReverseProxy(config.apiBaseUrl);
  const proxiedConfig: ClaudeAgentProviderConfig = {
    ...config,
    apiBaseUrl: proxy.baseUrl,
  };

  try {
    const cases = buildClaudeAgentCases({ config: proxiedConfig });

    const summary = await executeProviderCases(
      'claude-agent',
      'agent',
      config.apiBaseUrl,
      CLAUDE_AGENT_PARAMS,
      cases,
      failFast,
      concurrency,
    );

    return {
      ...summary,
      caseResults: summary.caseResults.map((result) => ({
        ...result,
        httpTrace: getClaudeAgentCaseHttpTrace(result.id),
      })),
    };
  } finally {
    await proxy.close();
  }
}
