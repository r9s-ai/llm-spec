#!/usr/bin/env node
/// <reference types="node" />

import * as fs from 'fs';
import * as path from 'path';
import { spawnSync } from 'child_process';

/**
 * API文档配置
 */
interface DocConfig {
  name: string;
  url: string;
  outputFilename: string;
  headers?: Record<string, string>;
}

interface EnvValue {
  name: string;
  value: string;
}

interface ProxyConfig {
  source: string;
  url: string;
  noProxy?: EnvValue;
}

/**
 * 要拉取的文档列表
 */
const docs: DocConfig[] = [
  {
    name: 'Anthropic Messages Create',
    url: 'https://platform.claude.com/docs/en/api/typescript/messages/create.md',
    outputFilename: 'anthropic-messages-create.md',
  },
  {
    name: 'OpenAI Chat Completions Create',
    url: 'https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/index.md',
    outputFilename: 'openai-chat-completions-create.md',
  },
  {
    name: 'OpenAI Responses Create',
    url: 'https://developers.openai.com/api/reference/resources/responses/methods/create/index.md',
    outputFilename: 'openai-responses-create.md',
  },
];

/**
 * 输出目录
 */
function resolveOutputDir(): string {
  const configuredDir = process.env.LLM_SPEC_DOCS_DIR?.trim();
  if (configuredDir) {
    return path.resolve(process.cwd(), configuredDir);
  }

  let currentDir = process.cwd();
  while (true) {
    if (
      fs.existsSync(path.join(currentDir, '.git')) ||
      fs.existsSync(path.join(currentDir, 'docs'))
    ) {
      return path.join(currentDir, 'docs', 'api-reference');
    }

    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      return path.resolve(process.cwd(), 'docs', 'api-reference');
    }
    currentDir = parentDir;
  }
}

const OUTPUT_DIR = resolveOutputDir();

function readEnv(names: readonly string[]): EnvValue | undefined {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) {
      return { name, value };
    }
  }

  return undefined;
}

function getDefaultPort(protocol: string): string {
  return protocol === 'https:' ? '443' : '80';
}

function splitNoProxyEntry(entry: string): { host: string; port?: string } {
  let host = entry.trim().toLowerCase();
  let port: string | undefined;

  if (host.startsWith('[')) {
    const closingBracket = host.indexOf(']');
    if (closingBracket >= 0) {
      const afterBracket = host.slice(closingBracket + 1);
      if (afterBracket.startsWith(':')) {
        port = afterBracket.slice(1);
      }
      host = host.slice(1, closingBracket);
    }
  } else {
    const colonIndex = host.lastIndexOf(':');
    if (colonIndex > -1 && host.indexOf(':') === colonIndex) {
      port = host.slice(colonIndex + 1);
      host = host.slice(0, colonIndex);
    }
  }

  return { host, port };
}

function noProxyMatches(url: URL, noProxy: string): boolean {
  const hostname = url.hostname.toLowerCase();
  const port = url.port || getDefaultPort(url.protocol);

  return noProxy.split(',').some((entry) => {
    const trimmedEntry = entry.trim();
    if (!trimmedEntry) {
      return false;
    }

    if (trimmedEntry === '*') {
      return true;
    }

    let { host, port: noProxyPort } = splitNoProxyEntry(trimmedEntry);
    if (noProxyPort && noProxyPort !== port) {
      return false;
    }

    if (host.startsWith('*.')) {
      host = host.slice(2);
      return hostname.endsWith(`.${host}`);
    }

    if (host.startsWith('.')) {
      host = host.slice(1);
    }

    return hostname === host || hostname.endsWith(`.${host}`);
  });
}

