import { File } from 'node:buffer';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, resolve as resolvePath } from 'node:path';
import { fileURLToPath } from 'node:url';

const moduleDir = dirname(fileURLToPath(import.meta.url));

const FIXTURE_DIR_CANDIDATES = [
  resolvePath(process.cwd(), 'src/api-sdk-tester/fixtures'),
  resolvePath(process.cwd(), 'packages/llm-spec/src/api-sdk-tester/fixtures'),
  resolvePath(moduleDir, 'fixtures'),
  resolvePath(moduleDir, '../src/api-sdk-tester/fixtures'),
] as const;

export const IMAGE_INPUT_FIXTURES = [
  {
    format: 'png',
    mimeType: 'image/png',
    fileName: 'images/image-input.png',
  },
  {
    format: 'jpeg',
    mimeType: 'image/jpeg',
    fileName: 'images/image-input.jpeg',
  },
  {
    format: 'jpg',
    mimeType: 'image/jpeg',
    fileName: 'images/image-input.jpg',
  },
  {
    format: 'webp',
    mimeType: 'image/webp',
    fileName: 'images/image-input.webp',
  },
  {
    format: 'gif',
    mimeType: 'image/gif',
    fileName: 'images/image-input.gif',
  },
] as const;

export const MEDIA_INPUT_FIXTURES = {
  audio: {
    silent1s: {
      mimeType: 'audio/wav',
      fileName: 'audio/silent-1s.wav',
    },
  },
  image: {
    sampleJpeg: {
      mimeType: 'image/jpeg',
      fileName: 'images/image-input.jpg',
    },
  },
  video: {
    office: {
      mimeType: 'video/mp4',
      fileName: 'video/office.mp4',
    },
  },
} as const;

let resolvedFixtureDir: string | undefined;
const fixtureByteCache = new Map<string, Buffer>();

function normalizeFixtureName(fileName: string): string {
  const normalized = fileName.replaceAll('\\', '/');
  if (isAbsolute(normalized) || normalized.split('/').includes('..')) {
    throw new Error(`fixture path must be relative to the fixture directory: ${fileName}`);
  }
  return normalized;
}

function resolveFixtureDir(): string {
  if (resolvedFixtureDir) {
    return resolvedFixtureDir;
  }

  const fixtureDir = FIXTURE_DIR_CANDIDATES.find((candidate) => existsSync(candidate));
  if (!fixtureDir) {
    throw new Error(
      `could not find api-sdk-tester fixtures directory; tried ${FIXTURE_DIR_CANDIDATES.join(', ')}`,
    );
  }

  resolvedFixtureDir = fixtureDir;
  return fixtureDir;
}

export function getFixturePath(fileName: string): string {
  return resolvePath(resolveFixtureDir(), normalizeFixtureName(fileName));
}

export function readFixtureBytes(fileName: string): Buffer {
  const normalized = normalizeFixtureName(fileName);
  const cached = fixtureByteCache.get(normalized);
  if (cached) {
    return cached;
  }

  const bytes = readFileSync(getFixturePath(normalized));
  fixtureByteCache.set(normalized, bytes);
  return bytes;
}

export function readFixtureBase64(fileName: string): string {
  return readFixtureBytes(fileName).toString('base64');
}

export function createFixtureDataUri(mimeType: string, fileName: string): string {
  return `data:${mimeType};base64,${readFixtureBase64(fileName)}`;
}

export function createFixtureFile(fileName: string, name: string, mimeType: string): File {
  return new File([readFixtureBytes(fileName)], name, { type: mimeType });
}
