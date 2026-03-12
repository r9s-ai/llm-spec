"""Mock data loader for offline testing.

Loads mock HTTP response data from JSON/JSONL files to support offline testing
without requiring real API credentials.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path


class MockDataLoader:
    """Loader for mock HTTP response data.

    Supports both streaming (JSONL) and non-streaming (JSON) response formats.
    Mock files are organized by provider/endpoint/test_name.
    """

    def __init__(self, base_dir: Path):
        """Initialize the mock data loader.

        Args:
            base_dir: Base directory containing mock data files.
        """
        self.base_dir = base_dir

    def load_response(
        self,
        provider: str,
        endpoint: str,
        test_name: str,
        is_stream: bool = False,
    ) -> dict | Iterator[bytes]:
        """Load mock response data for a test case.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "gemini")
            endpoint: API endpoint path (e.g., "/v1/chat/completions")
            test_name: Test case name (e.g., "baseline")
            is_stream: Whether this is a streaming response

        Returns:
            For non-streaming: dict with keys {status_code, headers, body}
            For streaming: Iterator[bytes] yielding SSE-formatted chunks

        Raises:
            FileNotFoundError: If the mock data file doesn't exist
        """
        endpoint_dir = endpoint.strip("/").replace("/", "_")
        safe_name = self._sanitize_filename(test_name)
        stream_fallback_path: Path | None = None
        if is_stream:
            file_path = self.base_dir / provider / endpoint_dir / f"{safe_name}.jsonl"
            stream_fallback_path = self.base_dir / provider / endpoint_dir / f"{safe_name}.json"
        else:
            file_path = self.base_dir / provider / endpoint_dir / f"{safe_name}.json"

        # Backward compatibility: stream mocks previously used `.json` extension.
        if (
            is_stream
            and not file_path.exists()
            and stream_fallback_path
            and stream_fallback_path.exists()
        ):
            file_path = stream_fallback_path

        # Fallback: parameterized test variant → base mock file.
        if not file_path.exists() and "[" in safe_name and "]" in safe_name:
            base_name = safe_name.split("[", 1)[0]
            if is_stream:
                fallback_jsonl = self.base_dir / provider / endpoint_dir / f"{base_name}.jsonl"
                fallback_json = self.base_dir / provider / endpoint_dir / f"{base_name}.json"
                if fallback_jsonl.exists():
                    file_path = fallback_jsonl
                elif fallback_json.exists():
                    file_path = fallback_json
            else:
                fallback_file = self.base_dir / provider / endpoint_dir / f"{base_name}.json"
                if fallback_file.exists():
                    file_path = fallback_file

        if not file_path.exists():
            raise FileNotFoundError(
                f"Mock data not found: {file_path}\n"
                f"Please create mock data for {provider}/{endpoint_dir}/{test_name}"
            )

        if is_stream:
            return self._load_stream_response(file_path)
        else:
            return self._load_json_response(file_path)

    def _sanitize_filename(self, name: str) -> str:
        """Replace unsafe filename characters with underscore."""
        return re.sub(r"[^a-zA-Z0-9_.:\-\[\],]", "_", name)

    def _load_json_response(self, file_path: Path) -> dict:
        """Load non-streaming JSON response."""
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def _load_stream_response(self, file_path: Path) -> Iterator[bytes]:
        """Load streaming response from JSONL file.

        Converts JSONL to SSE format (Server-Sent Events).
        """
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("#"):
                    continue

                event = json.loads(line)
                event_type = event.get("type", "chunk")
                data = event.get("data")

                if event_type == "done":
                    yield b"data: [DONE]\n\n"
                else:
                    sse_event = event.get("event")
                    data_str = json.dumps(data, ensure_ascii=False)
                    if sse_event:
                        yield f"event: {sse_event}\ndata: {data_str}\n\n".encode()
                    else:
                        yield f"data: {data_str}\n\n".encode()
