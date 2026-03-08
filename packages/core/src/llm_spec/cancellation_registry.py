"""Task execution cancellation registry shared by runtime adapters.

This module provides a thread-safe registry that allows one thread to
cancel asyncio tasks running in another thread's event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class TaskHandle:
    task_id: str
    loop: asyncio.AbstractEventLoop
    root_task: asyncio.Task[Any]


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
