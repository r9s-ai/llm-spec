import type OpenAI from 'openai';

import type { OpenAIProviderConfig } from '../../environment';
import { createFixtureFile } from '../../fixtures';
import { defineCases } from '../define-cases';
import { truncate } from '../runtime';
import type { TestCase } from '../types';
import { isOpenAICompatibilityGateway } from '../openai/shared';

export const OPENAI_EXTENDED_PARAMS = [
  'background',
  'chunking_strategy',
  'dimensions',
  'encoding_format',
  'file',
  'image',
  'include',
  'input',
  'input_fidelity',
  'instructions',
  'known_speaker_names',
  'language',
  'mask',
  'moderation',
  'model',
  'n',
  'output_compression',
  'output_format',
  'prompt',
  'quality',
  'response_format',
  'size',
  'speed',
  'stream',
  'stream_format',
  'style',
  'temperature',
  'timestamp_granularities',
  'user',
  'voice',
] as const;

export interface OpenAIExtendedCaseContext {
  client: OpenAI;
  config: OpenAIProviderConfig;
}

function createPngFile(name: string) {
  return createFixtureFile(`images/${name}`, name, 'image/png');
}

function createSilentWavFile(name: string) {
  return createFixtureFile(`audio/${name}`, name, 'audio/wav');
}

function summarizeObject(value: unknown): string {
  if (typeof value === 'string') {
    return `text="${truncate(value)}"`;
  }

  const obj = value as {
    data?: unknown[];
    text?: string;
    duration?: number;
    output_text?: string;
  };
  const dataCount = Array.isArray(obj.data) ? obj.data.length : undefined;
  const text = typeof obj.text === 'string'
    ? obj.text
    : typeof obj.output_text === 'string'
      ? obj.output_text
      : '';
  const parts: string[] = [];
  if (dataCount !== undefined) {
    parts.push(`data=${dataCount}`);
  }
  if (typeof obj.duration === 'number') {
    parts.push(`duration=${obj.duration}`);
  }
  if (text) {
    parts.push(`text="${truncate(text)}"`);
  }
  return parts.length > 0 ? parts.join(', ') : `json="${truncate(JSON.stringify(value))}"`;
}

async function summarizeBinaryResponse(response: Response): Promise<string> {
  const bytes = await response.arrayBuffer();
  return `bytes=${bytes.byteLength}, content_type=${response.headers.get('content-type') ?? 'unknown'}`;
}

function isAsyncIterable(value: unknown): value is AsyncIterable<unknown> {
  return typeof (value as { [Symbol.asyncIterator]?: unknown })?.[Symbol.asyncIterator] === 'function';
}

async function summarizeStream(stream: AsyncIterable<unknown>): Promise<string> {
  let events = 0;
  for await (const _event of stream) {
    events += 1;
  }
  return `events=${events}`;
}

