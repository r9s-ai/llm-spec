import { Buffer } from 'node:buffer';
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
  'known_speaker_references',
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

function createSilentWavDataUri(seconds: number): string {
  const sampleRate = 16_000;
  const channels = 1;
  const bytesPerSample = 2;
  const dataSize = sampleRate * seconds * channels * bytesPerSample;
  const bytes = Buffer.alloc(44 + dataSize);

  bytes.write('RIFF', 0);
  bytes.writeUInt32LE(36 + dataSize, 4);
  bytes.write('WAVE', 8);
  bytes.write('fmt ', 12);
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20);
  bytes.writeUInt16LE(channels, 22);
  bytes.writeUInt32LE(sampleRate, 24);
  bytes.writeUInt32LE(sampleRate * channels * bytesPerSample, 28);
  bytes.writeUInt16LE(channels * bytesPerSample, 32);
  bytes.writeUInt16LE(8 * bytesPerSample, 34);
  bytes.write('data', 36);
  bytes.writeUInt32LE(dataSize, 40);

  return `data:audio/wav;base64,${bytes.toString('base64')}`;
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
  const dalle2Model = 'dall-e-2';

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
              dimensions: 512,
            }),
            client.embeddings.create({
              model: embeddingModel,
              input: 'hello',
              encoding_format: 'base64',
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
      'audio_speech_voice_variants': {
        description: 'audio speech all documented voice variants',
        covers: ['voice'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const voices = [
            'alloy',
            'echo',
            'fable',
            'onyx',
            'nova',
            'shimmer',
            'ash',
            'ballad',
            'coral',
            'sage',
            'verse',
            'marin',
            'cedar',
          ] as const;
          const results: string[] = [];

          for (const voice of voices) {
            const response = await client.audio.speech.create({
              model: speechModel,
              input: 'Voice variant smoke test.',
              voice: voice as never,
              response_format: 'mp3',
            });
            results.push(`${voice}:${await summarizeBinaryResponse(response)}`);
          }

          return results.join(' | ');
        },
      },
      'audio_speech_response_format_variants': {
        description: 'audio speech response_format mp3/opus/aac/flac/wav/pcm variants',
        covers: ['response_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const formats = ['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'] as const;
          const results: string[] = [];

          for (const format of formats) {
            const response = await client.audio.speech.create({
              model: speechModel,
              input: 'Response format variant smoke test.',
              voice: 'alloy',
              response_format: format,
            });
            results.push(`${format}:${await summarizeBinaryResponse(response)}`);
          }

          return results.join(' | ');
        },
      },
      'audio_speech_speed_variants': {
        description: 'audio speech speed 0.25/0.5/1/1.5/2/4 variants',
        covers: ['speed'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const speeds = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0] as const;
          const results: string[] = [];

          for (const speed of speeds) {
            const response = await client.audio.speech.create({
              model: speechModel,
              input: 'Speed variant smoke test.',
              voice: 'alloy',
              response_format: 'mp3',
              speed,
            });
            results.push(`${speed}:${await summarizeBinaryResponse(response)}`);
          }

          return results.join(' | ');
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
          'known_speaker_references',
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
            timestamp_granularities: ['word', 'segment'],
          });
          const advancedResponse = await client.audio.transcriptions.create({
            file: createSilentWavFile('transcription-advanced.wav'),
            model: transcriptionModel,
            chunking_strategy: 'auto',
            include: ['logprobs'],
            known_speaker_names: ['speaker-a', 'speaker-b'],
            known_speaker_references: [
              createSilentWavDataUri(2),
              createSilentWavDataUri(2),
            ],
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
      'audio_transcriptions_response_format_variants': {
        description: 'audio transcriptions response_format json/text/verbose_json/srt/vtt variants',
        covers: ['response_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const formats = ['json', 'text', 'verbose_json', 'srt', 'vtt'] as const;
          const results: string[] = [];

          for (const format of formats) {
            const response = await client.audio.transcriptions.create({
              file: createSilentWavFile('silent-1s.wav'),
              model: transcriptionModel,
              response_format: format,
            } as never);
            results.push(`${format}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
        },
      },
      'audio_transcriptions_chunking_strategy_variants': {
        description: 'audio transcriptions chunking_strategy auto/server_vad variants',
        covers: ['chunking_strategy'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            { name: 'auto', value: 'auto' },
            { name: 'server_vad', value: { type: 'server_vad' } },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.audio.transcriptions.create({
              file: createSilentWavFile('silent-1s.wav'),
              model: transcriptionModel,
              chunking_strategy: variant.value,
              response_format: 'json',
            } as never);
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
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
      'audio_translations_response_format_variants': {
        description: 'audio translations response_format json/text/srt/verbose_json/vtt variants',
        covers: ['response_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const formats = ['json', 'text', 'srt', 'verbose_json', 'vtt'] as const;
          const results: string[] = [];

          for (const format of formats) {
            const response = await client.audio.translations.create({
              file: createSilentWavFile('silent-1s.wav'),
              model: translationModel,
              response_format: format,
            } as never);
            results.push(`${format}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
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
            output_format: 'webp',
            quality: 'low',
            size: '1024x1024',
            user: 'llm-spec-user',
          });
          return summarizeObject(response);
        },
      },
      'images_generations_dalle_style': {
        description: 'images generations DALL-E response_format/style baseline',
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
      'images_generations_dalle_size_variants': {
        description: 'images generations DALL-E size variants',
        covers: ['model', 'prompt', 'size'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            { name: 'dalle3_1024x1024', model: dalleModel, size: '1024x1024' },
            { name: 'dalle3_1792x1024', model: dalleModel, size: '1792x1024' },
            { name: 'dalle3_1024x1792', model: dalleModel, size: '1024x1792' },
            { name: 'dalle2_512x512', model: dalle2Model, size: '512x512' },
            { name: 'dalle2_256x256', model: dalle2Model, size: '256x256' },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.images.generate({
              model: variant.model,
              prompt: 'A tiny geometric icon on a plain background.',
              n: 1,
              size: variant.size,
            });
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
        },
      },
      'images_generations_dalle_quality_response_style_variants': {
        description: 'images generations DALL-E quality/response_format/style variants',
        covers: ['model', 'prompt', 'quality', 'response_format', 'style'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            { name: 'quality_hd', params: { quality: 'hd' } },
            { name: 'quality_standard', params: { quality: 'standard' } },
            { name: 'response_url', params: { response_format: 'url' } },
            { name: 'response_b64_json', params: { response_format: 'b64_json' } },
            { name: 'style_vivid', params: { style: 'vivid' } },
            { name: 'style_natural', params: { style: 'natural' } },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.images.generate({
              model: dalleModel,
              prompt: 'A tiny geometric icon on a plain background.',
              n: 1,
              size: '1024x1024',
              ...variant.params,
            });
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
        },
      },
      'images_generations_gpt_output_format_variants': {
        description: 'images generations GPT image output_format variants',
        covers: ['model', 'prompt', 'output_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const outputFormats = ['png', 'jpeg', 'webp'] as const;
          const results: string[] = [];

          for (const outputFormat of outputFormats) {
            const response = await client.images.generate({
              model: imageModel,
              prompt: 'A minimal rocket icon on a plain background.',
              output_format: outputFormat,
              size: '1024x1024',
            });
            results.push(`${outputFormat}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
        },
      },
      'images_generations_gpt_output_compression_variants': {
        description: 'images generations GPT image output_compression variants',
        covers: ['model', 'prompt', 'output_compression', 'output_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            { name: 'webp_80', outputFormat: 'webp' },
            { name: 'jpeg_80', outputFormat: 'jpeg' },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.images.generate({
              model: imageModel,
              prompt: 'A minimal landscape icon on a plain background.',
              output_format: variant.outputFormat,
              output_compression: 80,
              size: '1024x1024',
            });
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
        },
      },
      'images_generations_gpt_background_moderation_quality_size_variants': {
        description: 'images generations GPT image background/moderation/quality/size variants',
        covers: ['model', 'prompt', 'background', 'moderation', 'quality', 'size'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            {
              name: 'background_transparent',
              params: { background: 'transparent', output_format: 'png' },
            },
            { name: 'background_opaque', params: { background: 'opaque' } },
            { name: 'background_auto', params: { background: 'auto' } },
            { name: 'moderation_low', params: { moderation: 'low' } },
            { name: 'moderation_auto', params: { moderation: 'auto' } },
            { name: 'quality_high', params: { quality: 'high' } },
            { name: 'quality_medium', params: { quality: 'medium' } },
            { name: 'quality_low', params: { quality: 'low' } },
            { name: 'quality_auto', params: { quality: 'auto' } },
            { name: 'size_1024x1024', params: { size: '1024x1024' } },
            { name: 'size_1536x1024', params: { size: '1536x1024' } },
            { name: 'size_1024x1536', params: { size: '1024x1536' } },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.images.generate({
              model: imageModel,
              prompt: 'A minimal product icon on a plain background.',
              size: '1024x1024',
              ...variant.params,
            });
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
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
            output_format: 'webp',
            quality: 'low',
            size: '1024x1024',
            user: 'llm-spec-user',
          });
          return summarizeObject(response);
        },
      },
      'images_edits_dalle_response_format_url': {
        description: 'images edits DALL-E response_format=url variant',
        covers: ['image', 'prompt', 'model', 'response_format'],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const response = await client.images.edit({
            image: createPngFile('edit-base.png'),
            model: dalle2Model,
            prompt: 'Add a small white border around the square.',
            response_format: 'url',
          });
          return summarizeObject(response);
        },
      },
      'images_edits_gpt_variant_params': {
        description: 'images edits GPT image n/size/input_fidelity/output variants',
        covers: [
          'image',
          'prompt',
          'model',
          'n',
          'size',
          'input_fidelity',
          'output_format',
          'output_compression',
        ],
        precondition: skipCompatibilityGateway,
        run: async () => {
          const variants = [
            { name: 'n_2', params: { n: 2 } },
            { name: 'size_1536x1024', params: { size: '1536x1024' } },
            { name: 'input_fidelity_high', params: { input_fidelity: 'high' } },
            { name: 'output_format_webp', params: { output_format: 'webp' } },
            {
              name: 'output_compression_webp_80',
              params: { output_format: 'webp', output_compression: 80 },
            },
          ] as const;
          const results: string[] = [];

          for (const variant of variants) {
            const response = await client.images.edit({
              image: createPngFile('edit-base.png'),
              model: imageEditModel,
              prompt: 'Turn the square into a simple blue square icon.',
              size: '1024x1024',
              ...variant.params,
            });
            results.push(`${variant.name}:${summarizeObject(response)}`);
          }

          return results.join(' | ');
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
