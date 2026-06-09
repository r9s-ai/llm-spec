import { pathToFileURL } from 'node:url';
import { basename, isAbsolute, resolve as resolvePath } from 'node:path';

import type {
  PluginBeforeCaseResult,
  PluginCaseCompleteContext,
  PluginCaseRequestContext,
  PluginRequestParams,
  PluginRequestPatch,
  PluginRunCompleteContext,
  TestLifecyclePlugin,
} from '../types';

interface RegisteredPluginCase {
  provider: string;
  testId: string;
  id: string;
  name: string;
  description: string;
}

type PluginModuleCandidate =
  | TestLifecyclePlugin
  | TestLifecyclePlugin[]
  | (() => TestLifecyclePlugin | TestLifecyclePlugin[] | Promise<TestLifecyclePlugin | TestLifecyclePlugin[]>);

const registeredPluginCases = new Map<string, RegisteredPluginCase>();
let activePluginManager: TestPluginManager | undefined;

function cloneRequest(request: PluginRequestParams): PluginRequestParams {
  return {
    ...request,
    headers: { ...request.headers },
  };
}

function normalizeBody(value: unknown): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return undefined;
  }
  if (typeof value === 'string') {
    return value;
  }
  if (value instanceof URLSearchParams) {
    return value.toString();
  }
  if (value instanceof ArrayBuffer) {
    return Buffer.from(value).toString('utf8');
  }
  if (ArrayBuffer.isView(value)) {
    return Buffer.from(value.buffer, value.byteOffset, value.byteLength).toString('utf8');
  }
  return JSON.stringify(value);
}

function hasPluginHook(value: unknown): value is TestLifecyclePlugin {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const candidate = value as Partial<TestLifecyclePlugin>;
  return (
    typeof candidate.beforeCase === 'function' ||
    typeof candidate.afterCase === 'function' ||
    typeof candidate.afterRun === 'function'
  );
}

function isPluginFactory(
  value: unknown,
): value is () => TestLifecyclePlugin | TestLifecyclePlugin[] | Promise<TestLifecyclePlugin | TestLifecyclePlugin[]> {
  return typeof value === 'function';
}

function requestPatchFromResult(result: PluginBeforeCaseResult): PluginRequestPatch | undefined {
  if (!result || typeof result !== 'object') {
    return undefined;
  }

  if ('request' in result) {
    return result.request;
  }

  return result as PluginRequestPatch;
}

function applyRequestPatch(
  request: PluginRequestParams,
  patch: PluginRequestPatch | undefined,
): PluginRequestParams {
  if (!patch) {
    return request;
  }

  const next: PluginRequestParams = {
    ...request,
    headers: { ...request.headers },
  };

  if (typeof patch.url === 'string' && patch.url.trim()) {
    next.url = patch.url;
  }
  if (typeof patch.method === 'string' && patch.method.trim()) {
    next.method = patch.method;
  }
  if (patch.headers) {
    for (const [key, value] of Object.entries(patch.headers)) {
      if (value === null || value === undefined) {
        delete next.headers[key];
        continue;
      }
      next.headers[key] = String(value);
    }
  }
  if ('body' in patch) {
    const body = normalizeBody(patch.body);
    if (body === undefined) {
      delete next.body;
    } else {
      next.body = body;
    }
  }

  return next;
}

function pluginDisplayName(plugin: TestLifecyclePlugin, fallbackPath: string): string {
  return plugin.name?.trim() || basename(fallbackPath);
}

async function resolvePluginCandidate(candidate: PluginModuleCandidate): Promise<TestLifecyclePlugin[]> {
  const resolved = isPluginFactory(candidate) ? await candidate() : candidate;
  return Array.isArray(resolved) ? resolved : [resolved];
}

async function loadPluginModule(pluginPath: string): Promise<TestLifecyclePlugin[]> {
  const absolutePath = isAbsolute(pluginPath) ? pluginPath : resolvePath(process.cwd(), pluginPath);
  const moduleUrl = pathToFileURL(absolutePath);
  const loadedModule = await import(moduleUrl.href) as Record<string, unknown>;
  const candidate =
    loadedModule.default ??
    loadedModule.plugin ??
    loadedModule.plugins ??
    (hasPluginHook(loadedModule) ? loadedModule : undefined);

  if (!candidate) {
    throw new Error(`Plugin ${pluginPath} must export a plugin object, plugin array, or plugin factory`);
  }

  const plugins = await resolvePluginCandidate(candidate as PluginModuleCandidate);
  for (const plugin of plugins) {
    if (!hasPluginHook(plugin)) {
      throw new Error(`Plugin ${pluginPath} must define beforeCase, afterCase, or afterRun`);
    }
  }
  return plugins;
}

export class TestPluginManager {
  readonly plugins: readonly TestLifecyclePlugin[];

  constructor(plugins: readonly TestLifecyclePlugin[]) {
    this.plugins = [...plugins];
  }

  get hasPlugins(): boolean {
    return this.plugins.length > 0;
  }

  async runBeforeCase(context: PluginCaseRequestContext): Promise<PluginRequestParams> {
    let request = cloneRequest(context.request);

    for (const plugin of this.plugins) {
      if (!plugin.beforeCase) {
        continue;
      }

      const hookContext: PluginCaseRequestContext = {
        ...context,
        request: cloneRequest(request),
      };
      const result = await plugin.beforeCase(hookContext);
      request = applyRequestPatch(request, hookContext.request);
      request = applyRequestPatch(request, requestPatchFromResult(result));
    }

    return request;
  }

  async runAfterCase(context: PluginCaseCompleteContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.afterCase?.(context);
    }
  }

  async runAfterRun(context: PluginRunCompleteContext): Promise<void> {
    for (const plugin of this.plugins) {
      await plugin.afterRun?.(context);
    }
  }
}

export async function createTestPluginManager(
  pluginPaths: readonly string[],
  inlinePlugins: readonly TestLifecyclePlugin[] = [],
): Promise<TestPluginManager> {
  const plugins: TestLifecyclePlugin[] = [...inlinePlugins];
  for (const pluginPath of pluginPaths) {
    const loadedPlugins = await loadPluginModule(pluginPath);
    for (const plugin of loadedPlugins) {
      plugins.push(plugin);
      console.log(`[plugins] loaded ${pluginDisplayName(plugin, pluginPath)} from ${pluginPath}`);
    }
  }
  return new TestPluginManager(plugins);
}

export async function runWithTestPluginManager<T>(
  pluginManager: TestPluginManager,
  action: () => Promise<T>,
): Promise<T> {
  const previousManager = activePluginManager;
  activePluginManager = pluginManager;
  try {
    return await action();
  } finally {
    activePluginManager = previousManager;
  }
}

export function getActiveTestPluginManager(): TestPluginManager | undefined {
  return activePluginManager;
}

export function registerTestPluginCase(context: RegisteredPluginCase): void {
  registeredPluginCases.set(context.testId, context);
}

export function unregisterTestPluginCase(testId: string): void {
  registeredPluginCases.delete(testId);
}

export function getRegisteredTestPluginCase(testId: string | undefined): RegisteredPluginCase | undefined {
  return testId ? registeredPluginCases.get(testId) : undefined;
}

export async function runTestPluginBeforeCase(
  context: PluginCaseRequestContext,
): Promise<PluginRequestParams> {
  const manager = getActiveTestPluginManager();
  if (!manager?.hasPlugins) {
    return context.request;
  }
  return manager.runBeforeCase(context);
}
