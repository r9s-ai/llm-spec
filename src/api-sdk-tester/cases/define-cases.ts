import type { TestCase } from '../shared';

export interface TestCaseDefinition {
  description: string;
  covers?: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
  apiType?: 'chatCompletions' | 'responses';
}

export function defineCases(definitions: Record<string, TestCaseDefinition>): TestCase[] {
  return Object.entries(definitions).map(([id, definition]) => {
    // 自动推断 apiType:如果 ID 以 responses_ 开头,则为 responses,否则为 chatCompletions
    const inferredApiType = definition.apiType ?? (id.startsWith('responses_') ? 'responses' : 'chatCompletions');

    return {
      id,
      description: definition.description,
      covers: [...(definition.covers ?? [])],
      precondition: definition.precondition,
      run: definition.run,
      apiType: inferredApiType,
    };
  });
}
