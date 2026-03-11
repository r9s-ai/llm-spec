"""Concurrent test execution engine.

The Executor handles:
- Concurrent test scheduling with semaphore-based throttling
- Progress callbacks (callers inject side-effects like DB writes, SSE pushes)
- Cancellation (immediate, no DB polling required)

``run_suites()`` provides a high-level API for multi-suite orchestration:
- Creates HTTPClient + adapter per provider automatically (or uses caller-supplied factory)
- Controls suite-level and test-level concurrency
- Delivers suite-level callbacks (on_suite_start / on_suite_done / on_suite_error)
- Aggregates per-suite results
- Manages client lifecycle (cleanup on completion)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_spec.adapters.api_family import create_api_family_adapter
from llm_spec.adapters.base import ProviderAdapter
from llm_spec.cancellation_registry import cancellation_registry
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig
from llm_spec.results.result_types import FailureInfo, RunResult, TestVerdict
from llm_spec.results.task_result import build_run_result
from llm_spec.runners.runner import TestRunner
from llm_spec.suites.registry import Registry, build_execution_plan
from llm_spec.suites.types import SuiteSpec, TestCase


@dataclass
class ExecutionProgress:
    """Payload delivered to progress callbacks."""

    case: TestCase
    verdict: TestVerdict
    index: int
    done: int
    total: int


OnTestStart = Callable[[TestCase, int, int], Awaitable[None]] | None
OnTestDone = Callable[[ExecutionProgress], Awaitable[None]] | None

# ── Client factory type ───────────────────────────────────

ClientFactory = Callable[[str, AppConfig], tuple[HTTPClient, ProviderAdapter]]
"""``(provider_id, app_config) → (http_client, adapter)``"""


# ── Suite-level callback types ────────────────────────────


@dataclass
class SuiteContext:
    """Passed to suite-level callbacks, gives caller access to executor for cancellation."""

    suite: SuiteSpec
    cases: list[TestCase]
    executor: Executor


OnSuiteStart = Callable[["SuiteContext"], Awaitable[None]] | None
OnSuiteDone = Callable[["SuiteContext", "SuiteResult"], Awaitable[None]] | None
OnSuiteError = Callable[["SuiteContext", Exception], Awaitable[None]] | None


def _error_verdict(case: TestCase, error: Exception) -> TestVerdict:
    now = datetime.now(UTC).isoformat()
    return TestVerdict(
        case_id=case.case_id,
        test_name=case.test_name,
        focus=case.focus,
        status="error",
        started_at=now,
        finished_at=now,
        failure=FailureInfo(
            stage="request",
            code="REQUEST_ERROR",
            message=str(error),
        ),
    )


def _cancelled_verdict(case: TestCase) -> TestVerdict:
    now = datetime.now(UTC).isoformat()
    return TestVerdict(
        case_id=case.case_id,
        test_name=case.test_name,
        focus=case.focus,
        status="error",
        started_at=now,
        finished_at=now,
        failure=FailureInfo(
            stage="request",
            code="CANCELLED",
            message="Test execution was cancelled",
        ),
    )


def create_provider_adapter(
    provider: str,
    config: AppConfig,
) -> tuple[HTTPClient, ProviderAdapter]:
    """Create HTTPClient + ProviderAdapter from application config.

    The caller owns the returned HTTPClient and must close it when done.

    Returns:
        ``(http_client, adapter)`` tuple.
    """
    provider_cfg = config.get_provider_config(provider)
    http_client = HTTPClient(default_timeout=provider_cfg.timeout)
    adapter = create_api_family_adapter(
        provider=provider,
        config=provider_cfg,
        http_client=http_client,
    )
    return http_client, adapter


class Executor:
    """Concurrent test execution engine.

    Usage::

        executor = Executor(client, max_concurrent=5)
        verdicts = await executor.run_all(cases)

        # To cancel from another coroutine / thread:
        executor.cancel()
    """

    def __init__(
        self,
        client: ProviderAdapter,
        *,
        max_concurrent: int = 5,
        source_path: Path | None = None,
        on_test_start: OnTestStart = None,
        on_test_done: OnTestDone = None,
    ) -> None:
        self._runner = TestRunner(client=client, source_path=source_path)
        self._max_concurrent = max_concurrent
        self._on_test_start = on_test_start
        self._on_test_done = on_test_done
        self._cancelled = False
        self._inflight_tasks: list[asyncio.Task[Any]] = []
        self._done_count = 0

    # ── Public API ────────────────────────────────────────

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation of all in-flight tests.

        Safe to call from any thread (sets a flag + cancels asyncio tasks).
        """
        self._cancelled = True
        for t in self._inflight_tasks:
            if not t.done():
                t.cancel()

    async def run_all(self, cases: list[TestCase]) -> list[TestVerdict]:
        """Execute *cases* concurrently and return ordered verdicts.

        Respects ``max_concurrent`` via an asyncio.Semaphore.
        Delivers ``on_test_start`` / ``on_test_done`` callbacks as each test
        begins / completes.
        """
        if not cases:
            return []

        total = len(cases)
        sem = asyncio.Semaphore(self._max_concurrent)
        results: dict[int, TestVerdict] = {}
        self._done_count = 0

        async def _run_one(idx: int, case: TestCase) -> None:
            if self._cancelled:
                results[idx] = _cancelled_verdict(case)
                return

            if self._on_test_start:
                await self._on_test_start(case, idx, total)

            async with sem:
                if self._cancelled:
                    results[idx] = _cancelled_verdict(case)
                    return
                verdict = await self.run_one(case)

            results[idx] = verdict
            self._done_count += 1

            if self._on_test_done:
                await self._on_test_done(
                    ExecutionProgress(
                        case=case,
                        verdict=verdict,
                        index=idx,
                        done=self._done_count,
                        total=total,
                    )
                )

        self._inflight_tasks = [asyncio.create_task(_run_one(i, c)) for i, c in enumerate(cases)]
        await asyncio.gather(*self._inflight_tasks, return_exceptions=True)
        self._inflight_tasks.clear()

        # Return ordered verdicts; fill gaps with cancelled placeholders
        return [results.get(i, _cancelled_verdict(cases[i])) for i in range(total)]

    async def run_one(self, case: TestCase) -> TestVerdict:
        """Execute a single test case. No concurrency control.

        Used directly for retry, and internally by ``run_all``.
        """
        try:
            return await self._runner.run_async(case)
        except asyncio.CancelledError:
            return _cancelled_verdict(case)
        except Exception as e:
            return _error_verdict(case, e)


