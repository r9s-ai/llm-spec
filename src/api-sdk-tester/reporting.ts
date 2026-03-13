import type { ProviderSummary, RunSummary, TestCaseResult, TestStatus } from '../types';
import type { RuntimeConfig } from './runtime-config';

function printProviderHeader(name: string): void {
  console.log('\n============================================================');
  console.log(name);
  console.log('============================================================');
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

export function printRuntimeConfig(config: RuntimeConfig): void {
  printProviderHeader('Runtime Config');
  console.log(`providers: ${config.targetProviders.join(', ')}`);
  console.log(`failFast: ${String(config.failFast)}`);
  console.log(`reportFile: ${config.reportFile ?? '(none)'}`);
  console.log('');
  console.log('[openai]');
  console.log(`apiKey: ${maskSecret(config.openai.apiKey)}`);
  console.log(`apiBaseUrl: ${config.openai.apiBaseUrl ?? '(default)'}`);
  console.log(`model: ${config.openai.model}`);
  console.log(`audioModel: ${config.openai.audioModel ?? '(none)'}`);
  console.log(`timeoutMs: ${String(config.openai.timeoutMs)}`);
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
}

export function printProviderSummary(summary: ProviderSummary): void {
  printProviderHeader(`Provider Summary: ${summary.provider}`);
  console.log(`model: ${summary.model}`);
  console.log(`baseUrl: ${summary.apiBaseUrl ?? '(default)'}`);
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
  lines.push('LLM Spec Test Report');
  lines.push(`startedAt: ${summary.startedAt}`);
  lines.push(`finishedAt: ${summary.finishedAt}`);
  lines.push(`total: passed=${summary.totalPassed} failed=${summary.totalFailed} skipped=${summary.totalSkipped}`);

  for (const provider of summary.providers) {
    lines.push('');
    lines.push(`Provider: ${provider.provider}`);
    lines.push(`model: ${provider.model}`);
    lines.push(`baseUrl: ${provider.apiBaseUrl ?? '(default)'}`);
    lines.push(
      `coverage: ${formatCoverage(provider.coveredParams.length, provider.allParams.length)} | passed=${provider.passed} failed=${provider.failed} skipped=${provider.skipped}`,
    );
    lines.push(`coveredParams: ${provider.coveredParams.length > 0 ? provider.coveredParams.join(', ') : '(none)'}`);
    lines.push(
      `untestedParams: ${provider.untestedParams.length > 0 ? provider.untestedParams.join(', ') : '(none)'}`,
    );
    lines.push('cases:');

    for (const result of provider.caseResults) {
      lines.push(`- [${formatStatus(result.status)}] ${result.id} (${formatDuration(result.durationMs)})`);
      lines.push(`  description: ${result.description}`);
      lines.push(`  covered: ${result.coveredParams.length > 0 ? result.coveredParams.join(', ') : '(none)'}`);
      const note = formatCaseNote(result);
      if (note) {
        lines.push(`  note: ${note}`);
      }
    }
  }

  return `${lines.join('\n')}\n`;
}

export function renderHtmlReport(summary: RunSummary): string {
  const providerSections = summary.providers
    .map((provider) => {
      const caseRows = provider.caseResults
        .map((result) => {
          const note = formatCaseNote(result);
          return `<tr>
  <td><code>${escapeHtml(result.id)}</code><br><span class="muted">${escapeHtml(result.description)}</span></td>
  <td><span class="status ${statusClassName(result.status)}">${formatStatus(result.status)}</span></td>
  <td>${escapeHtml(formatDuration(result.durationMs))}</td>
  <td>${escapeHtml(result.coveredParams.length > 0 ? result.coveredParams.join(', ') : '(none)')}</td>
  <td>${note ? `<pre class="note">${escapeHtml(note)}</pre>` : '<span class="muted">(none)</span>'}</td>
</tr>`;
        })
        .join('\n');

      return `<section class="provider">
<h2>${escapeHtml(provider.provider)}</h2>
<p class="meta">model=${escapeHtml(provider.model)} | baseUrl=${escapeHtml(provider.apiBaseUrl ?? '(default)')} | coverage=${escapeHtml(formatCoverage(provider.coveredParams.length, provider.allParams.length))} | passed=${provider.passed} failed=${provider.failed} skipped=${provider.skipped}</p>
<details>
<summary>covered params (${provider.coveredParams.length})</summary>
<pre class="params">${escapeHtml(provider.coveredParams.length > 0 ? provider.coveredParams.join(', ') : '(none)')}</pre>
</details>
<details>
<summary>untested params (${provider.untestedParams.length})</summary>
<pre class="params">${escapeHtml(provider.untestedParams.length > 0 ? provider.untestedParams.join(', ') : '(none)')}</pre>
</details>
<table>
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
</table>
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
