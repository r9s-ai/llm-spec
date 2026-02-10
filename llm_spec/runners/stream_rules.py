"""Streaming validation (stream rules).

Notes:
- The runner parses transport bytes (raw_chunks) into parsed_chunks (list[dict]). This module turns
  streams into unified observations and performs declarative checks (required events, ordering, terminal, ...).
- This module must not import the runner (would create a circular dependency).
"""

from __future__ import annotations

import re
from typing import Any

Observation = dict[str, Any]


def extract_observations(
    *,
    provider: str,
    endpoint: str,
    parsed_chunks: list[dict[str, Any]] | None,
    raw_chunks: list[bytes] | None,
    stream_rules: dict[str, Any] | None,
) -> list[Observation]:
    """Convert a stream into unified observations for validate_stream().

    Current behavior:
    - By default ("auto") prefer parsed_chunks to generate event observations.
    - If parsed_chunks is empty but raw_chunks exists, fall back to bytes observations (reserved for binary streams).
    """
    extractor = None
    if isinstance(stream_rules, dict):
        extractor = stream_rules.get("extractor")

    extractor_name = (extractor or "auto").lower() if isinstance(extractor, str) else "auto"

    parsed_chunks = parsed_chunks or []
    raw_chunks = raw_chunks or []

    if extractor_name == "binary":
        return _extract_binary_observations(raw_chunks)

    if extractor_name in {"events", "sse_json", "auto"}:
        if parsed_chunks:
            return _extract_event_observations(provider=provider, parsed_chunks=parsed_chunks)
        if raw_chunks:
            # If we can't parse structured events, at least keep "bytes + EOF" observations.
            return _extract_binary_observations(raw_chunks)
        return []

    # Unknown extractor: fall back to safest option (events, else bytes).
    if parsed_chunks:
        return _extract_event_observations(provider=provider, parsed_chunks=parsed_chunks)
    if raw_chunks:
        return _extract_binary_observations(raw_chunks)
    return []


def validate_stream(
    *,
    provider: str,
    endpoint: str,
    observations: list[Observation],
    stream_rules: dict[str, Any] | None,
) -> list[str]:
    """Validate a stream using observations + stream_rules."""
    effective_rules = _resolve_stream_rules(
        provider=provider,
        endpoint=endpoint,
        stream_rules=stream_rules,
    )

    missing: list[str] = []

    observation_names = [o.get("name") for o in observations if isinstance(o, dict)]
    observed_event_names = [n for n in observation_names if isinstance(n, str)]
    observed_data = [
        o.get("data") for o in observations if isinstance(o, dict) and o.get("kind") == "event"
    ]

    min_observations = effective_rules.get("min_observations")
    if isinstance(min_observations, int) and len(observed_event_names) < min_observations:
        # Keep legacy error code name "min_chunks" for report compatibility.
        return [f"min_chunks:{min_observations}"]

    checks = effective_rules.get("checks")
    if isinstance(checks, list):
        missing.extend(_evaluate_stream_checks(checks, observed_event_names, observed_data))
        return missing

    # No explicit checks and no min_observations: treat as stream validation disabled.
    return []


def _evaluate_stream_checks(
    checks: list[Any],
    observed_event_names: list[str],
    observed_data: list[dict[str, Any] | None],
) -> list[str]:
    missing: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        check_type = check.get("type")
        if not isinstance(check_type, str):
            continue
        ct = check_type.lower()

        if ct == "required":
            reqs = check.get("values")
            if isinstance(reqs, list):
                for req in reqs:
                    if not _is_requirement_satisfied(req, observed_event_names):
                        missing.append(_format_requirement_label(req))

        elif ct == "required_any_of":
            groups = check.get("groups")
            if isinstance(groups, list):
                for group in groups:
                    if not isinstance(group, list) or not group:
                        continue
                    if any(_is_requirement_satisfied(req, observed_event_names) for req in group):
                        continue
                    missing.append(
                        f"any_of:({'|'.join(_format_requirement_label(r) for r in group)})"
                    )

        elif ct == "required_sequence":
            seq = check.get("values")
            if isinstance(seq, list) and seq:
                missing.extend(_find_missing_sequence_items(seq, observed_event_names))

        elif ct == "required_terminal":
            terminal = check.get("value")
            if terminal is None:
                continue
            if not observed_event_names or not _matches_requirement(
                terminal, observed_event_names[-1]
            ):
                missing.append(f"terminal:{_format_requirement_label(terminal)}")

        elif ct == "required_field":
            field_path = check.get("field")
            found = False
            for data in observed_data:
                if data and _get_value_at_path_local(data, field_path) is not None:
                    found = True
                    break
            if not found:
                missing.append(f"field:{field_path}")

    return missing


def _resolve_stream_rules(
    *,
    provider: str,
    endpoint: str,
    stream_rules: dict[str, Any] | None,
) -> dict[str, Any]:
    if not stream_rules:
        # No explicit stream_rules: use provider+endpoint defaults (or empty dict).
        return _default_stream_rules_for_endpoint(provider=provider, endpoint=endpoint) or {}

    if isinstance(stream_rules, dict) and stream_rules.get("inherit_defaults") is True:
        defaults = _default_stream_rules_for_endpoint(provider=provider, endpoint=endpoint) or {}
        merged = dict(defaults)
        merged.update(stream_rules)
        return merged

    return stream_rules