# ── High-level multi-suite API ────────────────────────────


@dataclass
class SuiteResult:
    """Aggregated result for one suite execution."""

    suite: SuiteSpec
    verdicts: list[TestVerdict]
    run_result: RunResult
    error: str | None = None


async def run_suites(
    registry: Registry,
    config: AppConfig,
    *,
    suite_ids: list[str] | None = None,
    selected_tests: dict[str, set[str]] | None = None,
    max_concurrent_suites: int = 3,
    max_concurrent_tests: int = 5,
    on_test_start: OnTestStart = None,
    on_test_done: OnTestDone = None,
    on_suite_start: OnSuiteStart = None,
    on_suite_done: OnSuiteDone = None,
    on_suite_error: OnSuiteError = None,
    client_factory: ClientFactory | None = None,
) -> list[SuiteResult]:
    """Execute multiple suites with suite-level and test-level concurrency.

    This is the top-level entry point for external callers who want to run
    multiple suites without managing HTTPClient/adapter lifecycle manually.

    Args:
        registry: Parsed suite registry snapshot.
        config: Application config with provider credentials.
        suite_ids: Which suites to run (default: all in registry).
        selected_tests: Per-suite test selection, keyed by suite_id.
        max_concurrent_suites: How many suites run in parallel.
        max_concurrent_tests: Per-suite test concurrency.
        on_test_start: Callback fired before each test begins.
        on_test_done: Callback fired after each test completes.
        on_suite_start: Callback fired before a suite begins (receives SuiteContext).
        on_suite_done: Callback fired after a suite completes successfully.
        on_suite_error: Callback fired when a suite fails with an exception.
        client_factory: Custom ``(provider, config) → (http_client, adapter)`` factory.
            Defaults to ``create_provider_adapter``.

    Returns:
        A ``SuiteResult`` per requested suite, in the same order as *suite_ids*.
    """
    ids = suite_ids if suite_ids is not None else registry.suite_ids
    suites: list[SuiteSpec] = []
    for sid in ids:
        s = registry.get_suite(sid)
        if s is None:
            raise KeyError(f"Suite not found: {sid}")
        suites.append(s)

    factory = client_factory or create_provider_adapter
    sem = asyncio.Semaphore(max(1, max_concurrent_suites))
    results: dict[int, SuiteResult] = {}

    async def _run_suite(idx: int, suite: SuiteSpec) -> None:
        async with sem:
            result = await _execute_one_suite(
                suite=suite,
                config=config,
                selected=selected_tests.get(suite.suite_id) if selected_tests else None,
                max_concurrent_tests=max_concurrent_tests,
                on_test_start=on_test_start,
                on_test_done=on_test_done,
                on_suite_start=on_suite_start,
                on_suite_done=on_suite_done,
                on_suite_error=on_suite_error,
                client_factory=factory,
            )
            results[idx] = result

    await asyncio.gather(*(_run_suite(i, s) for i, s in enumerate(suites)))
    return [results[i] for i in range(len(suites))]