export function buildOpenAIExtendedCases({ client, config }: OpenAIExtendedCaseContext): TestCase[] {
  const embeddingModel = config.embeddingModel ?? 'text-embedding-3-small';
  const speechModel = config.speechModel ?? 'gpt-4o-mini-tts';
  const transcriptionModel = config.transcriptionModel ?? 'gpt-4o-mini-transcribe';
  const translationModel = config.translationModel ?? 'whisper-1';
  const imageModel = config.imageModel ?? 'gpt-image-1.5';
  const imageEditModel = config.imageEditModel ?? 'gpt-image-1.5';
  const dalleModel = config.dalleModel ?? 'dall-e-3';

  const skipCompatibilityGateway = () =>
    isOpenAICompatibilityGateway(config.apiBaseUrl)
      ? `extended OpenAI API surfaces are not reliably supported on compatibility gateways: ${config.apiBaseUrl ?? '(unknown)'}`
      : undefined;

  return defineCases(
    {
      'embeddings_core': {
        description: 'embeddings baseline + dimensions/encoding/input/user variants',
        covers: ['model', 'input', 'dimensions', 'encoding_format', 'user'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const results = await Promise.all([
            client.embeddings.create({
              model: embeddingModel,
              input: 'hello',
            }),
            client.embeddings.create({
              model: embeddingModel,
              input: 'hello',
              dimensions: 128,
            }),
            client.embeddings.create({
              model: embeddingModel,
              input: 'hello',
              encoding_format: 'float',
            }),
            client.embeddings.create({
              model: embeddingModel,
              input: ['hello', 'world'],
            }),
            client.embeddings.create({
              model: embeddingModel,
              input: [[15339]],
              user: 'llm-spec-user',
            }),
          ]);
          return results.map((result) => summarizeObject(result)).join(' | ');
        },
      },
      'audio_speech_core': {
        description: 'audio speech voice/format/speed/instructions/stream_format variants',
        covers: ['model', 'input', 'voice', 'response_format', 'speed', 'instructions', 'stream_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const audioResponse = await client.audio.speech.create({
            model: speechModel,
            input: 'Hello from llm-spec.',
            voice: 'alloy',
            response_format: 'mp3',
            speed: 1.1,
            instructions: 'Speak clearly and briefly.',
            stream_format: 'audio',
          });
          const sseResponse = await client.audio.speech.create({
            model: speechModel,
            input: 'Hello from llm-spec.',
            voice: 'alloy',
            response_format: 'mp3',
            stream_format: 'sse',
          });
          return [
            `audio:${await summarizeBinaryResponse(audioResponse)}`,
            `sse:${await summarizeBinaryResponse(sseResponse)}`,
          ].join(' | ');
        },
      },
      'audio_transcriptions_core': {
        description: 'audio transcriptions file/prompt/language/format/timestamps/chunking/include/stream',
        covers: [
          'file',
          'model',
          'language',
          'prompt',
          'response_format',
          'temperature',
          'timestamp_granularities',
          'chunking_strategy',
          'include',
          'known_speaker_names',
          'stream',
        ],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const jsonResponse = await client.audio.transcriptions.create({
            file: createSilentWavFile('transcription-json.wav'),
            model: transcriptionModel,
            language: 'en',
            prompt: 'The audio may be silent.',
            response_format: 'json',
            temperature: 0,
          });
          const verboseResponse = await client.audio.transcriptions.create({
            file: createSilentWavFile('transcription-verbose.wav'),
            model: transcriptionModel,
            response_format: 'verbose_json',
            timestamp_granularities: ['segment'],
          });
          const advancedResponse = await client.audio.transcriptions.create({
            file: createSilentWavFile('transcription-advanced.wav'),
            model: transcriptionModel,
            chunking_strategy: 'auto',
            include: ['logprobs'],
            known_speaker_names: ['speaker-a'],
            response_format: 'json',
          } as never);
          const stream = await client.audio.transcriptions.create({
            file: createSilentWavFile('transcription-stream.wav'),
            model: transcriptionModel,
            response_format: 'json',
            stream: true,
          });

          return [
            `json:${summarizeObject(jsonResponse)}`,
            `verbose:${summarizeObject(verboseResponse)}`,
            `advanced:${summarizeObject(advancedResponse)}`,
            `stream:${isAsyncIterable(stream) ? await summarizeStream(stream) : summarizeObject(stream)}`,
          ].join(' | ');
        },
      },
      'audio_translations_core': {
        description: 'audio translations prompt/format/temperature variants',
        covers: ['file', 'model', 'prompt', 'response_format', 'temperature'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const results = await Promise.all([
            client.audio.translations.create({
              file: createSilentWavFile('translation-json.wav'),
              model: translationModel,
              prompt: 'Translate to English.',
              response_format: 'json',
              temperature: 0,
            }),
            client.audio.translations.create({
              file: createSilentWavFile('translation-verbose.wav'),
              model: translationModel,
              response_format: 'verbose_json',
            }),
            client.audio.translations.create({
              file: createSilentWavFile('translation-text.wav'),
              model: translationModel,
              response_format: 'text',
            }),
          ]);
          return results.map((result) => summarizeObject(result)).join(' | ');
        },
      },
      'images_generations_core': {
        description: 'images generations GPT image parameters',
        covers: [
          'model',
          'prompt',
          'background',
          'moderation',
          'n',
          'output_compression',
          'output_format',
          'quality',
          'size',
          'user',
        ],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.generate({
            model: imageModel,
            prompt: 'A tiny red square icon on a plain background.',
            background: 'opaque',
            moderation: 'low',
            n: 1,
            output_compression: 80,
            output_format: 'png',
            quality: 'low',
            size: '1024x1024',
            user: 'llm-spec-user',
          });
          return summarizeObject(response);
        },
      },
      'images_generations_dalle_style': {
        description: 'images generations response_format/style variants',
        covers: ['model', 'prompt', 'response_format', 'style', 'size', 'quality'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.generate({
            model: dalleModel,
            prompt: 'A tiny red square icon on a plain background.',
            response_format: 'b64_json',
            style: 'natural',
            quality: 'standard',
            size: '1024x1024',
          });
          return summarizeObject(response);
        },
      },
      'images_generations_stream': {
        description: 'images generations streaming',
        covers: ['model', 'prompt', 'stream'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.generate({
            model: imageModel,
            prompt: 'A tiny blue square icon on a plain background.',
            stream: true,
            partial_images: 0,
            size: '1024x1024',
          });
          return isAsyncIterable(response) ? summarizeStream(response) : summarizeObject(response);
        },
      },
      'images_edits_core': {
        description: 'images edits image/mask/background/fidelity/output variants',
        covers: [
          'image',
          'prompt',
          'background',
          'input_fidelity',
          'mask',
          'model',
          'n',
          'output_compression',
          'output_format',
          'quality',
          'size',
          'user',
        ],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.edit({
            image: createPngFile('edit-base.png'),
            mask: createPngFile('edit-mask.png'),
            model: imageEditModel,
            prompt: 'Turn the square into a simple green square icon.',
            background: 'transparent',
            input_fidelity: 'low',
            n: 1,
            output_compression: 80,
            output_format: 'png',
            quality: 'low',
            size: '1024x1024',
            user: 'llm-spec-user',
          });
          return summarizeObject(response);
        },
      },
      'images_edits_stream': {
        description: 'images edits streaming',
        covers: ['image', 'prompt', 'model', 'stream'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.edit({
            image: createPngFile('edit-stream-base.png'),
            model: imageEditModel,
            prompt: 'Turn the square into a simple yellow square icon.',
            stream: true,
            partial_images: 0,
            size: '1024x1024',
          });
          return isAsyncIterable(response) ? summarizeStream(response) : summarizeObject(response);
        },
      },
    },
    {
      apiType: 'embeddings',
      protocol: 'openai.extended',
      modelScope: 'extended',
    },
  ).map((testCase) => {
    if (testCase.id.startsWith('audio_')) {
      return {
        ...testCase,
        apiType: 'audio' as const,
        protocol: testCase.id.startsWith('audio_speech')
          ? 'openai.audio.speech'
          : testCase.id.startsWith('audio_transcriptions')
            ? 'openai.audio.transcriptions'
            : 'openai.audio.translations',
      };
    }
    if (testCase.id.startsWith('images_')) {
      return {
        ...testCase,
        apiType: 'images' as const,
        protocol: testCase.id.startsWith('images_edits')
          ? 'openai.images.edits'
          : 'openai.images.generations',
      };
    }
    return {
      ...testCase,
      protocol: 'openai.embeddings',
    };
  });
}
