# OpenAI API Routes

本文档列出 OpenAI provider 支持的所有 API 端点及其验证方法。

## 支持的端点

| 端点 | 方法 | 验证方法 | 需要文件 |
|------|------|----------|----------|
| `/v1/chat/completions` | POST | `validate_chat_completion()` | - |
| `/v1/responses` | POST | `validate_responses()` | - |
| `/v1/embeddings` | POST | `validate_embeddings()` | - |
| `/v1/audio/speech` | POST | `validate_speech()` | - |
| `/v1/audio/transcriptions` | POST | `validate_transcription()` | 音频文件 |
| `/v1/audio/translations` | POST | `validate_translation()` | 音频文件 |
| `/v1/images/generations` | POST | `validate_image_generation()` | - |
| `/v1/images/edits` | POST | `validate_image_edit()` | 图片文件 |
| `/v1/images/variations` | POST | `validate_image_variation()` | 图片文件 |

## 使用示例

### 基础用法

```python
from llm_spec.providers.openai import OpenAIClient

client = OpenAIClient(api_key="your-api-key")

# 验证某个端点
report = client.validate_chat_completion()
report.print()  # 终端彩色输出
```

### Chat Completions

```python
report = client.validate_chat_completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
report.print()
```

### Responses API

```python
report = client.validate_responses(
    model="gpt-4o-mini",
    input_text="Hello",
)
report.print()
```

### Embeddings

```python
# 单个文本
report = client.validate_embeddings(
    model="text-embedding-3-small",
    input_text="Hello, world!",
)

# 批量文本
report = client.validate_embeddings(
    input_text=["Hello", "World", "Test"],
)
```

### Audio - Speech (TTS)

```python
# 返回 (audio_bytes, is_valid)
audio_data, is_valid = client.validate_speech(
    model="tts-1",
    input_text="Hello, this is a test.",
    voice="alloy",  # alloy, echo, fable, onyx, nova, shimmer
)

# 保存音频
with open("output.mp3", "wb") as f:
    f.write(audio_data)
```

**注意**: Speech API 返回二进制音频数据，不返回 JSON。

### Audio - Transcription

```python
report = client.validate_transcription(
    file_path="audio.mp3",
    model="whisper-1",  # whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe
    response_format="json",  # json 或 verbose_json
)
```

### Audio - Translation

```python
report = client.validate_translation(
    file_path="foreign_audio.mp3",
    model="whisper-1",  # 仅支持 whisper-1
)
```

### Images - Generation

```python
report = client.validate_image_generation(
    prompt="A white cat sitting on a chair",
    model="dall-e-2",  # dall-e-2, dall-e-3
    size="256x256",    # dall-e-2: 256x256, 512x512, 1024x1024
    n=1,
)
```

### Images - Edit

```python
report = client.validate_image_edit(
    image_path="input.png",
    prompt="Add a hat to the cat",
    mask_path="mask.png",  # 可选，透明区域表示要编辑的部分
    model="dall-e-2",
)
```

### Images - Variation

```python
report = client.validate_image_variation(
    image_path="input.png",
    n=2,
    model="dall-e-2",  # 仅支持 dall-e-2
)
```

## 端点详情

### Chat Completions (`/v1/chat/completions`)

标准聊天 API，支持多轮对话。

- **模型**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo 等
- **支持流式**: `stream=True`

### Responses API (`/v1/responses`)

新版 API，支持工具调用、推理、网络搜索等高级功能。

- **模型**: gpt-4o, gpt-4o-mini 等
- **功能**: 工具调用、代码解释器、图片生成、网络搜索

### Embeddings (`/v1/embeddings`)

将文本转换为向量表示。

- **模型**: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
- **限制**: 单次请求最多 300,000 tokens

### Audio Speech (`/v1/audio/speech`)

文字转语音 (TTS)。

- **模型**: tts-1, tts-1-hd, gpt-4o-mini-tts
- **声音**: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse
- **格式**: mp3, opus, aac, flac, wav, pcm

### Audio Transcriptions (`/v1/audio/transcriptions`)

语音转文字。

- **模型**: whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe
- **支持格式**: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm

### Audio Translations (`/v1/audio/translations`)

将非英语音频翻译为英语文字。

- **模型**: whisper-1 (仅此)
- **支持格式**: 同 transcriptions

### Images Generations (`/v1/images/generations`)

根据文字描述生成图片。

- **模型**: dall-e-2, dall-e-3, gpt-image-1
- **尺寸**:
  - dall-e-2: 256x256, 512x512, 1024x1024
  - dall-e-3: 1024x1024, 1792x1024, 1024x1792

### Images Edits (`/v1/images/edits`)

编辑或扩展现有图片。

- **模型**: dall-e-2, gpt-image-1
- **要求**: PNG 格式，dall-e-2 要求 <4MB

### Images Variations (`/v1/images/variations`)

生成现有图片的变体。

- **模型**: dall-e-2 (仅此)
- **要求**: PNG 格式，<4MB
