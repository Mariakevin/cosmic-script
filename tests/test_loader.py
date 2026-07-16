"""Tests for the document loader."""

import os
import tempfile
import pytest
from pathlib import Path

from cosmic_script.ingestion.loader import load_document


FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadDocument:
    """load_document() — unified document loading."""

    # ── Happy path ──────────────────────────────────────────

    def test_load_txt_file(self):
        """Happy path: load a .txt file returns its content."""
        path = str(FIXTURES / "sample.txt")
        content = load_document(path)
        assert isinstance(content, str)
        assert len(content) > 0
        assert "plain text file" in content

    def test_load_md_file_strips_markdown(self):
        """Happy path: load .md file returns plain text without markdown syntax."""
        path = str(FIXTURES / "sample.md")
        content = load_document(path)
        assert isinstance(content, str)
        assert len(content) > 0
        # Markdown headers should be plain text (stripped of # markers)
        assert "#" not in content
        # Bold/italic markers stripped
        assert "**" not in content
        assert "*" not in content.replace("torrents", "")  # italic asterisks stripped
        # Content still readable
        assert "dark and stormy" in content
        assert "The Beginning" in content
        assert "Into the Woods" in content

    # ── Input variation ─────────────────────────────────────

    def test_load_empty_txt_file(self):
        """Boundary: empty .txt file returns empty string."""
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("")
            tmp_path = f.name
        try:
            content = load_document(tmp_path)
            assert content == ""
        finally:
            os.unlink(tmp_path)

    def test_load_md_file_no_markdown(self):
        """Input variation: .md file with no markdown syntax loads as-is."""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("Just plain text in a markdown file.")
            tmp_path = f.name
        try:
            content = load_document(tmp_path)
            assert content == "Just plain text in a markdown file."
        finally:
            os.unlink(tmp_path)

    # ── Error path ──────────────────────────────────────────

    def test_file_not_found(self):
        """Error path: non-existent file raises FileNotFoundError."""
        path = str(FIXTURES / "does_not_exist.xyz")
        with pytest.raises(FileNotFoundError):
            load_document(path)

    def test_unsupported_extension(self):
        """Error path: unsupported extension raises ValueError."""
        path = str(FIXTURES / "sample.txt")
        # Point to a file with unsupported extension, must exist for FileNotFoundError not to trigger first
        # We'll create a temp file with .docx
        with tempfile.NamedTemporaryFile(suffix=".docx", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match=r"unsupported.*extension|Unsupported"):
                load_document(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_unsupported_extension_message(self):
        """Error path: unsupported extension message includes extension."""
        with tempfile.NamedTemporaryFile(suffix=".docx", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError) as exc:
                load_document(tmp_path)
            assert ".docx" in str(exc.value)
        finally:
            os.unlink(tmp_path)

    # ── Invariant ───────────────────────────────────────────

    def test_returns_string_always(self):
        """Invariant: load_document always returns a string."""
        path = str(FIXTURES / "sample.txt")
        content = load_document(path)
        assert isinstance(content, str)

    def test_different_extensions_same_content(self):
        """Input variation: .txt and .md of same content differ only by format."""
        # Create .txt and .md with identical plain content
        base_text = "Identical text for both extensions."
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f_txt:
            f_txt.write(base_text)
            txt_path = f_txt.name
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f_md:
            f_md.write(base_text)
            md_path = f_md.name
        try:
            txt_content = load_document(txt_path)
            md_content = load_document(md_path)
            assert txt_content == md_content
        finally:
            os.unlink(txt_path)
            os.unlink(md_path)
