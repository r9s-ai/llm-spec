import type { TestCase } from '../shared';

export interface TestCaseDefinition {
  description: string;
  covers?: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
}

export function defineCases(definitions: Record<string, TestCaseDefinition>): TestCase[] {
  return Object.entries(definitions).map(([id, definition]) => ({
    id,
    description: definition.description,
    covers: [...(definition.covers ?? [])],
    precondition: definition.precondition,
    run: definition.run,
  }));
}
