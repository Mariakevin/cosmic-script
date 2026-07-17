"""SSE streaming support for real-time conversion progress."""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgressEvent:
    event_type: str  # "chapter_start", "chapter_complete", "conversion_complete"
    chapter: int = 0
    total_chapters: int = 0
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        payload = json.dumps(
            {
                "type": self.event_type,
                "chapter": self.chapter,
                "total_chapters": self.total_chapters,
                "message": self.message,
                **self.data,
            }
        )
        return f"event: {self.event_type}\ndata: {payload}\n\n"


class ProgressTracker:
    """Thread-safe progress tracker for conversion."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
        self._thread_events: list[ProgressEvent] = []
        self._lock = threading.Lock()

    def emit(self, event: ProgressEvent) -> None:
        with self._lock:
            self._thread_events.append(event)

    async def stream(self) -> list[str]:
        """Return all accumulated events as SSE strings."""
        with self._lock:
            events = list(self._thread_events)
        return [e.to_sse() for e in events]

    def get_events(self) -> list[ProgressEvent]:
        with self._lock:
            return list(self._thread_events)
