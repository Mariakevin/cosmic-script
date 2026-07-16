"""Tests for the Chapter model."""

import pytest
from cosmic_script.models import Chapter


class TestChapterModel:
    """Chapter model creation and invariants."""

    def test_chapter_with_all_fields(self):
        """Happy path: create Chapter with all fields."""
        chapter = Chapter(number=1, title="The Beginning", text="Story text here.")
        assert chapter.number == 1
        assert chapter.title == "The Beginning"
        assert chapter.text == "Story text here."

    def test_chapter_without_title(self):
        """Happy path: create Chapter without optional title."""
        chapter = Chapter(number=2, text="Some text.")
        assert chapter.number == 2
        assert chapter.title is None
        assert chapter.text == "Some text."

    def test_chapter_default_title_is_none(self):
        """Invariant: title field defaults to None."""
        chapter = Chapter(number=5, text="Text.")
        assert chapter.title is None

    def test_chapter_number_must_be_int(self):
        """Invariant: number must be an integer."""
        chapter = Chapter(number=10, text="X")
        assert isinstance(chapter.number, int)

    def test_chapter_text_must_be_str(self):
        """Invariant: text must be a string."""
        chapter = Chapter(number=1, text="Hello")
        assert isinstance(chapter.text, str)

    def test_chapter_negative_number(self):
        """Boundary: Chapter can hold any int including negatives (no validation in model)."""
        chapter = Chapter(number=-1, text="Negative")
        assert chapter.number == -1

    def test_chapter_empty_text(self):
        """Boundary: Chapter allows empty text."""
        chapter = Chapter(number=0, text="")
        assert chapter.text == ""

    def test_chapter_repr(self):
        """Verify repr shows expected info."""
        c = Chapter(number=1, title="Intro", text="Body")
        r = repr(c)
        assert "number=1" in r
        assert "title='Intro'" in r

    def test_chapter_equality_by_value(self):
        """Invariant: two identical chapters are equal (pydantic default)."""
        a = Chapter(number=1, text="Same")
        b = Chapter(number=1, text="Same")
        assert a == b
