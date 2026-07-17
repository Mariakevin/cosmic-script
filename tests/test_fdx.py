"""Tests for FDX import/export support.

Covers:
- FDX export via screenplay-tools FDX.Writer
- FDX import via screenplay-tools FDX.Parser
- Fountain -> FDX -> Fountain roundtrip
- Error handling for malformed FDX
"""

import os
import tempfile

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement, Scene
from cosmic_script.export.exporter import export_screenplay, SUPPORTED_FORMATS
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.validator import FountainValidator


# ---------------------------------------------------------------------------
# FDX Export
# ---------------------------------------------------------------------------


class TestFDXExport:
    """Tests for FDX format export."""

    def test_fdx_in_supported_formats(self) -> None:
        """'fdx' should be in SUPPORTED_FORMATS."""
        assert "fdx" in SUPPORTED_FORMATS
        assert SUPPORTED_FORMATS["fdx"] == ".fdx"

    def test_export_fdx_creates_file(self) -> None:
        """Exporting to fdx creates a valid XML file."""
        screenplay = Screenplay(
            title="FDX Test",
            author="Tester",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type="action", text="John enters the room."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello world."),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test.fdx")
            result = export_screenplay(screenplay, output, fmt="fdx")
            assert os.path.exists(result)
            content = open(result, "r", encoding="utf-8").read()
            assert "<FinalDraft" in content
            assert "Scene Heading" in content
            assert "JOHN" in content

    def test_export_fdx_has_title(self) -> None:
        """FDX export preserves screenplay title."""
        screenplay = Screenplay(
            title="My Movie",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - NIGHT"),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "titled.fdx")
            result = export_screenplay(screenplay, output, fmt="fdx")
            content = open(result, "r", encoding="utf-8").read()
            assert "My Movie" in content

    def test_export_fdx_unsupported_format_raises(self) -> None:
        """Exporting with unsupported format raises ValueError."""
        screenplay = Screenplay()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "bad.txt")
            with pytest.raises(ValueError, match="Unsupported format"):
                export_screenplay(screenplay, output, fmt="docx")

    def test_export_fdx_with_multiple_elements(self) -> None:
        """FDX export handles multiple element types correctly."""
        screenplay = Screenplay(
            title="Multi Element",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. KITCHEN - DAY"),
                ScreenplayElement(element_type="action", text="Alice chops vegetables."),
                ScreenplayElement(element_type="character", text="ALICE"),
                ScreenplayElement(element_type="parenthetical", text="whispering"),
                ScreenplayElement(element_type="dialogue", text="I need help."),
                ScreenplayElement(element_type="character", text="BOB"),
                ScreenplayElement(element_type="dialogue", text="Coming!"),
                ScreenplayElement(element_type="transition", text="FADE OUT."),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "multi.fdx")
            result = export_screenplay(screenplay, output, fmt="fdx")
            content = open(result, "r", encoding="utf-8").read()
            assert "Scene Heading" in content
            assert "Action" in content
            assert "Character" in content
            assert "Parenthetical" in content
            assert "Dialogue" in content
            assert "Transition" in content

    def test_export_fdx_empty_screenplay(self) -> None:
        """FDX export of empty screenplay produces minimal valid XML."""
        screenplay = Screenplay()
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "empty.fdx")
            result = export_screenplay(screenplay, output, fmt="fdx")
            content = open(result, "r", encoding="utf-8").read()
            assert "<FinalDraft" in content


# ---------------------------------------------------------------------------
# FDX Import
# ---------------------------------------------------------------------------


