"""In-memory execution registry for task/run/case asyncio handles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RunHandle:
    run_id: str
    case_tasks: dict[str, asyncio.Task[object]] = field(default_factory=dict)


@dataclass
class TaskHandle:
    task_id: str
    loop: asyncio.AbstractEventLoop
    root_task: asyncio.Task[object]
    runs: dict[str, RunHandle] = field(default_factory=dict)


class TaskExecutionRegistry:
    """Global in-memory registry for active task execution handles."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskHandle] = {}
        self._lock = Lock()

    def register_task(
        self, task_id: str, loop: asyncio.AbstractEventLoop, root_task: asyncio.Task[object]
    ) -> None:
        with self._lock:
            self._tasks[task_id] = TaskHandle(task_id=task_id, loop=loop, root_task=root_task)

    def unregister_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def register_run(self, task_id: str, run_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.runs.setdefault(run_id, RunHandle(run_id=run_id))

    def register_case_task(
        self, task_id: str, run_id: str, run_case_id: str | None, case_task: asyncio.Task[object]
    ) -> None:
        if not run_case_id:
            return
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            run = task.runs.setdefault(run_id, RunHandle(run_id=run_id))
            run.case_tasks[run_case_id] = case_task

    def cancel_task(self, task_id: str) -> bool:
        """Cancel one active task execution tree by task ID."""
        with self._lock:
            handle = self._tasks.get(task_id)
        if handle is None:
            return False

        def _cancel_all() -> None:
            for run in handle.runs.values():
                for case_task in run.case_tasks.values():
                    case_task.cancel()
            handle.root_task.cancel()

        handle.loop.call_soon_threadsafe(_cancel_all)
        return True


execution_registry = TaskExecutionRegistry()
