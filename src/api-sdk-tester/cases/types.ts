export interface TestCase {
  id: string;
  description: string;
  covers: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
  apiType?: 'chatCompletions' | 'responses';
  protocol?: string;
  modelScope?: string;
}
