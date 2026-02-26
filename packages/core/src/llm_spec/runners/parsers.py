"""Response parsers for streaming responses across providers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


from llm_spec.json_types import JSONValue


class StreamResponseParser:
    """Unified streaming response parser.

    Supports different provider streaming formats:
    - OpenAI/xAI/Anthropic: Server-Sent Events (SSE)
    - Gemini: JSON Lines or SSE

    Usage:
        parser = StreamResponseParser("openai")
        for chunk_bytes in client.stream(...):
            parsed_chunks = parser.parse_chunk(chunk_bytes)
            for chunk in parsed_chunks:
                # handle each parsed chunk
    """

    def __init__(self, provider: str):
        """Initialize the parser.

        Args:
            provider: provider name (openai, gemini, anthropic, xai)
        """
        self.provider = provider
        self.buffer = ""
        self._chunks: list[dict[str, Any]] = []

    def parse_chunk(self, chunk_bytes: bytes) -> list[dict[str, Any]]:
        """Parse a network chunk and return parsed data chunks.

        Args:
            chunk_bytes: raw bytes received from the transport layer

        Returns:
            Parsed chunks (may be empty if the network chunk does not contain a full data chunk).
        """
        self.buffer += chunk_bytes.decode("utf-8")

        if self.provider == "gemini":
            # Gemini may use JSON array streaming
            return self._parse_gemini_stream()
        else:
            # OpenAI, Anthropic, xAI use SSE
            return self._parse_sse()

    def _parse_sse(self) -> list[dict[str, Any]]:
        """Parse Server-Sent Events (SSE)."""
        results = []
        while "\n\n" in self.buffer:
            message, self.buffer = self.buffer.split("\n\n", 1)

            data = {}
            event_type = None

            for line in message.split("\n"):
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    content = line[6:].strip()
                    if content == "[DONE]":
                        # End marker, treated as a special event
                        data = {"status": "completed", "done": True}
                        break

                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        continue

            if data:
                # Inject event type into data if missing
                if event_type and "type" not in data:
                    data["type"] = event_type

                results.append(data)
                self._chunks.append(data)

        return results

    def _parse_gemini_stream(self) -> list[dict[str, Any]]:
        """Parse Gemini streaming responses (JSON array or SSE)."""
        # Try JSON Lines (one JSON per line)
        results = []
        if self.buffer.strip().startswith("{") and "\n" in self.buffer:
            lines = self.buffer.split("\n")
            # Keep the last (possibly incomplete) line in buffer
            self.buffer = lines[-1]

            for line in lines[:-1]:
                line = line.strip()
                if not line:
                    continue
                try:
                    # Remove trailing comma (for JSON array streaming)
                    if line.endswith(","):
                        line = line[:-1]
                    # Remove array brackets
                    if line == "[" or line == "]":
                        continue

                    data = json.loads(line)
                    results.append(data)
                    self._chunks.append(data)
                except json.JSONDecodeError:
                    continue
            return results

        return self._parse_sse()

    @property
    def all_chunks(self) -> list[dict[str, Any]]:
        """Return all parsed chunks."""
        return self._chunks

    def get_complete_content(self) -> str:
        """Extract and concatenate full text content from all chunks.

        Returns:
            Concatenated text content.
        """
        content_parts: list[str] = []

        for chunk in self._chunks:
            # OpenAI/xAI format
            if "choices" in chunk:
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    if "content" in delta and delta["content"]:
                        content_parts.append(delta["content"])

            # Gemini format
            elif "candidates" in chunk:
                for candidate in chunk.get("candidates", []):
                    content = candidate.get("content", {})
                    for part in content.get("parts", []):
                        if "text" in part:
                            content_parts.append(part["text"])

            # Anthropic format
            elif chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                delta_type = delta.get("type")
                # Text delta
                if delta_type == "text_delta" and "text" in delta:
                    content_parts.append(delta["text"])
                # JSON delta (tool input) - not included in text content

        return "".join(content_parts)

    def get_thinking_content(self) -> str:
        """Extract and concatenate thinking content (Anthropic thinking models).

        Returns:
            Concatenated thinking content.
        """
        thinking_parts: list[str] = []

        for chunk in self._chunks:
            # Anthropic thinking format
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "thinking_delta" and "thinking" in delta:
                    thinking_parts.append(delta["thinking"])

        return "".join(thinking_parts)

    def get_usage(self) -> dict[str, Any] | None:
        """Extract usage information from chunks.

        Returns:
            A usage dict if present, otherwise None.
        """
        if not self._chunks:
            return None

        # Try to use the last chunk
        last_chunk = self._chunks[-1]

        # OpenAI/xAI format (may appear on the last chunk)
        if "usage" in last_chunk and last_chunk["usage"]:
            return last_chunk["usage"]

        # Anthropic format (in message_delta event)
        for chunk in reversed(self._chunks):
            if chunk.get("type") == "message_delta":
                usage = chunk.get("usage")
                if usage:
                    return usage

        # Gemini format (usageMetadata on the last chunk)
        if "usageMetadata" in last_chunk:
            um = last_chunk["usageMetadata"]
            return {
                "prompt_tokens": um.get("promptTokenCount", 0),
                "completion_tokens": um.get("candidatesTokenCount", 0),
                "total_tokens": um.get("totalTokenCount", 0),
            }

        return None

    def get_finish_reason(self) -> str | None:
        """Extract finish reason from chunks.

        Returns:
            A finish reason string if present, otherwise None.
        """
        if not self._chunks:
            return None

        # OpenAI/xAI format
        last_chunk = self._chunks[-1]
        if "choices" in last_chunk:
            choices = last_chunk.get("choices", [])
            if choices and "finish_reason" in choices[0]:
                return choices[0]["finish_reason"]

        # Anthropic format (in message_delta events)
        for chunk in reversed(self._chunks):
            if chunk.get("type") == "message_delta":
                delta = chunk.get("delta", {})
                stop_reason = delta.get("stop_reason")
                if stop_reason:
                    return stop_reason

        # Gemini format
        if "candidates" in last_chunk:
            candidates = last_chunk.get("candidates", [])
            if candidates and "finishReason" in candidates[0]:
                return candidates[0]["finishReason"]

        return None

    def reset(self) -> None:
        """Reset parser state."""
        self.buffer = ""
        self._chunks = []

    def format_stream_response(
        self, raw_chunks: list[bytes]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Parse raw stream bytes and format them into a human-friendly JSON structure.

        Notes:
        - This calls ``self.parse_chunk()`` to convert ``raw_chunks`` into structured chunks,
          and returns a formatted object suitable for request/response logging.
        - It reuses the current parser instance (does not create a new StreamResponseParser),
          so runner-level parsing can avoid duplicate work.

        Args:
            raw_chunks: raw bytes chunks

        Returns:
            (formatted, parsed_chunks)

            The formatted structure is kept compatible with the older implementation:
              {"chunks": [...], "total_chunks": n, "raw_size_bytes": ...}
        """
        parsed_chunks: list[dict[str, Any]] = []
        for chunk in raw_chunks:
            # Simulate network framing: feed bytes directly
            parsed_chunks.extend(self.parse_chunk(chunk))

        formatted = {
            "chunks": parsed_chunks,
            "total_chunks": len(parsed_chunks),
            "raw_size_bytes": sum(len(c) for c in raw_chunks),
        }
        return formatted, parsed_chunks


