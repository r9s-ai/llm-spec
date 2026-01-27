"""OpenAI Audio 响应 Pydantic schemas"""

from pydantic import BaseModel


class AudioTranscriptionResponse(BaseModel):
    """Audio Transcription 响应模型"""

    text: str


class AudioTranslationResponse(BaseModel):
    """Audio Translation 响应模型"""

    text: str


class AudioSpeechResponse(BaseModel):
    """Audio Speech 响应模型（二进制音频数据，不需要验证）"""

    pass
