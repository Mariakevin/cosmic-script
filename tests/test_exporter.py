"""Tests for the Fountain export module."""

import os
import tempfile

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.export.exporter import export_screenplay
from cosmic_script.export.fountain import generate_fountain


class TestExportScreenplay:
    """Test suite for export_screenplay()."""

    def test_export_to_fountain(self, tmp_path):
        """Export to .fountain format saves valid Fountain text."""
        screenplay = Screenplay(
            title="Test Movie",
            author="Tester",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. ROOM - DAY"
                ),
                ScreenplayElement(element_type="action", text="A quiet room."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
            ],
        )

        output_path = os.path.join(tmp_path, "output.fountain")
        result_path = export_screenplay(screenplay, output_path, fmt="fountain")

        assert os.path.exists(output_path)
        assert result_path == output_path

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Title: Test Movie" in content
        assert "Author: Tester" in content
        assert "INT. ROOM - DAY" in content
        assert "JOHN" in content
        assert "Hello." in content

    def test_export_to_txt(self, tmp_path):
        """Export to .txt format saves plain text rendering."""
        screenplay = Screenplay(
            title="Test Movie",
            author="Tester",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. ROOM - DAY"
                ),
                ScreenplayElement(element_type="action", text="A quiet room."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
            ],
        )

        output_path = os.path.join(tmp_path, "output.txt")
        result_path = export_screenplay(screenplay, output_path, fmt="txt")

        assert os.path.exists(output_path)
        assert result_path == output_path

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Plain text should be readable screenplay format
        assert "INT. ROOM - DAY" in content
        assert "JOHN" in content
        assert "Hello." in content

    def test_export_default_format(self, tmp_path):
        """Default format is fountain when not specified."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. ROOM - DAY"
                ),
            ],
        )

        output_path = os.path.join(tmp_path, "output.fountain")
        export_screenplay(screenplay, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "INT. ROOM - DAY" in content

    def test_export_validates_before_save(self, tmp_path):
        """Exporter validates output and auto-fixes issues."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="character", text="john"),
                ScreenplayElement(element_type="dialogue", text="hi"),
            ],
        )

        output_path = os.path.join(tmp_path, "output.fountain")
        export_screenplay(screenplay, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Character should be uppercased through auto-fix
        assert "JOHN" in content

    def test_export_to_existing_directory(self, tmp_path):
        """Export to a non-existent directory creates it."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="EXT. WORLD - DAY"
                ),
            ],
        )

        output_path = os.path.join(tmp_path, "subdir", "nested", "output.fountain")
        result_path = export_screenplay(screenplay, output_path)

        assert os.path.exists(output_path)

    def test_export_empty_screenplay(self, tmp_path):
        """Empty screenplay exports as empty file."""
        screenplay = Screenplay()
        output_path = os.path.join(tmp_path, "empty.fountain")

        result_path = export_screenplay(screenplay, output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert content == ""

    def test_export_invalid_format_raises(self, tmp_path):
        """Unsupported format raises ValueError."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Hello."),
            ],
        )

        output_path = os.path.join(tmp_path, "output.pdf")

        with pytest.raises(ValueError, match="Unsupported format"):
            export_screenplay(screenplay, output_path, fmt="pdf")

    def test_fountain_format_string_return(self, tmp_path):
        """Function returns the valid Fountain text as a string when expected."""
        screenplay = Screenplay(
            title="Return Test",
            elements=[
                ScreenplayElement(
                    element_type="scene_heading", text="INT. TEST - DAY"
                ),
            ],
        )

        # The function should also return the full text when called standalone
        text = generate_fountain(screenplay)
        assert isinstance(text, str)
        assert "Title: Return Test" in text
        assert "INT. TEST - DAY" in text
