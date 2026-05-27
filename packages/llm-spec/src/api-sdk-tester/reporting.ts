import type {
  HttpTraceExchange,
  ProviderSummary,
  RunSummary,
  TestCaseHttpTrace,
  TestCaseResult,
  TestStatus,
} from '../types';
import type { RuntimeConfig } from './environment';

function printProviderHeader(name: string): void {
  console.log('\n============================================================');
  console.log(name);
  console.log('============================================================');
}

function isAgentProvider(provider: string): boolean {
  return provider.includes('claude-agent') || provider.includes('codex');
}

function formatProviderName(provider: string): string {
  if (provider.includes('claude-agent')) {
    return '🤖 [AGENT] claude-agent';
  }
  if (provider.includes('codex')) {
    return '🤖 [AGENT] codex';
  }
  return provider;
}

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatCoverage(covered: number, total: number): string {
  if (total <= 0) {
    return '0/0 (0.0%)';
  }
  const percent = ((covered / total) * 100).toFixed(1);
  return `${covered}/${total} (${percent}%)`;
}

const CLAUDE_AGENT_BETA_CASE_ANNOTATIONS: Readonly<Record<string, readonly string[]>> = {
  beta_context_1m_basic: ['context-1m-2025-08-07'],
  beta_context_1m_with_session: ['context-1m-2025-08-07'],
  beta_context_1m_system_message: ['context-1m-2025-08-07'],
  beta_context_1m_opus: ['context-1m-2025-08-07'],
  beta_context_1m_haiku: ['context-1m-2025-08-07'],
  beta_invalid_feature: ['invalid-beta-feature-xyz'],
  beta_empty_array: [],
  beta_with_tools: ['context-1m-2025-08-07'],
  beta_context_1m_streaming: ['context-1m-2025-08-07'],
  beta_context_1m_multi_turn: ['context-1m-2025-08-07'],
  beta_context_1m_resume_session: ['context-1m-2025-08-07'],
  beta_context_1m_with_custom_env: ['context-1m-2025-08-07'],
  beta_context_1m_error_recovery: ['context-1m-2025-08-07'],
  beta_thinking_adaptive: ['interleaved-thinking-2025-05-14'],
  beta_thinking_enabled: ['interleaved-thinking-2025-05-14'],
  beta_thinking_disabled: ['interleaved-thinking-2025-05-14'],
  beta_effort_low: ['effort-2025-11-24'],
  beta_effort_high: ['effort-2025-11-24'],
  beta_effort_max: ['effort-2025-11-24'],
  beta_effort_with_thinking: ['effort-2025-11-24', 'interleaved-thinking-2025-05-14'],
  beta_mcp_servers_config: ['mcp-servers-2025-12-04'],
  beta_context_1m_with_effort: ['context-1m-2025-08-07', 'effort-2025-11-24'],
  beta_thinking_effort_context_1m: [
    'context-1m-2025-08-07',
    'interleaved-thinking-2025-05-14',
    'effort-2025-11-24',
  ],
};

function getCaseBetaAnnotation(provider: string, caseId: string): readonly string[] | undefined {
  if (!provider.includes('claude-agent')) {
    return undefined;
  }
  return CLAUDE_AGENT_BETA_CASE_ANNOTATIONS[caseId];
}

function formatCaseNote(result: TestCaseResult): string | undefined {
  if (result.error) {
    return `error: ${result.error}`;
  }
  return result.detail;
}

function formatStatus(status: TestStatus): string {
  return status.toUpperCase();
}

function statusClassName(status: TestStatus): string {
  if (status === 'passed') {
    return 'status-passed';
  }
  if (status === 'failed') {
    return 'status-failed';
  }
  return 'status-skipped';
}

function maskSecret(value: string | undefined): string {
  if (!value) {
    return '(empty)';
  }
  if (value.length <= 6) {
    return `${value[0]}***`;
  }
  return `${value.slice(0, 3)}***${value.slice(-3)}`;
}

