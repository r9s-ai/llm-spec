import type { TestCase } from './types';

export interface TestCaseDefinition {
  description: string;
  covers?: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
  apiType?: 'chatCompletions' | 'responses' | 'embeddings' | 'audio' | 'images';
  protocol?: string;
  modelScope?: string;
}

export interface DefineCasesDefaults {
  apiType?: 'chatCompletions' | 'responses' | 'embeddings' | 'audio' | 'images';
  protocol?: string;
  modelScope?: string;
}

export function defineCases(
  definitions: Record<string, TestCaseDefinition>,
  defaults: DefineCasesDefaults = {},
): TestCase[] {
  return Object.entries(definitions).map(([id, definition]) => {
    const inferredApiType =
      definition.apiType ??
      defaults.apiType ??
      (id.startsWith('responses_') ? 'responses' : 'chatCompletions');

    return {
      id,
      description: definition.description,
      covers: [...(definition.covers ?? [])],
      precondition: definition.precondition,
      run: definition.run,
      apiType: inferredApiType,
      protocol: definition.protocol ?? defaults.protocol,
      modelScope: definition.modelScope ?? defaults.modelScope,
    };
  });
}
