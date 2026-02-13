"""Mock data loader for integration tests.

Loads mock HTTP response data from JSON/JSONL files to support offline testing
without requiring real API credentials.
"""

from __future__ import annotations

import json
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
            base_dir: Base directory containing mock data files
                     (typically tests/integration/mocks/)
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
            test_name: Test case name (e.g., "test_baseline")
            is_stream: Whether this is a streaming response

        Returns:
            For non-streaming: dict with keys {status_code, headers, body}
            For streaming: Iterator[bytes] yielding SSE-formatted chunks

        Raises:
            FileNotFoundError: If the mock data file doesn't exist
        """
        # Build file path:
        # - non-stream: provider/endpoint_dir/test_name.json
        # - stream: provider/endpoint_dir/test_name.jsonl (preferred), fallback to .json for backward compatibility
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

        # Fallback logic: if a variant-specific mock file (e.g., name[variant].json)
        # is not found, try the base mock file (name.json) if it's a parameterized test.
        if not file_path.exists() and "[" in safe_name and "]" in safe_name:
            # Extract base name from variant name, e.g., "test_name[variant]" -> "test_name"
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
        """Replace all characters except alphanumeric, _, -, [, and ] with _."""
        import re

        # Replace unsafe characters with underscore
        return re.sub(r"[^a-zA-Z0-9_\-\[\]]", "_", name)

    def _load_json_response(self, file_path: Path) -> dict:
        """Load non-streaming JSON response.

        Expected format:
        {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "body": { ... actual response data ... }
        }

        Args:
            file_path: Path to JSON file

        Returns:
            Dict containing status_code, headers, and body
        """
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def _load_stream_response(self, file_path: Path) -> Iterator[bytes]:
        """Load streaming response from JSONL file.

        Each line in the JSONL file should be:
        {"type": "chunk"|"done", "data": <chunk_data>}

        This method converts JSONL to SSE format (Server-Sent Events):
        - Regular chunks: "data: {json}\\n\\n"
        - Done marker: "data: [DONE]\\n\\n"

        Args:
            file_path: Path to JSONL file

        Yields:
            SSE-formatted byte chunks
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
                    # Terminal marker
                    yield b"data: [DONE]\n\n"
                else:
                    # Data chunk
                    data_str = json.dumps(data, ensure_ascii=False)
                    yield f"data: {data_str}\n\n".encode()
