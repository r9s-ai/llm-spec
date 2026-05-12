import { AsyncLocalStorage } from 'node:async_hooks';

export interface ActiveTestContext {
  provider: string;
  testId: string;
}

const activeTestContext = new AsyncLocalStorage<ActiveTestContext>();

export function runWithActiveTestContext<T>(
  context: ActiveTestContext,
  action: () => T,
): T {
  return activeTestContext.run(context, action);
}

export function getActiveTestContext(): ActiveTestContext | undefined {
  return activeTestContext.getStore();
}
