"""OpenAI Images 响应 Pydantic schemas"""

from pydantic import BaseModel


class ImageData(BaseModel):
    """单个图片数据"""

    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageResponse(BaseModel):
    """Images 响应模型"""

    created: int
    data: list[ImageData]
