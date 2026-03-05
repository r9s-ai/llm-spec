"""Asset resolution — resolves file paths and asset placeholders for test cases."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Any


class AssetResolver:
    """Resolves asset file paths and replaces $asset_* placeholders in request params.

    Search order for relative paths:
      1. config dir (parent of source_path)
      2. walk upward to suites-registry root
      3. suites-registry root itself
      4. current working directory
    """

    def __init__(self, source_path: Path | None = None) -> None:
        self.source_path = source_path
        self._bytes_cache: dict[Path, bytes] = {}

    # ── Public API ────────────────────────────────────────

    def resolve_placeholders(self, value: Any) -> Any:
        """Recursively resolve $asset_base64() / $asset_data_uri() in dicts/lists/strings."""
        if isinstance(value, dict):
            return {k: self.resolve_placeholders(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve_placeholders(v) for v in value]
        if isinstance(value, str):
            return self._resolve_function_string(value)
        return value

    def resolve_file_path(self, file_path_str: str) -> Path:
        """Resolve a relative file path to an absolute path using the search hierarchy."""
        raw = Path(file_path_str).expanduser()
        if raw.is_absolute():
            return raw

        rel = raw
        candidates: list[Path] = []

        if self.source_path is not None:
            cfg_dir = self.source_path.parent
            candidates.append(cfg_dir / rel)

            registry_root = self._detect_registry_root()
            cur = cfg_dir
            while True:
                candidates.append(cur / rel)
                if registry_root is not None and cur == registry_root:
                    break
                if cur.parent == cur:
                    break
                cur = cur.parent

            if registry_root is not None:
                candidates.append(registry_root / rel)

        registry_root = self._detect_registry_root()
        if registry_root is not None:
            candidates.append(registry_root / rel)

        candidates.append(Path.cwd() / rel)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return raw

    def prepare_upload_files(self, files: dict[str, str]) -> tuple[dict[str, Any], list[Any]]:
        """Resolve file paths and open file handles for upload.

        Returns ``(files_dict, opened_handles)`` — caller must close handles after use.
        """
        result: dict[str, Any] = {}
        opened: list[Any] = []
        for param_name, file_path_str in files.items():
            path = self.resolve_file_path(file_path_str)
            if not path.exists():
                raise FileNotFoundError(f"Test file not found: {file_path_str}")
            f = open(path, "rb")  # noqa: SIM115
            opened.append(f)
            result[param_name] = (path.name, f)
        return result, opened

    # ── Internal helpers ──────────────────────────────────

    @staticmethod
    def _strip_optional_quotes(text: str) -> str:
        s = text.strip()
        if len(s) >= 2 and (
            (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'"))
        ):
            return s[1:-1]
        return s

    def _read_bytes(self, path_str: str) -> tuple[Path, bytes]:
        resolved = self.resolve_file_path(path_str)
        if not resolved.exists():
            raise FileNotFoundError(f"Asset file not found: {path_str}")
        cached = self._bytes_cache.get(resolved)
        if cached is not None:
            return resolved, cached
        data = resolved.read_bytes()
        self._bytes_cache[resolved] = data
        return resolved, data

    def _resolve_function_string(self, text: str) -> str:
        stripped = text.strip()

        m_base64 = re.fullmatch(r"\$asset_base64\((.+)\)", stripped)
        if m_base64:
            raw_path = self._strip_optional_quotes(m_base64.group(1))
            _path, data = self._read_bytes(raw_path)
            return base64.b64encode(data).decode("ascii")

        m_data_uri = re.fullmatch(r"\$asset_data_uri\((.+)\)", stripped)
        if m_data_uri:
            arg_str = m_data_uri.group(1)
            path_part, sep, mime_part = arg_str.partition(",")
            raw_path = self._strip_optional_quotes(path_part)
            resolved, data = self._read_bytes(raw_path)
            mime = self._strip_optional_quotes(mime_part) if sep else ""
            if not mime:
                mime = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime};base64,{b64}"

        return text

    def _detect_registry_root(self) -> Path | None:
        if self.source_path is not None:
            for parent in [self.source_path.parent, *self.source_path.parents]:
                if parent.name == "suites-registry":
                    return parent
                if (parent / "suites-registry").is_dir():
                    return parent / "suites-registry"

        cwd = Path.cwd()
        if (cwd / "suites-registry").is_dir():
            return cwd / "suites-registry"
        for parent in cwd.parents:
            if parent.name == "suites-registry":
                return parent
            if (parent / "suites-registry").is_dir():
                return parent / "suites-registry"
        return None
