import { cp, mkdir, rm, stat } from 'node:fs/promises';
import { dirname, resolve as resolvePath } from 'node:path';
import { fileURLToPath } from 'node:url';

async function ensureDirectory(path: string): Promise<void> {
  try {
    if (!(await stat(path)).isDirectory()) {
      throw new Error(`${path} is not a directory`);
    }
  } catch (error) {
    throw new Error(`Reporter build output not found at ${path}. Run reporter build first.`, {
      cause: error,
    });
  }
}

const scriptDir = dirname(fileURLToPath(import.meta.url));
const defaultSource = resolvePath(scriptDir, '../../../reporter/dist');
const defaultDestination = resolvePath(scriptDir, '../public');
const source = resolvePath(process.env.REPORTER_DIST_DIR ?? defaultSource);
const destination = resolvePath(process.env.LLM_SPEC_STATIC_DIR ?? defaultDestination);

await ensureDirectory(source);
await rm(destination, { recursive: true, force: true });
await mkdir(destination, { recursive: true });
await cp(source, destination, { recursive: true });

console.log(`Copied reporter build from ${source} to ${destination}`);