class ResponseParser:
    """Non-streaming response parser."""

    @staticmethod
    def parse_response(response: object) -> JSONValue | str:
        """Best-effort extract response body for reporting.

        Preference order:
        1) JSON (dict/list/primitive) if response.json() succeeds
        2) text fallback
        """
        # Keep this method dependency-light (no hard dependency on httpx at runtime).
        try:
            json_method = getattr(response, "json", None)
            if callable(json_method):
                value: object = json_method()
                # Only accept JSON-shaped values
                if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
                    return value
        except Exception:
            pass

        # Binary-ish responses (e.g. audio) - store a lightweight summary instead of junk text.
        try:
            headers_obj = getattr(response, "headers", None)
            content_type: str | None = None
            if headers_obj is not None:
                # headers could be Mapping or httpx.Headers
                content_type_val = headers_obj.get("content-type")
                if isinstance(content_type_val, str):
                    content_type = content_type_val

            if content_type is not None and (
                content_type.startswith("audio/")
                or content_type.startswith("image/")
                or content_type.startswith("application/octet-stream")
            ):
                content = getattr(response, "content", b"")
                size = len(content) if isinstance(content, (bytes, bytearray)) else None
                return {
                    "binary": True,
                    "content_type": content_type,
                    "size_bytes": size,
                }
        except Exception:
            pass

        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return str(response)