def _default_stream_rules_for_endpoint(*, provider: str, endpoint: str) -> dict[str, Any] | None:
    provider = (provider or "").lower()
    endpoint = endpoint or ""

    # Anthropic /v1/messages streaming: event types are fixed; missing events likely indicate upstream issues.
    if provider == "anthropic" and endpoint.startswith("/v1/messages"):
        return {
            "min_observations": 1,
            "checks": [
                {
                    "type": "required_sequence",
                    "values": [
                        "message_start",
                        "content_block_start",
                        "content_block_delta",
                        "content_block_stop",
                        "message_delta",
                        "message_stop",
                    ],
                },
                {"type": "required_terminal", "value": "message_stop"},
            ],
        }

    # OpenAI Responses (/v1/responses) streaming:
    # - SSE event stream typically converges on response.completed, then ends with "data: [DONE]" (mapped to [DONE])
    # - Text output is usually carried by content_part + output_text.* events
    if provider == "openai" and endpoint.startswith("/v1/responses"):
        return {
            "min_observations": 1,
            "checks": [
                {
                    "type": "required_sequence",
                    "values": [
                        "response.created",
                        "response.output_item.added",
                        "response.content_part.added",
                        "response.output_text.delta",
                        "response.output_text.done",
                        "response.content_part.done",
                        "response.output_item.done",
                        "response.completed",
                        "[DONE]",
                    ],
                },
                {"type": "required_terminal", "value": "[DONE]"},
            ],
        }

    # OpenAI/xAI Chat Completions streaming: terminates with [DONE] (parser maps it to [DONE]).
    if provider in {"openai", "xai"} and endpoint.startswith("/v1/chat/completions"):
        return {
            "min_observations": 1,
            "checks": [
                {"type": "required_terminal", "value": "[DONE]"},
            ],
        }

    # Gemini: top-level chunk structure is consistent; usually no special event checks are required.
    return None


def _extract_event_observations(
    *, provider: str, parsed_chunks: list[dict[str, Any]]
) -> list[Observation]:
    observations: list[Observation] = []
    for chunk in parsed_chunks:
        event_name = _infer_event_name(provider=provider, chunk=chunk)
        observations.append(
            {
                "kind": "event",
                "name": event_name,
                "data": chunk,
            }
        )
    return observations


def _extract_binary_observations(raw_chunks: list[bytes]) -> list[Observation]:
    observations: list[Observation] = []
    for b in raw_chunks:
        observations.append(
            {
                "kind": "bytes",
                "name": "bytes",
                "n": len(b),
            }
        )
    if raw_chunks:
        observations.append({"kind": "terminal", "name": "eof"})
    return observations


def _infer_event_name(*, provider: str, chunk: dict[str, Any]) -> str:
    if chunk.get("done") is True:
        return "[DONE]"

    chunk_type = chunk.get("type")
    if isinstance(chunk_type, str) and chunk_type:
        return chunk_type

    # OpenAI/xAI chat.completions streaming chunk
    if provider in {"openai", "xai"} and chunk.get("object") == "chat.completion.chunk":
        return "chat.completion.chunk"

    # Gemini has no explicit event type; use a placeholder so rules can validate min_chunks/terminal.
    if provider == "gemini":
        return "gemini.chunk"

    return "__unknown__"


def _format_requirement_label(req: Any) -> str:
    if isinstance(req, str):
        return req
    if isinstance(req, dict):
        if isinstance(req.get("event"), str):
            return req["event"]
        if isinstance(req.get("regex"), str):
            return f"re:{req['regex']}"
    return str(req)


def _matches_requirement(req: Any, event_name: str) -> bool:
    if isinstance(req, str):
        return event_name == req
    if isinstance(req, dict):
        event = req.get("event")
        if isinstance(event, str):
            return event_name == event
        regex = req.get("regex")
        if isinstance(regex, str):
            return re.search(regex, event_name) is not None
    return False


def _is_requirement_satisfied(req: Any, observed_event_names: list[str]) -> bool:
    min_count = 1
    max_count: int | None = None
    if isinstance(req, dict):
        if isinstance(req.get("min"), int):
            min_count = req["min"]
        if isinstance(req.get("max"), int):
            max_count = req["max"]

    count = sum(1 for e in observed_event_names if _matches_requirement(req, e))
    if count < min_count:
        return False
    # Exceeding max is structural, but current API only returns "missing"; treat as unsatisfied.
    return not (max_count is not None and count > max_count)


def _find_missing_sequence_items(
    required_sequence: list[Any],
    observed_event_names: list[str],
) -> list[str]:
    """Require ``required_sequence`` to appear as a subsequence (extra events allowed)."""
    missing: list[str] = []
    idx = 0
    for req in required_sequence:
        found = False
        while idx < len(observed_event_names):
            if _matches_requirement(req, observed_event_names[idx]):
                found = True
                idx += 1
                break
            idx += 1
        if not found:
            missing.append(_format_requirement_label(req))
    return missing


def _get_value_at_path_local(obj: dict[str, Any], path: str | None) -> Any:
    """Helper to get value at path (mini-duplicate of runner.py to avoid circular dep)."""
    if not path:
        return None
    parts = path.split(".")
    current = obj
    for part in parts:
        # Simple dict traversal (array index support omitted for brevity/simplicity in stream chunks)
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current
