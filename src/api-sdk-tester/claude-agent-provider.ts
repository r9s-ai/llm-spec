import type { ProviderSummary } from '../types';
import { buildClaudeAgentCases, CLAUDE_AGENT_PARAMS } from './cases/anthropic';
import type { ClaudeAgentProviderConfig } from './runtime-config';
import {
  createSetupSkippedSummary,
  executeProviderCases,
  setCurrentProvider,
} from './shared';

export async function runClaudeAgentCases(
  config: ClaudeAgentProviderConfig,
  failFast: boolean,
): Promise<ProviderSummary> {
  setCurrentProvider('claude-agent');

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
  );
}