const HTTP_TRACE_PREVIEW_LIMIT = 4000;

function truncateTracePreview(value: string): string {
  if (value.length <= HTTP_TRACE_PREVIEW_LIMIT) {
    return value;
  }
  return `${value.slice(0, HTTP_TRACE_PREVIEW_LIMIT - 15)}\n...[truncated]`;
}

function formatTracePayload(value: string | undefined): string {
  if (!value) {
    return '(none)';
  }
  return truncateTracePreview(value);
}

function formatTraceHeaders(headers: Record<string, string>): string {
  if (Object.keys(headers).length === 0) {
    return '(none)';
  }
  return truncateTracePreview(JSON.stringify(headers, null, 2));
}

function appendTraceBlock(
  lines: string[],
  prefix: string,
  label: string,
  value: string,
): void {
  lines.push(`${prefix}${label}:`);
  for (const line of value.split('\n')) {
    lines.push(`${prefix}  ${line}`);
  }
}

function appendHttpTraceText(lines: string[], trace: TestCaseHttpTrace | undefined): void {
  if (!trace) {
    return;
  }

  lines.push(`  httpTrace: testId=${trace.testId}, exchanges=${trace.exchangeCount}, source=${trace.source}`);
  if (trace.exchanges.length === 0) {
    lines.push('  httpTraceDetail: no matching request/response found in requests.log');
    return;
  }

  trace.exchanges.forEach((exchange, index) => {
    const responseSummary = exchange.response
      ? exchange.response.kind === 'error'
        ? `error=${exchange.response.error ?? '(unknown)'}`
        : `status=${exchange.response.status ?? '(unknown)'} ${exchange.response.statusText ?? ''}`.trim()
      : 'response=(missing)';

    lines.push(`  http[${index + 1}]: ${exchange.request.method} ${exchange.request.url} | ${responseSummary}`);
    appendTraceBlock(lines, '    ', 'requestHeaders', formatTraceHeaders(exchange.request.headers));
    appendTraceBlock(lines, '    ', 'requestBody', formatTracePayload(exchange.request.body));

    if (exchange.response) {
      appendTraceBlock(lines, '    ', 'responseHeaders', formatTraceHeaders(exchange.response.headers));
      appendTraceBlock(lines, '    ', 'responseBody', formatTracePayload(exchange.response.body));
      if (exchange.response.kind === 'error' && exchange.response.error) {
        appendTraceBlock(lines, '    ', 'responseError', truncateTracePreview(exchange.response.error));
      }
    }
  });
}

function renderHttpTraceExchangeHtml(exchange: HttpTraceExchange, index: number): string {
  const responseSummary = exchange.response
    ? exchange.response.kind === 'error'
      ? `error=${exchange.response.error ?? '(unknown)'}`
      : `status=${exchange.response.status ?? '(unknown)'} ${exchange.response.statusText ?? ''}`.trim()
    : 'response=(missing)';

  const responseBody = exchange.response
    ? `<div class="trace-section">
  <div class="trace-label">Response Body</div>
  <pre class="trace-block">${escapeHtml(formatTracePayload(exchange.response.body))}</pre>
</div>`
    : '';

  const responseHeaders = exchange.response
    ? `<div class="trace-section">
  <div class="trace-label">Response Headers</div>
  <pre class="trace-block">${escapeHtml(formatTraceHeaders(exchange.response.headers))}</pre>
</div>`
    : '';

  const responseError = exchange.response?.kind === 'error' && exchange.response.error
    ? `<div class="trace-section">
  <div class="trace-label">Response Error</div>
  <pre class="trace-block">${escapeHtml(truncateTracePreview(exchange.response.error))}</pre>
</div>`
    : '';

  return `<div class="trace-entry">
  <div class="trace-title">HTTP ${index + 1}: ${escapeHtml(exchange.request.method)} ${escapeHtml(exchange.request.url)}</div>
  <div class="trace-summary">${escapeHtml(responseSummary)}</div>
  <div class="trace-section">
    <div class="trace-label">Request Headers</div>
    <pre class="trace-block">${escapeHtml(formatTraceHeaders(exchange.request.headers))}</pre>
  </div>
  <div class="trace-section">
    <div class="trace-label">Request Body</div>
    <pre class="trace-block">${escapeHtml(formatTracePayload(exchange.request.body))}</pre>
  </div>
  ${responseHeaders}
  ${responseBody}
  ${responseError}
</div>`;
}

