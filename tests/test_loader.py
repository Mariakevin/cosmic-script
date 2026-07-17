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
        # We'll create a temp file with .xyz (truly unsupported)
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError, match=r"unsupported.*extension|Unsupported"):
                load_document(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_unsupported_extension_message(self):
        """Error path: unsupported extension message includes extension."""
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError) as exc:
                load_document(tmp_path)
            assert ".xyz" in str(exc.value)
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


class TestEncodingDetection:
    """Tests for encoding detection in _load_txt."""

    def test_utf8_file_loads_correctly(self):
        """UTF-8 encoded file loads correctly."""
        content = "Hello, world! \u00e9\u00e8\u00ea"
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="wb", delete=False) as f:
            f.write(content.encode("utf-8"))
            tmp_path = f.name
        try:
            loaded = load_document(tmp_path)
            assert loaded == content
        finally:
            os.unlink(tmp_path)

    def test_latin1_file_fallback(self):
        """Latin-1 encoded file loads via chardet or fallback."""
        # Latin-1 characters (not valid UTF-8)
        content_bytes = b"Caf\xe9 is great"
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="wb", delete=False) as f:
            f.write(content_bytes)
            tmp_path = f.name
        try:
            loaded = load_document(tmp_path)
            # Should be decoded (maybe via chardet or latin-1 fallback)
            assert isinstance(loaded, str)
            assert len(loaded) > 0
        finally:
            os.unlink(tmp_path)

    def test_utf8_bom_file_loads(self):
        """UTF-8 with BOM loads correctly."""
        content = "BOM file content"
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="wb", delete=False) as f:
            f.write(b"\xef\xbb\xbf" + content.encode("utf-8"))
            tmp_path = f.name
        try:
            loaded = load_document(tmp_path)
            assert loaded == content
        finally:
            os.unlink(tmp_path)

    def test_binary_file_fallback(self):
        """Binary file (not text) loads without crash (fallback)."""
        # Random bytes that may not be valid any encoding
        content_bytes = b"\x00\x01\x02\x03\xff\xfe"
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="wb", delete=False) as f:
            f.write(content_bytes)
            tmp_path = f.name
        try:
            loaded = load_document(tmp_path)
            # Should not raise, maybe returns decoded string with replacement chars
            assert isinstance(loaded, str)
        finally:
            os.unlink(tmp_path)
