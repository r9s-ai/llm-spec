let currentProvider = 'unknown';

export function setCurrentProvider(provider: string): void {
  currentProvider = provider;
}

export function getCurrentProvider(): string {
  return currentProvider;
}
