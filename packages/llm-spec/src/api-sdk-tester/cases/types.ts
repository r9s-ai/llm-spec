export interface TestCase {
  id: string;
  description: string;
  covers: readonly string[];
  precondition?: () => string | undefined;
  run: () => Promise<string | undefined>;
  apiType?: 'chatCompletions' | 'responses' | 'embeddings' | 'audio' | 'images';
  protocol?: string;
  modelScope?: string;
}
