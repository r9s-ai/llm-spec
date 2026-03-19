"""Execution-layer data structures."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from llm_spec.client.http_client import HTTPClient
from llm_spec.suites.types import CoverParams, ExecutableCase, SuiteSpec

if TYPE_CHECKING:
    from llm_spec.execute.executor import Executor


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
    """Execution verdict for a single ExecutableCase."""

    case_id: str
    test_name: str

    # Covered parameters
    cover_params: list[CoverParams] = field(default_factory=list)

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


@dataclass
class TaskHandle:
    task_id: str
    loop: asyncio.AbstractEventLoop
    root_task: asyncio.Task[Any]


@dataclass
class ExecutionProgress:
    """Payload delivered to progress callbacks."""

    case: ExecutableCase
    verdict: TestVerdict
    index: int
    done: int
    total: int


@dataclass
class SuiteCallbackContext:
    """Passed to suite-level callbacks, gives caller access to suite execution context."""

    suite: SuiteSpec
    cases: list[ExecutableCase]
    executor: Executor


@dataclass
class SuiteResult:
    """Aggregated result for one suite execution."""

    suite: SuiteSpec
    verdicts: list[TestVerdict]
    run_result: RunResult
    error: str | None = None


@dataclass
class _SuiteState:
    suite: SuiteSpec
    cases: list[ExecutableCase]
    verdicts: list[TestVerdict | None]
    executor: Executor
    http_client: HTTPClient
    started_at: str | None = None
    finished_at: str | None = None
    done_count: int = 0


__all__ = [
    "FailureInfo",
    "TestVerdict",
    "RunResult",
    "TaskHandle",
    "ExecutionProgress",
    "SuiteCallbackContext",
    "SuiteResult",
]
