"""Concurrent test execution engine.

The Executor handles:
- Concurrent test scheduling with semaphore-based throttling
- Progress callbacks (callers inject side-effects like DB writes, SSE pushes)
- Task-level cancellation (immediate, no DB polling required)

``run_suites()`` provides a high-level API for multi-suite orchestration:
- Creates HTTPClient + adapter per provider automatically (or uses caller-supplied factory)
- Controls global test concurrency across all suites
- Delivers suite-level callbacks (on_suite_start / on_suite_done / on_suite_error)
- Aggregates per-suite results
- Manages client lifecycle (cleanup on completion)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from llm_spec.adapters.api_family import create_api_family_adapter
from llm_spec.adapters.base import ProviderAdapter
from llm_spec.client.http_client import HTTPClient
from llm_spec.config.loader import AppConfig
from llm_spec.execute.runners.runner import TestRunner, error_verdict
from llm_spec.execute.types import (
    ExecutionProgress,
    FailureInfo,
    RunResult,
    SuiteCallbackContext,
    SuiteResult,
    TaskHandle,
    TestVerdict,
    _SuiteState,
)
from llm_spec.suites.registry import Registry, build_executable_cases
from llm_spec.suites.types import ExecutableCase, SuiteSpec

# ── Client factory type ───────────────────────────────────


class TaskCancellationRegistry:
    """Global in-memory registry for active task-level cancellation handles."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = Lock()

    def register_task(
        self,
        task_id: str,
        loop: asyncio.AbstractEventLoop,
        root_task: asyncio.Task[Any],
    ) -> None:
        with self._lock:
            self._tasks[task_id] = TaskHandle(task_id=task_id, loop=loop, root_task=root_task)

    def unregister_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel one active task execution tree by task ID."""
        with self._lock:
            handle = self._tasks.get(task_id)
        if handle is None:
            return False

        def _cancel_all() -> None:
            handle.root_task.cancel()

        handle.loop.call_soon_threadsafe(_cancel_all)
        return True


cancellation_registry = TaskCancellationRegistry()

# ── Result helpers ────────────────────────────────────────


def build_run_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    provider: str,
    model: str | None,
    route: str | None,
    endpoint: str,
    suite_name: str = "",
    verdicts: list[TestVerdict],
) -> RunResult:
    """Build a RunResult from collected verdicts."""
    return RunResult(
        run_id=run_id,
        provider=provider,
        model=model,
        route=route,
        endpoint=endpoint,
        suite_name=suite_name,
        started_at=started_at,
        finished_at=finished_at,
        verdicts=verdicts,
    )


OnTestStart = Callable[[ExecutableCase, int, int], Awaitable[None]] | None
OnTestDone = Callable[[ExecutionProgress], Awaitable[None]] | None


OnSuiteStart = Callable[[SuiteCallbackContext], Awaitable[None]] | None
OnSuiteDone = Callable[[SuiteCallbackContext, SuiteResult], Awaitable[None]] | None
OnSuiteError = Callable[[SuiteCallbackContext, Exception], Awaitable[None]] | None

ClientFactory = Callable[[str, AppConfig], tuple[HTTPClient, ProviderAdapter]]
"""``(provider_id, app_config) → (http_client, adapter)``"""


# ── Suite-level callback types ────────────────────────────


def _cancelled_verdict(case: ExecutableCase) -> TestVerdict:
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


def _build_error_result(suite: SuiteSpec, exc: Exception) -> SuiteResult:
    return SuiteResult(
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


async def _prepare_suite_states(
    suites: list[SuiteSpec],
    *,
    selected_tests: dict[str, set[str]] | None,
    config: AppConfig,
    factory: ClientFactory,
    max_concurrent_tests: int,
    on_suite_error: OnSuiteError,
) -> tuple[list[_SuiteState | None], list[SuiteResult | None]]:
    suite_states: list[_SuiteState | None] = [None] * len(suites)
    results_by_index: list[SuiteResult | None] = [None] * len(suites)

    for idx, suite in enumerate(suites):
        http_client: HTTPClient | None = None
        executor: Executor | None = None
        ctx: SuiteCallbackContext | None = None
        try:
            cases = build_executable_cases(
                suite, selected_tests=selected_tests.get(suite.suite_id) if selected_tests else None
            )
            http_client, adapter = factory(suite.provider_id, config)
            executor = Executor(
                client=adapter,
                max_concurrent=max_concurrent_tests,
                source_path=suite.source_path,
            )
            ctx = SuiteCallbackContext(suite=suite, cases=cases, executor=executor)
            suite_states[idx] = _SuiteState(
                suite=suite,
                cases=cases,
                verdicts=[None] * len(cases),
                executor=executor,
                http_client=http_client,
            )
        except Exception as exc:
            if on_suite_error and ctx is not None:
                await on_suite_error(ctx, exc)
            if http_client is not None:
                await http_client.close_async()
            results_by_index[idx] = _build_error_result(suite, exc)

    return suite_states, results_by_index


async def _run_case(
    state: _SuiteState,
    case_idx: int,
    *,
    sem: asyncio.Semaphore,
    on_test_start: OnTestStart,
    on_test_done: OnTestDone,
) -> None:
    case = state.cases[case_idx]

    if on_test_start:
        await on_test_start(case, case_idx, len(state.cases))
    if state.started_at is None:
        state.started_at = datetime.now(UTC).isoformat()

    try:
        async with sem:
            verdict = await state.executor.run_one(case)
    except asyncio.CancelledError:
        verdict = _cancelled_verdict(case)
    except Exception as exc:
        verdict = error_verdict(case, message=str(exc), code="REQUEST_ERROR")

    state.verdicts[case_idx] = verdict
    state.done_count += 1
    state.finished_at = datetime.now(UTC).isoformat()

    if on_test_done:
        await on_test_done(
            ExecutionProgress(
                case=case,
                verdict=verdict,
                index=case_idx,
                done=state.done_count,
                total=len(state.cases),
            )
        )


async def _execute_suite_cases(
    suite_states: list[_SuiteState | None],
    results_by_index: list[SuiteResult | None],
    *,
    max_concurrent_tests: int,
    on_test_start: OnTestStart,
    on_test_done: OnTestDone,
    on_suite_start: OnSuiteStart,
    on_suite_error: OnSuiteError,
) -> None:
    sem = asyncio.Semaphore(max(1, max_concurrent_tests))

    tasks: list[asyncio.Task[Any]] = []
    for idx, state in enumerate(suite_states):
        if state is None:
            continue
        if on_suite_start:
            ctx = SuiteCallbackContext(
                suite=state.suite, cases=state.cases, executor=state.executor
            )
            try:
                await on_suite_start(ctx)
            except Exception as exc:
                if on_suite_error:
                    await on_suite_error(ctx, exc)
                await state.http_client.close_async()
                results_by_index[idx] = _build_error_result(state.suite, exc)
                suite_states[idx] = None
                continue
        for case_idx in range(len(state.cases)):
            task = asyncio.create_task(
                _run_case(
                    state,
                    case_idx,
                    sem=sem,
                    on_test_start=on_test_start,
                    on_test_done=on_test_done,
                )
            )
            tasks.append(task)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def _cleanup_suite_states(suite_states: list[_SuiteState | None]) -> None:
    for state in suite_states:
        if state is None:
            continue
        await state.http_client.close_async()


async def _collect_suite_results(
    suite_states: list[_SuiteState | None],
    results_by_index: list[SuiteResult | None],
    *,
    on_suite_done: OnSuiteDone,
) -> list[SuiteResult]:
    for idx, state in enumerate(suite_states):
        if state is None:
            continue
        suite = state.suite
        verdicts: list[TestVerdict] = [
            v if v is not None else _cancelled_verdict(state.cases[i])
            for i, v in enumerate(state.verdicts)
        ]
        started_at = state.started_at or datetime.now(UTC).isoformat()
        finished_at = state.finished_at or started_at
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
        results_by_index[idx] = result

        if on_suite_done:
            await on_suite_done(
                SuiteCallbackContext(suite=suite, cases=state.cases, executor=state.executor),
                result,
            )

    if any(result is None for result in results_by_index):
        missing = [idx for idx, result in enumerate(results_by_index) if result is None]
        raise RuntimeError(f"Missing suite results for indices: {missing}")

    return [result for result in results_by_index if result is not None]


class Executor:
    """Concurrent test execution engine.

    Usage::

        executor = Executor(client, max_concurrent=5)
        verdicts = await executor.run_all(cases)
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
        self._inflight_tasks: list[asyncio.Task[Any]] = []
        self._done_count = 0

    # ── Public API ────────────────────────────────────────

    async def run_one(self, case: ExecutableCase) -> TestVerdict:
        """Execute a single test case. No concurrency control.

        Used directly for retry.
        """
        try:
            return await self._runner.run_async(case)
        except asyncio.CancelledError:
            return _cancelled_verdict(case)
        except Exception as e:
            return error_verdict(case, message=str(e), code="REQUEST_ERROR")


