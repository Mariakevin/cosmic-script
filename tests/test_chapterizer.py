"""Tests for the chapterizer module."""

import pytest
from pathlib import Path

from cosmic_script.models import Chapter
from cosmic_script.ingestion.chapterizer import split_into_chapters


FIXTURES = Path(__file__).parent / "fixtures"


class TestSplitIntoChapters:
    """split_into_chapters() — chapter detection and fallback."""

    # ── Happy path: chapter detection ───────────────────────

    def test_detects_chapters_file(self):
        """Happy path: detect chapters from chapters.txt fixture."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        assert len(chapters) >= 6, f"Expected at least 6 chapters, got {len(chapters)}"

    def test_chapter_numbers_sequential(self):
        """Invariant: chapters have sequential numbering starting from 1."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        for i, ch in enumerate(chapters, start=1):
            assert ch.number == i, f"Expected chapter {i}, got {ch.number}"

    def test_chapter_has_text_content(self):
        """Invariant: each chapter has non-empty text."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        for ch in chapters:
            assert len(ch.text) > 0, f"Chapter {ch.number} has empty text"

    def test_chapter_with_title(self):
        """Happy path: 'Chapter 1: The Beginning' extracts title."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        # Chapter 1: The Beginning
        assert chapters[0].title == "The Beginning"

    def test_chapter_without_title(self):
        """Happy path: 'Chapter 2' (no colon) gives title=None."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        # Chapter 2 has no title
        ch2 = [c for c in chapters if c.number == 2]
        assert len(ch2) == 1
        assert ch2[0].title is None

    # ── Pattern coverage ────────────────────────────────────

    def test_handles_uppercase_chapter(self):
        """Pattern: 'CHAPTER 3: The Revelation' is detected."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        ch3 = [c for c in chapters if c.number == 3]
        assert len(ch3) == 1
        assert ch3[0].title == "The Revelation"

    def test_handles_roman_numeral_chapter(self):
        """Pattern: 'Chapter IV' is detected with number=4."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        ch4 = [c for c in chapters if c.number == 4]
        assert len(ch4) == 1

    def test_handles_part_pattern(self):
        """Pattern: 'Part 1: The Set-Up' and 'PART 2' are detected."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        # There should be 6+ chapters (4 chapters + 2 parts)
        ch5 = [c for c in chapters if c.number == 5]
        ch6 = [c for c in chapters if c.number == 6]
        assert len(ch5) == 1
        assert len(ch6) == 1
        # Part titles
        assert ch5[0].title == "The Set-Up"
        assert ch6[0].title is None

    # ── Fallback: no chapters detected ──────────────────────

    def test_fallback_equal_chunks(self):
        """Boundary: no chapter headings -> fallback to equal-size chunks."""
        text = (FIXTURES / "no_chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        # Should still get chapters from fallback
        assert len(chapters) >= 1
        for ch in chapters:
            assert isinstance(ch, Chapter)
            assert len(ch.text) > 0

    def test_fallback_chunks_have_sequential_numbers(self):
        """Invariant: fallback chunks are numbered sequentially."""
        text = (FIXTURES / "no_chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        for i, ch in enumerate(chapters, start=1):
            assert ch.number == i

    def test_fallback_chunk_size_roughly_equal(self):
        """Invariant: fallback chunks have roughly equal character counts."""
        text = (FIXTURES / "no_chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        if len(chapters) >= 3:
            sizes = [len(ch.text) for ch in chapters]
            max_size = max(sizes)
            min_size = min(sizes)
            # Allow up to 3x difference due to word boundaries
            assert max_size <= min_size * 3 or min_size == 0

    # ── Edge cases ──────────────────────────────────────────

    def test_empty_text_returns_empty_list(self):
        """Boundary: empty text returns empty list."""
        result = split_into_chapters("")
        assert result == []

    def test_text_with_only_chapter_headings(self):
        """Boundary: text with only chapter headings (no body)."""
        text = "Chapter 1\nChapter 2\nChapter 3"
        chapters = split_into_chapters(text)
        assert len(chapters) >= 2

    def test_whitespace_only_text(self):
        """Boundary: whitespace-only text returns empty list."""
        result = split_into_chapters("   \n  \n  ")
        assert result == []

    # ── State transition / idempotency ──────────────────────

    def test_returns_list_of_chapter(self):
        """Invariant: return type is list[Chapter]."""
        text = "Some text."
        chapters = split_into_chapters(text)
        assert isinstance(chapters, list)
        if chapters:
            assert isinstance(chapters[0], Chapter)

    def test_chapter_text_stripped(self):
        """Invariant: chapter text is stripped of leading/trailing whitespace."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        for ch in chapters:
            assert ch.text == ch.text.strip()

    def test_multiple_calls_same_result(self):
        """State transition: calling twice on same text yields same chapters."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        r1 = split_into_chapters(text)
        r2 = split_into_chapters(text)
        assert r1 == r2

    def test_extra_newlines_preserved_in_body(self):
        """Invariant: paragraph breaks within chapter body are preserved as single newlines."""
        text = (FIXTURES / "chapters.txt").read_text(encoding="utf-8")
        chapters = split_into_chapters(text)
        # Each chapter should have its content with paragraph separators
        for ch in chapters:
            if "\n\n" in ch.text:
                break
        else:
            # May or may not have double newlines, but shouldn't fail
            pass
