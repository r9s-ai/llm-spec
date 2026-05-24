#!/usr/bin/env python3
"""Block runtime databases and obvious LLM API secrets from commits."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SQLITE_HEADER = b"SQLite format 3\x00"
DENIED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
}
DENIED_RUNTIME_NAMES = {
    "llm_spec_web.db",
    "llm_spec_web.db-shm",
    "llm_spec_web.db-wal",
}

SECRET_PATTERNS = [
    ("LLM/OpenAI-style API key", re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Anthropic API key", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b")),
]

ALLOWLIST = {
    b"sk-test",
    b"sk-openai",
    b"sk-proxy",
    b"sk-ant-test",
}


def _is_allowlisted(match: bytes) -> bool:
    return match in ALLOWLIST or b"..." in match


def _redact(match: bytes) -> str:
    text = match.decode("utf-8", errors="replace")
    if len(text) <= 12:
        return "<redacted>"
    return f"{text[:6]}...{text[-4:]}"


def check_path(path: Path) -> list[str]:
    errors: list[str] = []
    normalized = path.as_posix()

    if not path.exists() or not path.is_file():
        return errors

    if path.name in DENIED_RUNTIME_NAMES or path.suffix.lower() in DENIED_SUFFIXES:
        errors.append(f"{normalized}: runtime database files must not be committed")

    data = path.read_bytes()
    if data.startswith(SQLITE_HEADER):
        errors.append(f"{normalized}: SQLite database content must not be committed")

    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(data):
            value = match.group(0)
            if _is_allowlisted(value):
                continue
            errors.append(f"{normalized}: possible {label} detected ({_redact(value)})")

    return errors


def main(argv: list[str]) -> int:
    errors: list[str] = []
    for arg in argv:
        errors.extend(check_path(Path(arg)))

    if not errors:
        return 0

    print("Sensitive file check failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print(
        "\nMove runtime data outside the repo, add it to .gitignore, and rotate any exposed key.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