function renderHttpTraceHtml(trace: TestCaseHttpTrace | undefined): string {
  if (!trace) {
    return '';
  }

  if (trace.exchanges.length === 0) {
    return `<details class="http-trace">
  <summary>HTTP Trace | testId=${escapeHtml(trace.testId)} | exchanges=0</summary>
  <div class="trace-empty">No matching request/response found in requests.log.</div>
</details>`;
  }

  return `<details class="http-trace">
  <summary>HTTP Trace | testId=${escapeHtml(trace.testId)} | exchanges=${trace.exchangeCount}</summary>
  ${trace.exchanges.map((exchange, index) => renderHttpTraceExchangeHtml(exchange, index)).join('\n')}
</details>`;
}

export function printRuntimeConfig(config: RuntimeConfig): void {
  printProviderHeader('Runtime Config');
  if (config.testTarget) {
    console.log('mode: single target');
    console.log(`apiType: ${config.testTarget.apiType}`);
    console.log(`apiKey: ${maskSecret(config.testTarget.apiKey)}`);
    console.log(`apiBaseUrl: ${config.testTarget.apiBaseUrl ?? '(default)'}`);
    console.log(`model: ${config.testTarget.model}`);
    console.log(`timeoutMs: ${String(config.testTarget.timeoutMs)}`);
    if (config.testTarget.apiVersion) {
      console.log(`apiVersion: ${config.testTarget.apiVersion}`);
    }
  } else {
    console.log(`mode: provider matrix`);
    console.log(`providers: ${config.targetProviders.join(', ')}`);
  }
  console.log(`targetCases: ${config.targetCases ?? '(all)'}`);
  console.log(`failFast: ${String(config.failFast)}`);
  console.log(`concurrency: ${String(config.concurrency)}`);
  console.log(`reportFile: ${config.reportFile ?? '(none)'}`);
  console.log('');
  console.log('[openai]');
  console.log(`apiKey: ${maskSecret(config.openai.apiKey)}`);
  console.log(`apiBaseUrl: ${config.openai.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.openai.model}`);
  console.log(`audioModel: ${config.openai.audioModel ?? '(none)'}`);
  console.log(`timeoutMs: ${String(config.openai.timeoutMs)}`);
  console.log('');
  console.log('[xai]');
  console.log(`apiKey: ${maskSecret(config.xai.apiKey)}`);
  console.log(`apiBaseUrl: ${config.xai.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.xai.model}`);
  console.log(`timeoutMs: ${String(config.xai.timeoutMs)}`);
  console.log('');
  console.log('[anthropic]');
  console.log(`apiKey: ${maskSecret(config.anthropic.apiKey)}`);
  console.log(`apiBaseUrl: ${config.anthropic.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.anthropic.model}`);
  console.log(`container: ${config.anthropic.container ?? '(none)'}`);
  console.log(`inferenceGeo: ${config.anthropic.inferenceGeo ?? '(none)'}`);
  console.log(`timeoutMs: ${String(config.anthropic.timeoutMs)}`);
  console.log('');
  console.log('[gemini]');
  console.log(`apiKey: ${maskSecret(config.gemini.apiKey)}`);
  console.log(`apiBaseUrl: ${config.gemini.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.gemini.model}`);
  console.log(`apiVersion: ${config.gemini.apiVersion ?? '(default)'}`);
  console.log(`cachedContent: ${config.gemini.cachedContent ?? '(none)'}`);
  console.log(`audioModel: ${config.gemini.audioModel ?? '(none)'}`);
  console.log(`imageModel: ${config.gemini.imageModel ?? '(none)'}`);
  console.log(`vertexOnlyCases: ${String(config.gemini.enableVertexOnlyCases)}`);
  console.log(`timeoutMs: ${String(config.gemini.timeoutMs)}`);
  console.log('');
  console.log('[claude-agent]');
  console.log(`apiKey: ${maskSecret(config.claudeAgent.apiKey)}`);
  console.log(`apiBaseUrl: ${config.claudeAgent.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.claudeAgent.model}`);
  console.log(`workingDirectory: ${config.claudeAgent.workingDirectory}`);
  console.log(`skipGitRepoCheck: ${String(config.claudeAgent.skipGitRepoCheck)}`);
  console.log(`timeoutMs: ${String(config.claudeAgent.timeoutMs)}`);
  console.log('');
  console.log('[codex]');
  console.log(`apiKey: ${maskSecret(config.codex.apiKey)}`);
  console.log(`apiBaseUrl: ${config.codex.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.codex.model ?? '(default)'}`);
  console.log(`workingDirectory: ${config.codex.workingDirectory}`);
  console.log(`skipGitRepoCheck: ${String(config.codex.skipGitRepoCheck)}`);
  console.log(`timeoutMs: ${String(config.codex.timeoutMs)}`);
}