class TestFDXImport:
    """Tests for FDX format import."""

    def test_loader_supports_fdx_extension(self) -> None:
        """load_document should accept .fdx files."""
        from cosmic_script.ingestion.loader import load_document

        # We need a real FDX file to test, so create one
        screenplay = Screenplay(
            title="Import Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="action", text="Action line."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            fdx_path = os.path.join(tmpdir, "import_test.fdx")
            export_screenplay(screenplay, fdx_path, fmt="fdx")
            text = load_document(fdx_path)
            # The imported text should contain the character name
            assert "JOHN" in text

    def test_loader_rejects_unknown_extension(self) -> None:
        """load_document raises ValueError for unknown extension."""
        from cosmic_script.ingestion.loader import load_document

        with tempfile.TemporaryDirectory() as tmpdir:
            fake = os.path.join(tmpdir, "test.xyz")
            with open(fake, "w") as f:
                f.write("test")
            with pytest.raises(ValueError, match="Unsupported file extension"):
                load_document(fake)


# ---------------------------------------------------------------------------
# Roundtrip Tests
# ---------------------------------------------------------------------------


class TestFDXRoundtrip:
    """Fountain -> FDX -> Fountain roundtrip tests."""

    def test_fountain_to_fdx_to_fountain_preserves_elements(self) -> None:
        """Roundtrip should preserve character names and scene headings."""
        original = Screenplay(
            title="Roundtrip",
            author="Tester",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type="action", text="John enters."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello!"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Export to FDX
            fdx_path = os.path.join(tmpdir, "roundtrip.fdx")
            export_screenplay(original, fdx_path, fmt="fdx")

            # Import FDX
            from cosmic_script.ingestion.loader import load_document

            imported_text = load_document(fdx_path)

            # The imported text should contain key elements
            assert "JOHN" in imported_text
            assert "Hello!" in imported_text

    def test_fdx_roundtrip_validates(self) -> None:
        """FDX roundtrip output should pass Fountain validation."""
        original = Screenplay(
            title="Validation Roundtrip",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - NIGHT"),
                ScreenplayElement(element_type="action", text="Lights flicker."),
                ScreenplayElement(element_type="character", text="MARY"),
                ScreenplayElement(element_type="dialogue", text="Is someone there?"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            fdx_path = os.path.join(tmpdir, "validate.fdx")
            export_screenplay(original, fdx_path, fmt="fdx")

            from cosmic_script.ingestion.loader import load_document

            imported_text = load_document(fdx_path)

            # The imported text is Fountain-formatted, validate it
            validator = FountainValidator()
            result = validator.validate(imported_text)
            # No critical errors (E1-E4)
            critical = {e["code"] for e in result["errors"]} & {"E1", "E2", "E3", "E4"}
            assert len(critical) == 0, f"Critical errors in roundtrip: {result['errors']}"


# ---------------------------------------------------------------------------
# FDX Writer Direct Tests
# ---------------------------------------------------------------------------


class TestFDXWriterDirect:
    """Direct tests for the screenplay-tools FDX.Writer."""

    def test_writer_produces_valid_xml(self) -> None:
        """FDX.Writer output should be well-formed XML."""
        from screenplay_tools.fdx.writer import Writer
        from screenplay_tools.screenplay import Script, SceneHeading, Action, Character, Dialogue

        script = Script()
        script.add_element(SceneHeading("INT. OFFICE - DAY"))
        script.add_element(Action("John enters."))
        script.add_element(Character("JOHN"))
        script.add_element(Dialogue("Hello!"))

        writer = Writer()
        xml = writer.write(script)
        assert xml.startswith("<?xml")
        assert "<FinalDraft" in xml
        assert "Scene Heading" in xml
        assert "JOHN" in xml

    def test_writer_handles_parenthetical(self) -> None:
        """FDX.Writer includes parenthetical elements."""
        from screenplay_tools.fdx.writer import Writer
        from screenplay_tools.screenplay import (
            Script,
            SceneHeading,
            Character,
            Dialogue,
            Parenthetical,
        )

        script = Script()
        script.add_element(SceneHeading("INT. ROOM - DAY"))
        script.add_element(Character("JOHN"))
        script.add_element(Parenthetical("whispering"))
        script.add_element(Dialogue("Be quiet."))

        writer = Writer()
        xml = writer.write(script)
        assert "Parenthetical" in xml
        assert "whispering" in xml


# ---------------------------------------------------------------------------
# FDX Parser Direct Tests
# ---------------------------------------------------------------------------


class TestFDXParserDirect:
    """Direct tests for the screenplay-tools FDX.Parser."""

    def test_parser_reads_character_elements(self) -> None:
        """FDX.Parser correctly parses Character paragraphs."""
        from screenplay_tools.fdx.parser import Parser

        fdx_xml = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Template="No" Version="5">
  <Content>
    <Paragraph Type="Scene Heading"><Text>INT. OFFICE - DAY</Text></Paragraph>
    <Paragraph Type="Action"><Text>John enters.</Text></Paragraph>
    <Paragraph Type="Character"><Text>JOHN</Text></Paragraph>
    <Paragraph Type="Dialogue"><Text>Hello world.</Text></Paragraph>
  </Content>
</FinalDraft>"""

        parser = Parser()
        script = parser.parse(fdx_xml)
        assert len(script.elements) >= 3
        char_elements = [e for e in script.elements if e.type.value == "CHARACTER"]
        assert len(char_elements) == 1
        assert char_elements[0].name == "JOHN"

    def test_parser_handles_malformed_xml(self) -> None:
        """FDX.Parser handles invalid XML gracefully."""
        from screenplay_tools.fdx.parser import Parser

        parser = Parser()
        with pytest.raises(ValueError):
            parser.parse("this is not xml at all")

    def test_parser_reads_extension(self) -> None:
        """FDX.Parser correctly parses character extensions."""
        from screenplay_tools.fdx.parser import Parser

        fdx_xml = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Template="No" Version="5">
  <Content>
    <Paragraph Type="Character"><Text>JOHN (V.O.)</Text></Paragraph>
    <Paragraph Type="Dialogue"><Text>Narrating the story.</Text></Paragraph>
  </Content>
</FinalDraft>"""

        parser = Parser()
        script = parser.parse(fdx_xml)
        char = [e for e in script.elements if e.type.value == "CHARACTER"][0]
        assert char.name == "JOHN"
        assert char.extension == "V.O."
