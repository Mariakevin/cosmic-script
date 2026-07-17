"""Tests for SSE streaming support."""

from __future__ import annotations

import pytest
from cosmic_script.web.streaming import ProgressEvent, ProgressTracker


class TestProgressEvent:
    def test_creation(self):
        e = ProgressEvent(event_type="chapter_start", chapter=1, total_chapters=5)
        assert e.event_type == "chapter_start"
        assert e.chapter == 1

    def test_to_sse_format(self):
        e = ProgressEvent(
            event_type="chapter_complete", chapter=2, total_chapters=5, message="Done"
        )
        sse = e.to_sse()
        assert "event: chapter_complete" in sse
        assert '"chapter": 2' in sse
        assert '"total_chapters": 5' in sse
        assert '"message": "Done"' in sse
        assert sse.endswith("\n\n")

    def test_to_sse_includes_extra_data(self):
        e = ProgressEvent(event_type="chapter_complete", data={"model": "gemini/2.5-flash"})
        sse = e.to_sse()
        assert '"model": "gemini/2.5-flash"' in sse


class TestProgressTracker:
    def test_emit_and_get(self):
        t = ProgressTracker()
        t.emit(ProgressEvent(event_type="chapter_start", chapter=1))
        events = t.get_events()
        assert len(events) == 1
        assert events[0].event_type == "chapter_start"

    def test_multiple_events(self):
        t = ProgressTracker()
        t.emit(ProgressEvent(event_type="chapter_start", chapter=1))
        t.emit(ProgressEvent(event_type="chapter_complete", chapter=1))
        t.emit(ProgressEvent(event_type="conversion_complete"))
        assert len(t.get_events()) == 3

    @pytest.mark.asyncio
    async def test_stream_returns_sse_strings(self):
        t = ProgressTracker()
        t.emit(ProgressEvent(event_type="chapter_start", chapter=1))
        t.emit(ProgressEvent(event_type="conversion_complete"))
        sses = await t.stream()
        assert len(sses) == 2
        assert "event: chapter_start" in sses[0]
        assert "event: conversion_complete" in sses[1]