export function printProviderSummary(summary: ProviderSummary): void {
  const displayName = formatProviderName(summary.provider);
  const isAgent = isAgentProvider(summary.provider);

  if (isAgent) {
    console.log('\n' + '='.repeat(60));
    console.log('🤖 AGENT SDK TEST RESULTS');
    console.log('='.repeat(60));
  }

  printProviderHeader(`Provider Summary: ${displayName}`);
  console.log(`type: ${isAgent ? 'Agent SDK' : 'Standard API'}`);
  console.log(`model: ${summary.model}`);
  console.log(`baseUrl: ${summary.apiBaseUrl ?? '(default)'}`);
  if (summary.setupDetail) {
    console.log(`setup: ${summary.setupDetail}`);
  }
  console.log(`startedAt: ${summary.startedAt}`);
  console.log(`finishedAt: ${summary.finishedAt}`);
  console.log(`passed=${summary.passed} failed=${summary.failed} skipped=${summary.skipped}`);
  console.log(`covered params (${summary.coveredParams.length}/${summary.allParams.length}):`);
  console.log(summary.coveredParams.length > 0 ? summary.coveredParams.join(', ') : '(none)');
  if (summary.untestedParams.length > 0) {
    console.log(`untested params (${summary.untestedParams.length}):`);
    console.log(summary.untestedParams.join(', '));
  } else {
    console.log('untested params: none');
  }
}

export function printRunSummary(summary: RunSummary): void {
  printProviderHeader('Final Summary');
  console.log(`startedAt: ${summary.startedAt}`);
  console.log(`finishedAt: ${summary.finishedAt}`);
  console.log(`total passed: ${summary.totalPassed}`);
  console.log(`total failed: ${summary.totalFailed}`);
  console.log(`total skipped: ${summary.totalSkipped}`);
}