function resolveProxyConfig(url: string): ProxyConfig | undefined {
  const targetUrl = new URL(url);
  const noProxy = readEnv(['NO_PROXY', 'no_proxy']);
  if (noProxy && noProxyMatches(targetUrl, noProxy.value)) {
    return undefined;
  }

  const proxyEnvNames =
    targetUrl.protocol === 'http:'
      ? ['HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy']
      : ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'];
  const proxy = readEnv(proxyEnvNames);

  if (!proxy) {
    return undefined;
  }

  return {
    source: proxy.name,
    url: proxy.value,
    noProxy,
  };
}

function formatProxyForLog(proxyUrl: string): string {
  try {
    const url = new URL(proxyUrl);
    if (url.username || url.password) {
      url.username = '***';
      url.password = '***';
    }
    return url.toString();
  } catch {
    return proxyUrl.replace(/\/\/[^/@]+@/, '//***@');
  }
}

/**
 * 确保目录存在
 */
function ensureDirectoryExists(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
    console.log(`✓ 创建目录: ${dir}`);
  }
}

/**
 * 拉取单个文档
 */
async function fetchDoc(config: DocConfig): Promise<void> {
  const proxy = resolveProxyConfig(config.url);

  console.log(`\n📄 正在拉取: ${config.name}`);
  console.log(`   URL: ${config.url}`);
  if (proxy) {
    console.log(`   🔄 使用代理(${proxy.source}): ${formatProxyForLog(proxy.url)}`);
  }

  try {
    let content: string;

    if (proxy) {
      // 使用代理时改为调用curl，确保与手动验证行为一致
      const args = [
        '--silent',
        '--show-error',
        '--location',
        '--fail',
        '--proxy',
        proxy.url,
      ];

      if (proxy.noProxy) {
        args.push('--noproxy', proxy.noProxy.value);
      }

      if (config.headers) {
        for (const [key, value] of Object.entries(config.headers)) {
          args.push('-H', `${key}: ${value}`);
        }
      }

      args.push(config.url);

      const result = spawnSync('curl', args, {
        encoding: 'utf-8',
        maxBuffer: 20 * 1024 * 1024,
      });

      if (result.error) {
        throw new Error(`curl执行失败: ${result.error.message}`);
      }

      if (result.status !== 0) {
        throw new Error(
          `curl请求失败 (exit ${result.status}): ${result.stderr || '未知错误'}`
        );
      }

      content = result.stdout;
    } else {
      // 不使用代理：使用全局fetch
      const response = await fetch(config.url, {
        headers: config.headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      content = await response.text();
    }

    const outputPath = path.join(OUTPUT_DIR, config.outputFilename);
    fs.writeFileSync(outputPath, content, 'utf-8');

    console.log(`   ✓ 成功保存到: ${outputPath}`);
    console.log(`   ✓ 文件大小: ${(content.length / 1024).toFixed(2)} KB`);
  } catch (error) {
    console.error(`   ✗ 拉取失败: ${error instanceof Error ? error.message : String(error)}`);
    throw error;
  }
}

/**
 * 主函数
 */
async function main(): Promise<void> {
  console.log('🚀 开始拉取API文档...\n');

  // 确保输出目录存在
  ensureDirectoryExists(OUTPUT_DIR);

  // 拉取所有文档
  const results = await Promise.allSettled(docs.map(fetchDoc));

  // 统计结果
  const succeeded = results.filter(r => r.status === 'fulfilled').length;
  const failed = results.filter(r => r.status === 'rejected').length;

  console.log('\n' + '='.repeat(60));
  console.log('📊 拉取完成!');
  console.log(`   ✓ 成功: ${succeeded}/${docs.length}`);
  if (failed > 0) {
    console.log(`   ✗ 失败: ${failed}/${docs.length}`);
  }
  console.log(`   📁 输出目录: ${OUTPUT_DIR}`);
  console.log('='.repeat(60) + '\n');

  // 如果有失败的，以错误码退出
  if (failed > 0) {
    process.exit(1);
  }
}

// 运行主函数
main().catch((error) => {
  console.error('\n❌ 脚本执行失败:', error);
  process.exit(1);
});
