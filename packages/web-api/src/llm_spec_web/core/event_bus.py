"""In-memory event bus for real-time progress updates."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any


class EventBus:
    """In-memory event bus for run progress updates.

    This class provides a lightweight pub/sub mechanism for real-time
    progress updates without frequent database writes.

    Usage:
        # Push event (called by RunService)
        await event_bus.push(run_id, "test_finished", {"status": "pass"})

        # Subscribe to events (called by SSE endpoint)
        async for event in event_bus.subscribe(run_id):
            yield event
    """

    def __init__(self) -> None:
        # Each run_id has its own queue
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        # Track active runs
        self._active_runs: set[str] = set()

    def get_queue(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Get or create queue for a run."""
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]

    def is_active(self, run_id: str) -> bool:
        """Check if a run is still active."""
        return run_id in self._active_runs

    def start_run(self, run_id: str) -> None:
        """Mark a run as active."""
        self._active_runs.add(run_id)

    def end_run(self, run_id: str) -> None:
        """Mark a run as finished."""
        self._active_runs.discard(run_id)

    def push(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Push an event to the queue (sync version for non-async context).

        Args:
            run_id: Run job ID.
            event_type: Event type (e.g., "test_finished").
            payload: Event payload.
        """
        queue = self.get_queue(run_id)
        event = {
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(UTC).isoformat(),
        }
        # Use put_nowait to avoid blocking
        # Queue is full, drop the event (shouldn't happen with unbounded queue)
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(event)

    async def push_async(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Push an event to the queue (async version).

        Args:
            run_id: Run job ID.
            event_type: Event type (e.g., "test_finished").
            payload: Event payload.
        """
        queue = self.get_queue(run_id)
        event = {
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(UTC).isoformat(),
        }
        await queue.put(event)

    async def subscribe(
        self,
        run_id: str,
        timeout: float = 30.0,
    ):
        """Subscribe to events for a run.

        This is an async generator that yields events as they are pushed.

        Args:
            run_id: Run job ID.
            timeout: Max seconds to wait for each event.

        Yields:
            Event dictionaries with event_type, payload, created_at.
        """
        queue = self.get_queue(run_id)

        while True:
            try:
                # Wait for new event
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                yield event

                # Check if this is a terminal event
                if event["event_type"] in ("run_finished", "run_failed", "run_cancelled"):
                    break

            except TimeoutError:
                # Send heartbeat to keep connection alive
                yield {
                    "event_type": "heartbeat",
                    "payload": {},
                    "created_at": datetime.now(UTC).isoformat(),
                }

    def cleanup(self, run_id: str) -> None:
        """Clean up resources for a finished run.

        Args:
            run_id: Run job ID.
        """
        self._active_runs.discard(run_id)
        if run_id in self._queues:
            del self._queues[run_id]


# Global event bus instance
event_bus = EventBus()
