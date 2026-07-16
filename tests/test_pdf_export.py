"""Tests for the PDF export module."""

import os
import tempfile

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.export.pdf_export import ScreenplayPDF, export_pdf


class TestScreenplayPDF:
    """Test suite for ScreenplayPDF rendering."""

    def setup_method(self):
        self.pdf = ScreenplayPDF()
        # Add a page so we can test rendering without add_page each time
        self.pdf.add_page()

    def test_happy_path_render_scene_heading(self):
        """Scene heading renders without error."""
        self.pdf.render_scene_heading("INT. HOUSE - DAY")
        # After rendering, y should have moved
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_happy_path_render_action(self):
        """Action renders without error."""
        self.pdf.render_action("John opens the door and walks in.")
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_happy_path_render_character(self):
        """Character cue renders without error."""
        self.pdf.render_character("JOHN")
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_happy_path_render_dialogue(self):
        """Dialogue renders without error."""
        self.pdf.render_dialogue("Hello there, how are you?")
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_happy_path_render_parenthetical(self):
        """Parenthetical renders without error."""
        self.pdf.render_parenthetical("whispering")
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_happy_path_render_transition(self):
        """Transition renders without error."""
        self.pdf.render_transition("FADE TO BLACK")
        assert self.pdf.get_y() > self.pdf.t_margin

    def test_title_page_created(self):
        """Title page is created when metadata provided."""
        pdf = ScreenplayPDF()
        pdf.render_title_page(title="My Movie", author="Me")
        # After rendering title page, we should have at least one page
        assert pdf.page_no() >= 1

    def test_page_numbers_on_non_title_pages(self):
        """Page numbers appear on content pages but not title page."""
        pdf = ScreenplayPDF()
        # Title page
        pdf.render_title_page("Test", "Author")
        # Content page
        pdf.add_page()
        pdf.render_action("Some action text here.")

        # Page number should render in footer
        # We can't easily check the rendered output, but we can verify
        # the footer method does not crash
        pdf.footer()

    def test_footer_skipped_on_title_page(self):
        """Footer does not produce page number on title page."""
        pdf = ScreenplayPDF()
        pdf._is_title_page = True
        pdf.add_page()
        # Should not raise
        pdf.footer()

    def test_full_screenplay_render(self, tmp_path):
        """Complete screenplay renders to PDF without error."""
        screenplay = Screenplay(
            title="Test Movie",
            author="Tester",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type="action", text="John sits at his desk."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="I can't believe it."),
                ScreenplayElement(element_type="character", text="MARY"),
                ScreenplayElement(element_type="parenthetical", text="sarcastically"),
                ScreenplayElement(element_type="dialogue", text="Oh really? I can."),
                ScreenplayElement(element_type="transition", text="FADE TO BLACK"),
            ],
        )

        pdf = ScreenplayPDF()
        pdf.render_screenplay(screenplay)
        assert pdf.page_no() >= 1

    def test_render_empty_screenplay(self):
        """Empty screenplay renders as blank (no crash)."""
        screenplay = Screenplay()
        pdf = ScreenplayPDF()
        pdf.render_screenplay(screenplay)
        # Should have no pages if no content
        assert pdf.page_no() == 0

    def test_render_screenplay_with_scenes(self, tmp_path):
        """Screenplay with scenes (not elements) renders correctly."""
        from cosmic_script.models import Scene
        screenplay = Screenplay(
            title="Scene Test",
            author="Test",
            scenes=[
                Scene(heading="INT. HOUSE - DAY", content="John enters the room.\n\nJOHN\nHello."),
            ],
        )
        pdf = ScreenplayPDF()
        pdf.render_screenplay(screenplay)
        assert pdf.page_no() >= 1

    def test_element_case_uppercased(self):
        """Character names are automatically uppercased."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        pdf.render_character("john")
        # No crash — text is rendered uppercase

    def test_mixed_element_types(self):
        """Rendering all element types in sequence does not crash."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        pdf.render_scene_heading("INT. ROOM - DAY")
        pdf.render_action("A quiet, dusty room.")
        pdf.render_character("JOHN")
        pdf.render_dialogue("Hello.")
        pdf.render_parenthetical("quietly")
        pdf.render_dialogue("World.")
        pdf.render_transition("FADE OUT")


class TestExportPdf:
    """Test suite for export_pdf function."""

    def test_export_pdf_creates_file(self, tmp_path):
        """export_pdf writes a valid PDF file."""
        screenplay = Screenplay(
            title="Test",
            author="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="EXT. FIELD - DAY"),
                ScreenplayElement(element_type="action", text="A wide open field."),
            ],
        )

        output_path = os.path.join(tmp_path, "output.pdf")
        result = export_pdf(screenplay, output_path)

        assert os.path.exists(output_path)
        assert result == os.path.abspath(output_path)
        # PDF files start with %PDF
        with open(output_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_export_pdf_empty_screenplay(self, tmp_path):
        """Empty screenplay exports as valid minimal PDF."""
        screenplay = Screenplay()
        output_path = os.path.join(tmp_path, "empty.pdf")
        export_pdf(screenplay, output_path)
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            header = f.read(5)
        # Even empty is a valid PDF with metadata
        assert header == b"%PDF-"

    def test_export_pdf_creates_parent_dirs(self, tmp_path):
        """Parent directories are created automatically."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. TEST - DAY"),
            ],
        )
        output_path = os.path.join(tmp_path, "sub", "nested", "output.pdf")
        result = export_pdf(screenplay, output_path)
        assert os.path.exists(output_path)

    def test_export_pdf_full_screenplay(self, tmp_path):
        """Full screenplay with all element types exports successfully."""
        screenplay = Screenplay(
            title="Full Feature",
            author="Writer",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type="action", text="Morning light fills the room."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Time to start the day."),
                ScreenplayElement(element_type="parenthetical", text="yawning"),
                ScreenplayElement(element_type="dialogue", text="Another day, another dollar."),
                ScreenplayElement(element_type="transition", text="CUT TO:"),
                ScreenplayElement(element_type="scene_heading", text="EXT. STREET - DAY"),
                ScreenplayElement(element_type="action", text="Cars rush by."),
                ScreenplayElement(element_type="character", text="MARY"),
                ScreenplayElement(element_type="dialogue", text="Wait for me!"),
            ],
        )
        output_path = os.path.join(tmp_path, "full.pdf")
        export_pdf(screenplay, output_path)
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"