async def run_task_suites(
    task_id: str,
    registry: Registry,
    config: AppConfig,
    *,
    suite_ids: list[str] | None = None,
    selected_tests: dict[str, set[str]] | None = None,
    max_concurrent_suites: int = 3,
    max_concurrent_tests: int = 5,
    on_test_start: OnTestStart = None,
    on_test_done: OnTestDone = None,
    on_suite_start: OnSuiteStart = None,
    on_suite_done: OnSuiteDone = None,
    on_suite_error: OnSuiteError = None,
    client_factory: ClientFactory | None = None,
) -> list[SuiteResult]:
    """Execute suites and register/unregister task cancellation handles.

    This wraps ``run_suites`` so caller layers (web/CLI) do not need to manage
    loop/task registration for cross-thread cancellation.
    """
    current = asyncio.current_task()
    if current is not None:
        cancellation_registry.register_task(task_id, asyncio.get_running_loop(), current)

    try:
        return await run_suites(
            registry,
            config,
            suite_ids=suite_ids,
            selected_tests=selected_tests,
            max_concurrent_suites=max_concurrent_suites,
            max_concurrent_tests=max_concurrent_tests,
            on_test_start=on_test_start,
            on_test_done=on_test_done,
            on_suite_start=on_suite_start,
            on_suite_done=on_suite_done,
            on_suite_error=on_suite_error,
            client_factory=client_factory,
        )
    finally:
        cancellation_registry.unregister_task(task_id)


def cancel_task_execution(task_id: str) -> bool:
    """Request cancellation of one task execution by ID."""
    return cancellation_registry.cancel_task(task_id)


async def _execute_one_suite(
    *,
    suite: SuiteSpec,
    config: AppConfig,
    selected: set[str] | None,
    max_concurrent_tests: int,
    on_test_start: OnTestStart,
    on_test_done: OnTestDone,
    on_suite_start: OnSuiteStart,
    on_suite_done: OnSuiteDone,
    on_suite_error: OnSuiteError,
    client_factory: ClientFactory,
) -> SuiteResult:
    """Execute one suite end-to-end: create client → run → cleanup."""

    cases = build_execution_plan(suite, selected_tests=selected)
    http_client, adapter = client_factory(suite.provider_id, config)
    executor = Executor(
        client=adapter,
        max_concurrent=max_concurrent_tests,
        source_path=suite.source_path,
        on_test_start=on_test_start,
        on_test_done=on_test_done,
    )
    ctx = SuiteContext(suite=suite, cases=cases, executor=executor)

    try:
        if on_suite_start:
            await on_suite_start(ctx)

        started_at = datetime.now(UTC).isoformat()
        verdicts = await executor.run_all(cases)
        finished_at = datetime.now(UTC).isoformat()

        run_result = build_run_result(
            run_id=suite.suite_id,
            started_at=started_at,
            finished_at=finished_at,
            provider=suite.provider_id,
            model=suite.model_id,
            route=suite.route_id,
            endpoint=suite.endpoint,
            suite_name=suite.suite_name,
            verdicts=verdicts,
        )
        result = SuiteResult(suite=suite, verdicts=verdicts, run_result=run_result)

        if on_suite_done:
            await on_suite_done(ctx, result)

        return result
    except Exception as exc:
        error_result = SuiteResult(
            suite=suite,
            verdicts=[],
            run_result=build_run_result(
                run_id=suite.suite_id,
                started_at=datetime.now(UTC).isoformat(),
                finished_at=datetime.now(UTC).isoformat(),
                provider=suite.provider_id,
                model=suite.model_id,
                route=suite.route_id,
                endpoint=suite.endpoint,
                suite_name=suite.suite_name,
                verdicts=[],
            ),
            error=str(exc),
        )

        if on_suite_error:
            await on_suite_error(ctx, exc)

        return error_result
    finally:
        await http_client.close_async()
