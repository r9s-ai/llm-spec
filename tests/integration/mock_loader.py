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
        # Build file path: provider/endpoint_dir/test_name{.json|_stream.jsonl}
        endpoint_dir = endpoint.strip("/").replace("/", "_")
        suffix = "_stream.jsonl" if is_stream else ".json"
        mock_file = self.base_dir / provider / endpoint_dir / f"{test_name}{suffix}"

        if not mock_file.exists():
            raise FileNotFoundError(
                f"Mock data not found: {mock_file}\n"
                f"Please create mock data for {provider}/{endpoint_dir}/{test_name}"
            )

        if is_stream:
            return self._load_stream_response(mock_file)
        else:
            return self._load_json_response(mock_file)

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
                if not line:
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
