"""Result types — Layer 4 of the data model.

FailureInfo → TestVerdict → RunResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from llm_spec.suites.types import FocusParam


@dataclass
class FailureInfo:
    """Failure details, only present when status != 'pass'."""

    stage: str  # "schema" | "request" | "required_fields" | "stream_rules"
    code: str | None = None  # "SCHEMA_MISMATCH" | "TIMEOUT" etc.
    message: str = ""
    missing_fields: list[str] = field(default_factory=list)
    missing_events: list[str] = field(default_factory=list)


@dataclass
class TestVerdict:
    """Execution verdict for a single TestCase."""

    case_id: str
    test_name: str

    # Focus parameter
    focus: FocusParam | None = None

    # Verdict
    status: Literal["pass", "fail", "error"] = "error"

    # Timing
    started_at: str = ""
    finished_at: str = ""
    latency_ms: int | None = None

    # HTTP layer
    http_status: int | None = None

    # Check results (None = not executed)
    schema_ok: bool | None = None
    required_fields_ok: bool | None = None
    stream_rules_ok: bool | None = None

    # Failure details
    failure: FailureInfo | None = None

    # Debug snapshots (TODO: populate later)
    request_snapshot: dict[str, Any] | None = None
    response_body: Any = None


@dataclass
class RunResult:
    """Aggregated result for one SuiteSpec run."""

    run_id: str
    version: str = "run_result.v1"

    # Suite identity
    provider: str = ""
    model: str | None = None
    route: str | None = None
    endpoint: str = ""
    suite_name: str = ""

    # Timing
    started_at: str = ""
    finished_at: str = ""

    # Verdicts
    verdicts: list[TestVerdict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.verdicts)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.verdicts if v.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for v in self.verdicts if v.status != "pass")


__all__ = [
    "FailureInfo",
    "TestVerdict",
    "RunResult",
]
