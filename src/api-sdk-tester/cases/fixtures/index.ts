import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export type MediaFixtureType = 'audio' | 'images' | 'video';

const fixturesDirFromModule = dirname(fileURLToPath(import.meta.url));

function resolveFixturesRoot(): string {
  const candidates = [
    join(process.cwd(), 'src', 'api-sdk-tester', 'cases', 'fixtures'),
    join(process.cwd(), 'dist', 'api-sdk-tester', 'cases', 'fixtures'),
    fixturesDirFromModule,
  ];

  const fixturesRoot = candidates.find((candidate) => existsSync(join(candidate, 'README.md')));
  if (!fixturesRoot) {
    throw new Error('Unable to locate api-sdk-tester fixtures directory');
  }

  return fixturesRoot;
}

function fixturePath(type: MediaFixtureType, fileName: string): string {
  return join(resolveFixturesRoot(), type, fileName);
}

export function readMediaFixtureBase64(type: MediaFixtureType, fileName: string): string {
  return readFileSync(fixturePath(type, fileName)).toString('base64');
}

export function readAudioFixtureBase64(fileName: string): string {
  return readMediaFixtureBase64('audio', fileName);
}

export function readImageFixtureBase64(fileName: string): string {
  return readMediaFixtureBase64('images', fileName);
}

export function readVideoFixtureBase64(fileName: string): string {
  return readMediaFixtureBase64('video', fileName);
}

export function createDataUri(mimeType: string, base64: string): string {
  return `data:${mimeType};base64,${base64}`;
}

export function readMediaFixtureDataUri(
  type: MediaFixtureType,
  fileName: string,
  mimeType: string,
): string {
  return createDataUri(mimeType, readMediaFixtureBase64(type, fileName));
}

export const fixtures = {
  audio: {
    response2second: {
      mimeType: 'audio/mp3',
      base64: () => readAudioFixtureBase64('response.mp3'),
      dataUri: () => readMediaFixtureDataUri('audio', 'response.mp3', 'audio/mp3'),
    },
  },
  images: {
    hamburger: {
      mimeType: 'image/jpeg',
      base64: () => readImageFixtureBase64('hamburger.jpg'),
      dataUri: () => readMediaFixtureDataUri('images', 'hamburger.jpg', 'image/jpeg'),
    },
  },
  video: {
    office: {
      mimeType: 'video/mp4',
      base64: () => readVideoFixtureBase64('office.mp4'),
      dataUri: () => readMediaFixtureDataUri('video', 'office.mp4', 'video/mp4'),
    },
  },
} as const;