# ── High-level multi-suite API ────────────────────────────


async def run_suites(
    registry: Registry,
    config: AppConfig,
    *,
    suite_ids: list[str] | None = None,
    selected_tests: dict[str, set[str]] | None = None,
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
        max_concurrent_tests: Global test concurrency across all suites.
        on_test_start: Callback fired before each test begins.
        on_test_done: Callback fired after each test completes.
        on_suite_start: Callback fired before a suite begins (receives SuiteCallbackContext).
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

    # ── Flattened execution: single global concurrency gate ───────────

    suite_states, results_by_index = await _prepare_suite_states(
        suites,
        selected_tests=selected_tests,
        config=config,
        factory=factory,
        max_concurrent_tests=max_concurrent_tests,
        on_suite_error=on_suite_error,
    )

    try:
        await _execute_suite_cases(
            suite_states,
            results_by_index,
            max_concurrent_tests=max_concurrent_tests,
            on_test_start=on_test_start,
            on_test_done=on_test_done,
            on_suite_start=on_suite_start,
            on_suite_error=on_suite_error,
        )
    finally:
        await _cleanup_suite_states(suite_states)

    return await _collect_suite_results(
        suite_states,
        results_by_index,
        on_suite_done=on_suite_done,
    )


async def run_suites_with_cancellation(
    task_id: str,
    registry: Registry,
    config: AppConfig,
    *,
    suite_ids: list[str] | None = None,
    selected_tests: dict[str, set[str]] | None = None,
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

    Accepts all keyword arguments of :func:`run_suites`.
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
