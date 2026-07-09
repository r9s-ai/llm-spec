import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import type { UsageCaptureArtifact } from './type';

export const DEFAULT_USAGE_ARTIFACT_PATH = 'src/billing-audit/data/usage.json';

export function getUnixTimeSeconds(): string {
  return String(Math.floor(Date.now() / 1000));
}

export function writeUsageArtifact(
  artifact: UsageCaptureArtifact,
  path = DEFAULT_USAGE_ARTIFACT_PATH,
): string {
  const artifactPath = resolvePath(process.cwd(), path);
  mkdirSync(dirname(artifactPath), { recursive: true });
  writeFileSync(artifactPath, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8');
  return artifactPath;
}