export function renderTextReport(summary: RunSummary): string {
  const lines: string[] = [];
  lines.push('='.repeat(60));
  lines.push('LLM Spec Test Report');
  lines.push('='.repeat(60));
  lines.push(`startedAt: ${summary.startedAt}`);
  lines.push(`finishedAt: ${summary.finishedAt}`);
  lines.push(`total: passed=${summary.totalPassed} failed=${summary.totalFailed} skipped=${summary.totalSkipped}`);

  // 分别统计Agent和Standard providers
  const agentProviders = summary.providers.filter(p => isAgentProvider(p.provider));
  const standardProviders = summary.providers.filter(p => !isAgentProvider(p.provider));

  // 先显示Standard API providers
  if (standardProviders.length > 0) {
    lines.push('');
    lines.push('='.repeat(60));
    lines.push('📊 STANDARD API PROVIDERS');
    lines.push('='.repeat(60));

    for (const provider of standardProviders) {
      lines.push('');
      lines.push(`Provider: ${provider.provider}`);
      lines.push(`model: ${provider.model}`);
      lines.push(`baseUrl: ${provider.apiBaseUrl ?? '(default)'}`);
      if (provider.setupDetail) {
        lines.push(`setup: ${provider.setupDetail}`);
      }
      lines.push(
        `coverage: ${formatCoverage(provider.coveredParams.length, provider.allParams.length)} | passed=${provider.passed} failed=${provider.failed} skipped=${provider.skipped}`,
      );
      lines.push(`coveredParams: ${provider.coveredParams.length > 0 ? provider.coveredParams.join(', ') : '(none)'}`);
      lines.push(
        `untestedParams: ${provider.untestedParams.length > 0 ? provider.untestedParams.join(', ') : '(none)'}`,
      );
      lines.push(`cases: ${provider.caseResults.length > 0 ? '' : '(none)'}`.trimEnd());

      for (const result of provider.caseResults) {
        lines.push(`- [${formatStatus(result.status)}] ${result.id} (${formatDuration(result.durationMs)})`);
        lines.push(`  description: ${result.description}`);
        if (result.protocol) {
          lines.push(`  protocol: ${result.protocol}`);
        }
        if (result.modelScope) {
          lines.push(`  modelScope: ${result.modelScope}`);
        }
        lines.push(`  covered: ${result.coveredParams.length > 0 ? result.coveredParams.join(', ') : '(none)'}`);
        const betaAnnotation = getCaseBetaAnnotation(provider.provider, result.id);
        if (betaAnnotation) {
          lines.push(`  beta: ${betaAnnotation.length > 0 ? betaAnnotation.join(', ') : '(none)'}`);
        }
        const note = formatCaseNote(result);
        if (note) {
          lines.push(`  note: ${note}`);
        }
        appendHttpTraceText(lines, result.httpTrace);
      }
    }
  }

  // 再显示Agent SDK providers (突出显示)
  if (agentProviders.length > 0) {
    lines.push('');
    lines.push('='.repeat(60));
    lines.push('🤖 AGENT SDK PROVIDERS (NEW!)');
    lines.push('='.repeat(60));

    for (const provider of agentProviders) {
      lines.push('');
      lines.push(`🤖 Agent: ${formatProviderName(provider.provider)}`);
      lines.push(`type: Agent SDK`);
      lines.push(`model: ${provider.model}`);
      lines.push(`baseUrl: ${provider.apiBaseUrl ?? '(default)'}`);
      if (provider.setupDetail) {
        lines.push(`setup: ${provider.setupDetail}`);
      }
      lines.push(
        `coverage: ${formatCoverage(provider.coveredParams.length, provider.allParams.length)} | passed=${provider.passed} failed=${provider.failed} skipped=${provider.skipped}`,
      );
      lines.push(`coveredParams: ${provider.coveredParams.length > 0 ? provider.coveredParams.join(', ') : '(none)'}`);
      lines.push(
        `untestedParams: ${provider.untestedParams.length > 0 ? provider.untestedParams.join(', ') : '(none)'}`,
      );
      lines.push(`cases: ${provider.caseResults.length > 0 ? '' : '(none)'}`.trimEnd());

      for (const result of provider.caseResults) {
        lines.push(`- [${formatStatus(result.status)}] ${result.id} (${formatDuration(result.durationMs)})`);
        lines.push(`  description: ${result.description}`);
        if (result.protocol) {
          lines.push(`  protocol: ${result.protocol}`);
        }
        if (result.modelScope) {
          lines.push(`  modelScope: ${result.modelScope}`);
        }
        lines.push(`  covered: ${result.coveredParams.length > 0 ? result.coveredParams.join(', ') : '(none)'}`);
        const betaAnnotation = getCaseBetaAnnotation(provider.provider, result.id);
        if (betaAnnotation) {
          lines.push(`  beta: ${betaAnnotation.length > 0 ? betaAnnotation.join(', ') : '(none)'}`);
        }
        const note = formatCaseNote(result);
        if (note) {
          lines.push(`  note: ${note}`);
        }
        appendHttpTraceText(lines, result.httpTrace);
      }
    }
  }

  return `${lines.join('\n')}\n`;
}

