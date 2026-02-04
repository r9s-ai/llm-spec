"""响应解析器 - 处理不同厂商的流式响应"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel

from llm_spec.validation.validator import ResponseValidator


class StreamParser:
    """统一流式响应解析器

    支持不同厂商的流式响应格式：
    - OpenAI/xAI/Anthropic: Server-Sent Events (SSE)
    - Gemini: JSON Lines 或 SSE

    用法:
        parser = StreamParser("openai", chunk_schema)
        for chunk_bytes in client.stream(...):
            parsed_chunks = parser.parse_chunk(chunk_bytes)
            for chunk in parsed_chunks:
                # 处理每个解析出的 chunk
    """

    def __init__(self, provider: str, chunk_schema: type[BaseModel] | None = None):
        """初始化解析器

        Args:
            provider: 厂商名称 (openai, gemini, anthropic, xai)
            chunk_schema: 可选的 Pydantic schema，用于验证每个 chunk
        """
        self.provider = provider
        self.chunk_schema = chunk_schema
        self.buffer = ""
        self._chunks: list[dict[str, Any]] = []

    def parse_chunk(self, chunk_bytes: bytes) -> list[dict[str, Any]]:
        """解析一个网络 chunk，返回解析出的数据 chunk 列表

        Args:
            chunk_bytes: 网络层收到的原始字节

        Returns:
            解析出的数据 chunk 列表（可能为空，因为一个网络 chunk
            可能不包含完整的数据 chunk）
        """
        self.buffer += chunk_bytes.decode("utf-8")

        if self.provider == "gemini":
            # Gemini 可能使用 JSON array streaming
            return self._parse_gemini_stream()
        else:
            # OpenAI, Anthropic, xAI 使用 SSE
            return self._parse_sse()

    def _parse_sse(self) -> list[dict[str, Any]]:
        """解析 Server-Sent Events 格式

        SSE 格式示例:
            data: {"id": "...", "choices": [...]}

            data: {"id": "...", "choices": [...]}

            data: [DONE]
        """
        results: list[dict[str, Any]] = []

        # SSE 事件由双换行分隔
        events = self.buffer.split("\n\n")
        self.buffer = events.pop()  # 保留最后不完整部分

        for event in events:
            data_lines: list[str] = []

            for line in event.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())

            if not data_lines:
                continue

            data_str = "\n".join(data_lines)

            # 跳过结束标记
            if data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)

                # 可选：验证 chunk 结构
                if self.chunk_schema:
                    result = ResponseValidator.validate_json(data, self.chunk_schema)
                    if not result.is_valid:
                        raise ValueError(f"Chunk validation failed: {result.error_message}")

                results.append(data)
                self._chunks.append(data)

            except json.JSONDecodeError:
                # 跳过无法解析的行
                pass

        return results

    def _parse_gemini_stream(self) -> list[dict[str, Any]]:
        """解析 Gemini 流式响应格式

        Gemini streamGenerateContent 返回 JSON array，逐行流式传输:
            [{"candidates": [...]}
            ,{"candidates": [...]}
            ]
        """
        results: list[dict[str, Any]] = []

        # 按行分割
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()  # 保留最后不完整部分

        for line in lines:
            line = line.strip()

            # 跳过空行和数组边界字符
            if not line or line in ("[", "]", ","):
                continue

            # 移除行首的逗号（Gemini 流式格式特点）
            if line.startswith(","):
                line = line[1:].strip()

            if not line:
                continue

            try:
                data = json.loads(line)

                # 可选：验证 chunk 结构
                if self.chunk_schema:
                    result = ResponseValidator.validate_json(data, self.chunk_schema)
                    if not result.is_valid:
                        raise ValueError(f"Chunk validation failed: {result.error_message}")

                results.append(data)
                self._chunks.append(data)

            except json.JSONDecodeError:
                # 跳过无法解析的行
                pass

        return results

    @property
    def all_chunks(self) -> list[dict[str, Any]]:
        """获取所有已解析的 chunks"""
        return self._chunks

    def validate_stream(self, rules: dict[str, Any]) -> None:
        """验证流式响应是否满足规则

        Args:
            rules: 验证规则，支持:
                - require_usage: 最后一个 chunk 必须包含 usage
                - min_chunks: 最少 chunk 数量

        Raises:
            ValueError: 验证失败
        """
        chunks = self._chunks

        if not chunks:
            raise ValueError("No chunks received")

        if rules.get("require_usage"):
            last_chunk = chunks[-1]
            if "usage" not in last_chunk:
                raise ValueError("Last chunk missing 'usage' field")

        min_chunks = rules.get("min_chunks", 1)
        if len(chunks) < min_chunks:
            raise ValueError(f"Expected at least {min_chunks} chunks, got {len(chunks)}")

    def get_complete_content(self) -> str:
        """从所有 chunks 中提取并拼接完整内容

        Returns:
            拼接后的完整文本内容
        """
        content_parts: list[str] = []

        for chunk in self._chunks:
            # OpenAI/xAI 格式
            if "choices" in chunk:
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    if "content" in delta and delta["content"]:
                        content_parts.append(delta["content"])

            # Gemini 格式
            elif "candidates" in chunk:
                for candidate in chunk.get("candidates", []):
                    content = candidate.get("content", {})
                    for part in content.get("parts", []):
                        if "text" in part:
                            content_parts.append(part["text"])

            # Anthropic 格式
            elif chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta" and "text" in delta:
                    content_parts.append(delta["text"])

        return "".join(content_parts)

    def reset(self) -> None:
        """重置解析器状态"""
        self.buffer = ""
        self._chunks = []
