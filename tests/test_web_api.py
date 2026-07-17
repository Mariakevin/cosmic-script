"""Tests for FastAPI web endpoints."""

import io
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from cosmic_script.web.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper: create a sample .txt file in a temp dir
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_txt_path() -> str:
    """Create a temporary .txt file with sample story content."""
    content = (
        "Chapter 1: The Beginning\n\n"
        "Sarah walked into the room. John was waiting.\n\n"
        '"Hello," said Sarah.\n\n'
        'John replied, "Good to see you."'
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# POST /api/documents/upload
# ---------------------------------------------------------------------------


class TestUploadDocument:
    """Coverage: happy-path, boundary, error-path, input-variation."""

    def test_upload_txt_file(self, sample_txt_path: str) -> None:
        """Happy-path: upload a .txt file returns metadata."""
        with open(sample_txt_path, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("story.txt", f, "text/plain")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "story.txt"
        assert data["word_count"] > 0
        assert data["char_count"] > 0
        assert "Sarah" in data["text"]

    def test_upload_empty_file(self) -> None:
        """Boundary: empty file still returns metadata."""
        empty = io.BytesIO(b"")
        response = client.post(
            "/api/upload",
            files={"file": ("empty.txt", empty, "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["word_count"] == 0
        assert data["char_count"] == 0

    def test_upload_unsupported_extension(self) -> None:
        """Error-path: .exe file returns 422."""
        response = client.post(
            "/api/upload",
            files={"file": ("malware.exe", io.BytesIO(b"x"), "application/octet-stream")},
        )
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_upload_no_file_returns_422(self) -> None:
        """Error-path: missing file returns 422."""
        response = client.post("/api/upload")
        assert response.status_code == 422

    def test_upload_response_schema(self, sample_txt_path: str) -> None:
        """Invariant: response has expected schema fields."""
        with open(sample_txt_path, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("story.txt", f, "text/plain")},
            )
        assert response.status_code == 200
        data = response.json()
        assert "filename" in data
        assert "text" in data
        assert "word_count" in data
        assert "char_count" in data
        assert "char_count_no_spaces" in data


# ---------------------------------------------------------------------------
# POST /api/chapters
# ---------------------------------------------------------------------------


class TestExtractChapters:
    """Coverage: happy-path, boundary, error-path."""

    def test_extract_chapters_happy(self) -> None:
        """Happy-path: text with chapter markers returns chapters."""
        text = "Chapter 1: First\n\nSome text here.\n\nChapter 2: Second\n\nMore text here."
        response = client.post("/api/chapters", json={"text": text})
        assert response.status_code == 200
        data = response.json()
        assert len(data["chapters"]) == 2
        assert data["chapters"][0]["number"] == 1
        assert data["chapters"][1]["title"] == "Second"

    def test_extract_chapters_empty_text(self) -> None:
        """Boundary: empty text returns empty list."""
        response = client.post("/api/chapters", json={"text": ""})
        assert response.status_code == 200
        assert response.json() == {"chapters": []}

    def test_extract_chapters_no_markers(self) -> None:
        """Input-variation: text without chapter markers falls back."""
        text = "Just a single block of text without any chapter headings."
        response = client.post("/api/chapters", json={"text": text})
        assert response.status_code == 200
        data = response.json()
        # Should have at least one chapter (fallback)
        assert len(data["chapters"]) >= 1

    def test_extract_chapters_response_schema(self) -> None:
        """Invariant: response contains chapters list with expected fields."""
        response = client.post(
            "/api/chapters",
            json={"text": "Chapter 1: Test\n\nContent."},
        )
        assert response.status_code == 200
        data = response.json()
        assert "chapters" in data
        for ch in data["chapters"]:
            assert "number" in ch
            assert "text_preview" in ch


# ---------------------------------------------------------------------------
# POST /api/convert
# ---------------------------------------------------------------------------


class TestConvert:
    """Coverage: happy-path (demo), boundary, error-path."""

    def test_convert_demo_mode(self) -> None:
        """Happy-path: demo mode returns mock screenplay."""
        response = client.post(
            "/api/convert",
            json={"text": "Sarah walked in.", "model": "demo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "scenes" in data
        assert "elements" in data
        assert data["title"] is not None

    def test_convert_empty_text_returns_400(self) -> None:
        """Error-path: empty text returns 400."""
        response = client.post(
            "/api/convert",
            json={"text": "", "model": "demo"},
        )
        assert response.status_code == 400

    def test_convert_whitespace_only_returns_400(self) -> None:
        """Boundary: whitespace-only text returns 400."""
        response = client.post(
            "/api/convert",
            json={"text": "   \n  ", "model": "demo"},
        )
        assert response.status_code == 400

    def test_convert_demo_response_schema(self) -> None:
        """Invariant: demo response matches ScreenplayResponse."""
        response = client.post(
            "/api/convert",
            json={"text": "Hello world.", "model": "demo"},
        )
        data = response.json()
        assert "title" in data
        assert "author" in data
        assert "scenes" in data
        assert "elements" in data
        if data["elements"]:
            for elem in data["elements"]:
                assert "type" in elem
                assert "text" in elem

    def test_convert_with_title_and_author(self) -> None:
        """Input-variation: title and author are passed through."""
        response = client.post(
            "/api/convert",
            json={
                "text": "Once upon a time.",
                "model": "demo",
                "title": "My Story",
                "author": "Writer",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My Story"
        assert data["author"] == "Writer"


# ---------------------------------------------------------------------------
# POST /api/convert/stream
# ---------------------------------------------------------------------------


class TestConvertStream:
    """Coverage: happy-path (demo), boundary, error-path, SSE format."""

    def test_convert_stream_demo_mode(self) -> None:
        """Happy-path: demo mode returns SSE events."""
        response = client.post(
            "/api/convert/stream",
            json={"text": "Sarah walked in.", "model": "demo"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        text = response.text
        assert "event: chapter_start" in text
        assert "event: chapter_complete" in text
        assert "event: conversion_complete" in text

    def test_convert_stream_empty_text_returns_400(self) -> None:
        """Error-path: empty text returns 400."""
        response = client.post(
            "/api/convert/stream",
            json={"text": "", "model": "demo"},
        )
        assert response.status_code == 400

    def test_convert_stream_whitespace_only_returns_400(self) -> None:
        """Boundary: whitespace-only text returns 400."""
        response = client.post(
            "/api/convert/stream",
            json={"text": "   \n  ", "model": "demo"},
        )
        assert response.status_code == 400

    def test_convert_stream_sse_format(self) -> None:
        """Invariant: SSE events have correct format with data payload."""
        response = client.post(
            "/api/convert/stream",
            json={"text": "Hello world.", "model": "demo"},
        )
        text = response.text
        # Check SSE format: "event: X\ndata: {...}\n\n"
        lines = text.split("\n\n")
        for block in lines:
            if not block.strip():
                continue
            assert "event:" in block
            assert "data:" in block
            # Extract and parse JSON from data line
            data_line = [l for l in block.split("\n") if l.startswith("data:")][0]
            json_str = data_line[len("data: ") :]
            import json

            payload = json.loads(json_str)
            assert "type" in payload
            assert "chapter" in payload
            assert "total_chapters" in payload
            assert "message" in payload

    def test_convert_stream_with_title_and_author(self) -> None:
        """Input-variation: title and author are passed through."""
        response = client.post(
            "/api/convert/stream",
            json={
                "text": "Once upon a time.",
                "model": "demo",
                "title": "My Story",
                "author": "Writer",
            },
        )
        assert response.status_code == 200
        text = response.text
        assert '"message": "Converting chapter 1/1"' in text

    def test_convert_stream_error_event(self) -> None:
        """Error-path: conversion failure emits error event."""
        response = client.post(
            "/api/convert/stream",
            json={"text": "Test.", "model": "nonexistent-model-xyz"},
        )
        # Should still return SSE with error event (or fallback to demo)
        assert response.status_code == 200
        assert "event:" in response.text


# ---------------------------------------------------------------------------
# GET /api/export
# ---------------------------------------------------------------------------


class TestExportFountain:
    """Coverage: happy-path, error-path."""

    def test_export_fountain(self) -> None:
        """Happy-path: export to fountain format."""
        payload = {
            "screenplay": {
                "title": "Test",
                "author": "Me",
                "scenes": [
                    {"heading": "INT. HOUSE - DAY", "content": "John enters.\n\nJOHN\nHello."}
                ],
                "elements": [
                    {"type": "scene_heading", "text": "INT. HOUSE - DAY"},
                    {"type": "action", "text": "John enters."},
                    {"type": "character", "text": "JOHN"},
                    {"type": "dialogue", "text": "Hello."},
                ],
            },
            "format": "fountain",
        }
        response = client.post("/api/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert data["format"] == "fountain"
        assert "INT. HOUSE - DAY" in data["content"]

    def test_export_unsupported_format(self) -> None:
        """Error-path: unsupported format returns 422."""
        payload = {
            "screenplay": {"title": "Test", "elements": []},
            "format": "docx",
        }
        response = client.post("/api/export", json=payload)
        assert response.status_code == 422

    def test_export_empty_screenplay(self) -> None:
        """Boundary: empty screenplay exports gracefully."""
        payload = {
            "screenplay": {"title": "", "elements": []},
            "format": "fountain",
        }
        response = client.post("/api/export", json=payload)
        assert response.status_code == 200
        assert response.json()["content"] == ""


# ---------------------------------------------------------------------------
# POST /api/coverage
# ---------------------------------------------------------------------------


class TestCoverage:
    """Coverage: happy-path (no LLM), error-path."""

    def test_coverage_empty_text_returns_400(self) -> None:
        """Error-path: empty text returns 400."""
        response = client.post("/api/coverage", json={"text": ""})
        assert response.status_code == 400

    def test_coverage_demo_fallback(self) -> None:
        """Happy-path: coverage falls back to demo on API error."""
        # Use an invalid model to force fallback
        response = client.post(
            "/api/coverage",
            json={"text": "A story about a hero."},
            params={"model": "bogus-model-that-fails"},
        )
        # Should fall back to demo without crashing
        assert response.status_code == 200
        data = response.json()
        assert "logline" in data
        assert "synopsis" in data
        assert "strengths" in data
        assert "weaknesses" in data
        assert "rating" in data

    def test_coverage_response_schema(self) -> None:
        """Invariant: coverage response has expected schema."""
        response = client.post(
            "/api/coverage",
            json={"text": "Hero saves the day."},
            params={"model": "bogus"},
        )
        assert response.status_code == 200
        data = response.json()
        for key in (
            "logline",
            "synopsis",
            "strengths",
            "weaknesses",
            "rating",
            "recommendation",
            "genre",
            "target_audience",
            "model_used",
        ):
            assert key in data


# ---------------------------------------------------------------------------
# POST /api/logline
# ---------------------------------------------------------------------------


class TestLogline:
    """Coverage: happy-path (no LLM), error-path."""

    def test_logline_empty_text_returns_400(self) -> None:
        """Error-path: empty text returns 400."""
        response = client.post("/api/logline", json={"text": ""})
        assert response.status_code == 400

    def test_logline_demo_fallback(self) -> None:
        """Happy-path: logline falls back to demo on API error."""
        response = client.post(
            "/api/logline",
            json={"text": "A detective solves a mystery."},
            params={"model": "bogus-model"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "logline" in data
        assert len(data["logline"]) > 10

    def test_logline_response_format(self) -> None:
        """Invariant: logline response is a string under a 'logline' key."""
        response = client.post(
            "/api/logline",
            json={"text": "Story text here."},
            params={"model": "bogus"},
        )
        data = response.json()
        assert isinstance(data["logline"], str)


# ---------------------------------------------------------------------------
# GET /api/estimate
# ---------------------------------------------------------------------------


class TestEstimate:
    """Coverage: happy-path, boundary."""

    def test_estimate_with_text(self) -> None:
        """Happy-path: text returns page estimate."""
        response = client.get(
            "/api/estimate", params={"text": "INT. HOUSE - DAY\n\nJohn enters.\n\nJOHN\nHello."}
        )
        assert response.status_code == 200
        data = response.json()
        assert "estimated_pages" in data
        assert "total_lines" in data
        assert "breakdown" in data
        assert "confidence" in data
        assert data["estimated_pages"] > 0

    def test_estimate_empty_text(self) -> None:
        """Boundary: empty text returns zero estimate."""
        response = client.get("/api/estimate", params={"text": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["estimated_pages"] == 0.0
        assert data["total_lines"] == 0

    def test_estimate_no_text_param(self) -> None:
        """Boundary: missing text param defaults to empty string."""
        response = client.get("/api/estimate")
        assert response.status_code == 200
        data = response.json()
        assert data["estimated_pages"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/genres
# ---------------------------------------------------------------------------


class TestGenres:
    """Coverage: happy-path."""

    def test_list_genres(self) -> None:
        """Happy-path: returns list of genres with name and description."""
        response = client.get("/api/genres")
        assert response.status_code == 200
        data = response.json()
        assert "genres" in data
        assert len(data["genres"]) > 0
        for genre in data["genres"]:
            assert "name" in genre
            assert "description" in genre

    def test_genres_include_known_genre(self) -> None:
        """Invariant: known genres like 'action' and 'drama' are present."""
        response = client.get("/api/genres")
        data = response.json()
        names = [g["name"] for g in data["genres"]]
        assert "action" in names
        assert "drama" in names
        assert "comedy" in names
        assert "horror" in names

    def test_genres_response_is_stable(self) -> None:
        """Invariant: multiple calls return the same list."""
        r1 = client.get("/api/genres").json()
        r2 = client.get("/api/genres").json()
        assert r1 == r2