export function renderHtmlReport(summary: RunSummary): string {
  const providerSections = summary.providers
    .map((provider) => {
      const isAgent = isAgentProvider(provider.provider);
      const displayName = formatProviderName(provider.provider);

      const caseRows = provider.caseResults
        .map((result) => {
          const note = formatCaseNote(result);
          const betaAnnotation = getCaseBetaAnnotation(provider.provider, result.id);
          const betaLine = betaAnnotation
            ? `<div class="beta-note">beta: ${escapeHtml(betaAnnotation.length > 0 ? betaAnnotation.join(', ') : '(none)')}</div>`
            : '';
          const httpTrace = renderHttpTraceHtml(result.httpTrace);
          const noteContent = note
            ? `<pre class="note">${escapeHtml(note)}</pre>`
            : httpTrace
              ? ''
              : '<span class="muted">(none)</span>';
          const scopeLines = [
            result.protocol ? `<div class="case-meta">protocol: ${escapeHtml(result.protocol)}</div>` : '',
            result.modelScope ? `<div class="case-meta">modelScope: ${escapeHtml(result.modelScope)}</div>` : '',
          ]
            .filter(Boolean)
            .join('');
          return `<tr>
  <td><code>${escapeHtml(result.id)}</code><br><span class="muted">${escapeHtml(result.description)}</span></td>
  <td><span class="status ${statusClassName(result.status)}">${formatStatus(result.status)}</span></td>
  <td>${escapeHtml(formatDuration(result.durationMs))}</td>
  <td>${escapeHtml(result.coveredParams.length > 0 ? result.coveredParams.join(', ') : '(none)')}</td>
  <td>${scopeLines}${betaLine}${noteContent}${httpTrace}</td>
</tr>`;
        })
        .join('\n');

      const agentBadge = isAgent
        ? '<span class="agent-badge">🤖 AGENT SDK</span>'
        : '';

      const providerClass = isAgent ? 'provider agent-provider' : 'provider';
      const setupDetail = provider.setupDetail
        ? `<p class="meta">setup: ${escapeHtml(provider.setupDetail)}</p>`
        : '';
      const caseTable = provider.caseResults.length > 0
        ? `<table>
<thead>
<tr>
  <th>Case</th>
  <th>Status</th>
  <th>Duration</th>
  <th>Covered Params</th>
  <th>Detail/Error</th>
</tr>
</thead>
<tbody>
${caseRows}
</tbody>
</table>`
        : '<p class="muted">No test cases recorded.</p>';

      return `<section class="${providerClass}">
<h2>${agentBadge}${escapeHtml(displayName)}</h2>
<p class="meta">
  <span class="provider-type">${isAgent ? 'Agent SDK' : 'Standard API'}</span> |
  model=${escapeHtml(provider.model)} |
  baseUrl=${escapeHtml(provider.apiBaseUrl ?? '(default)')} |
  coverage=${escapeHtml(formatCoverage(provider.coveredParams.length, provider.allParams.length))} |
  passed=${provider.passed} failed=${provider.failed} skipped=${provider.skipped}
</p>
<details>
<summary>covered params (${provider.coveredParams.length})</summary>
<pre class="params">${escapeHtml(provider.coveredParams.length > 0 ? provider.coveredParams.join(', ') : '(none)')}</pre>
</details>
<details>
<summary>untested params (${provider.untestedParams.length})</summary>
<pre class="params">${escapeHtml(provider.untestedParams.length > 0 ? provider.untestedParams.join(', ') : '(none)')}</pre>
</details>
${setupDetail}
${caseTable}
</section>`;
    })
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM Spec Test Report</title>
<style>
  :root {
    color-scheme: light;
    font-family: "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
  }
  body {
    margin: 0;
    padding: 20px;
    line-height: 1.45;
    background: #f6f8fa;
    color: #0f172a;
  }
  .layout {
    max-width: 1240px;
    margin: 0 auto;
    background: #fff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 20px;
  }
  h1, h2 {
    margin: 0 0 10px 0;
  }
  h2 {
    margin-top: 24px;
    font-size: 18px;
  }
  .summary {
    margin-bottom: 12px;
    padding: 12px;
    background: #f1f8ff;
    border: 1px solid #c6e2ff;
    border-radius: 6px;
  }
  .meta, .muted {
    color: #475569;
    font-size: 13px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    font-size: 13px;
    table-layout: fixed;
  }
  th, td {
    border: 1px solid #d0d7de;
    padding: 8px;
    vertical-align: top;
    text-align: left;
  }
  th {
    background: #f8fafc;
  }
  .status {
    display: inline-block;
    min-width: 54px;
    text-align: center;
    border-radius: 999px;
    padding: 2px 8px;
    font-weight: 700;
    font-size: 12px;
  }
  .status-passed {
    color: #0f5132;
    background: #d1e7dd;
  }
  .status-failed {
    color: #842029;
    background: #f8d7da;
  }
  .status-skipped {
    color: #664d03;
    background: #fff3cd;
  }
  .provider {
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px dashed #cbd5e1;
  }
  .provider:first-of-type {
    border-top: none;
    margin-top: 0;
    padding-top: 0;
  }
  .agent-provider {
    background: linear-gradient(135deg, #fff9e6 0%, #fff 100%);
    border: 2px solid #ffc107;
    border-radius: 8px;
    padding: 20px;
    margin-top: 24px;
    box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
  }
  .agent-badge {
    display: inline-block;
    background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
    color: #fff;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
    margin-right: 8px;
    box-shadow: 0 2px 4px rgba(255, 152, 0, 0.3);
    vertical-align: middle;
  }
  .provider-type {
    display: inline-block;
    background: #e3f2fd;
    color: #1976d2;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 8px;
  }
  .case-meta {
    color: #475569;
    font-size: 12px;
    margin-bottom: 4px;
  }
  details {
    margin-top: 8px;
  }
  .params, .note {
    margin: 6px 0 0 0;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    background: #f8fafc;
    border: 1px solid #d0d7de;
    border-radius: 4px;
    padding: 6px;
    font-size: 12px;
    font-family: inherit;
  }
  .beta-note {
    margin-top: 6px;
    padding: 4px 6px;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    background: #fff7ed;
    border: 1px solid #fdba74;
    border-radius: 4px;
    color: #9a3412;
    font-size: 12px;
  }
  .http-trace {
    margin-top: 8px;
  }
  .trace-entry {
    margin-top: 8px;
    padding: 8px;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    background: #ffffff;
  }
  .trace-title {
    font-weight: 700;
    margin-bottom: 4px;
  }
  .trace-summary, .trace-label, .trace-empty {
    color: #475569;
    font-size: 12px;
  }
  .trace-label {
    margin: 6px 0 4px 0;
    font-weight: 600;
  }
  .trace-block {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    background: #f8fafc;
    border: 1px solid #d0d7de;
    border-radius: 4px;
    padding: 6px;
    font-size: 12px;
    font-family: inherit;
  }
</style>
</head>
<body>
<main class="layout">
  <h1>LLM Spec Test Report</h1>
  <div class="summary">
    <div>startedAt: ${escapeHtml(summary.startedAt)}</div>
    <div>finishedAt: ${escapeHtml(summary.finishedAt)}</div>
    <div>total: passed=${summary.totalPassed} failed=${summary.totalFailed} skipped=${summary.totalSkipped}</div>
  </div>
  ${providerSections}
</main>
</body>
</html>
`;
}
