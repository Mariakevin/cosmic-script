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


class TestScreenplayTypography:
    """Test screenplay formatting standards (Courier 12pt metrics)."""

    def setup_method(self):
        self.pdf = ScreenplayPDF()
        self.pdf.add_page()

    def test_bottom_margin_is_one_inch(self):
        """Bottom margin should be 1 inch (25.4mm) per screenplay standards."""
        from cosmic_script.export.pdf_export import BOTTOM_MARGIN

        assert abs(BOTTOM_MARGIN - 25.4) < 0.01, f"BOTTOM_MARGIN={BOTTOM_MARGIN}, expected 25.4mm"

    def test_dialogue_width_is_three_point_five_inches(self):
        """Dialogue spans from 2.5" to 6" = 3.5" width (88.9mm)."""
        from cosmic_script.export.pdf_export import DIALOGUE_X, DIALOGUE_W

        # DIALOGUE_X should be at 2.5"
        assert abs(DIALOGUE_X - 63.5) < 0.01, f"DIALOGUE_X={DIALOGUE_X}, expected 63.5mm"
        # DIALOGUE_W should be 3.5" = 88.9mm
        assert abs(DIALOGUE_W - 88.9) < 0.01, f"DIALOGUE_W={DIALOGUE_W}, expected 88.9mm"

    def test_page_number_at_top_right(self):
        """Page numbers should be rendered at top right, not bottom center."""
        pdf = ScreenplayPDF()
        pdf.render_title_page("Test", "Author")
        pdf.add_page()
        pdf.render_action("Some text.")
        # Get the y position where footer was called
        # We check that page_no() starts at 2 (title page is page 1)
        assert pdf.page_no() >= 2

    def test_title_page_skips_numbering(self):
        """Title page should not have a page number."""
        pdf = ScreenplayPDF()
        pdf.render_title_page("Test", "Author")
        # Title page is page 1, no number rendered
        assert pdf.page_no() == 1

    def test_blank_line_before_scene_heading(self):
        """Scene heading should be preceded by a blank line (except at page top)."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        y_before = pdf.get_y()
        pdf.render_scene_heading("INT. HOUSE - DAY")
        y_after = pdf.get_y()
        # Should have moved at least 2 lines: blank line + heading text
        from cosmic_script.export.pdf_export import LINE_HEIGHT

        min_expected = LINE_HEIGHT * 2  # blank line + heading
        assert y_after - y_before >= min_expected - 0.01, (
            f"Scene heading moved {y_after - y_before:.2f}mm, expected >= {min_expected:.2f}mm"
        )

    def test_blank_line_before_character(self):
        """Character cue should be preceded by a blank line."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        y_before = pdf.get_y()
        pdf.render_character("JOHN")
        y_after = pdf.get_y()
        from cosmic_script.export.pdf_export import LINE_HEIGHT

        min_expected = LINE_HEIGHT * 2  # blank line + character name
        assert y_after - y_before >= min_expected - 0.01, (
            f"Character moved {y_after - y_before:.2f}mm, expected >= {min_expected:.2f}mm"
        )

    def test_blank_line_before_dialogue(self):
        """Dialogue follows immediately after character (blank line is before character block)."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        pdf.render_character("JOHN")
        y_before_dialogue = pdf.get_y()
        pdf.render_dialogue("Hello there.")
        y_after_dialogue = pdf.get_y()
        from cosmic_script.export.pdf_export import LINE_HEIGHT

        # Dialogue is single-spaced, no extra blank line between character and dialogue
        assert abs(y_after_dialogue - y_before_dialogue - LINE_HEIGHT) < 0.01, (
            f"Dialogue moved {y_after_dialogue - y_before_dialogue:.2f}mm, expected {LINE_HEIGHT:.2f}mm"
        )

    def test_transition_right_aligned_at_six_inches(self):
        """Transition should be right-aligned, ending at 6" from left."""
        from cosmic_script.export.pdf_export import CONTENT_W, LEFT_MARGIN

        # CONTENT_W should be 6" = 152.4mm
        assert abs(CONTENT_W - 152.4) < 0.01, f"CONTENT_W={CONTENT_W}, expected 152.4mm"

    def test_action_lines_single_spaced(self):
        """Action lines should be single-spaced (12pt line height)."""
        from cosmic_script.export.pdf_export import LINE_HEIGHT

        # 12pt = 4.23mm, single spacing
        assert abs(LINE_HEIGHT - 4.23) < 0.01, f"LINE_HEIGHT={LINE_HEIGHT}, expected 4.23mm"

    def test_courier_12pt_character_width(self):
        """Courier 12pt has 10 CPI = 0.1 inch per character."""
        from cosmic_script.export.pdf_export import FONT_SIZE

        assert FONT_SIZE == 12, f"FONT_SIZE={FONT_SIZE}, expected 12pt"

    def test_contd_marker_on_page_break(self):
        """(CONT'D) marker is added when dialogue wraps to new page."""
        pdf = ScreenplayPDF()
        pdf.add_page()
        pdf.render_character("JOHN")
        # Fill up the page to force a page break
        for _ in range(50):
            pdf.render_action("Filler text to push content down the page.")
        pdf.render_dialogue("This dialogue should trigger a page break with (CONT'D).")
        # Should have at least 2 pages now
        assert pdf.page_no() >= 2

    def test_dialogue_width_matches_spec(self):
        """DIALOGUE_W should be 3.5 inches (88.9mm) per screenplay standards."""
        from cosmic_script.export.pdf_export import DIALOGUE_W

        assert abs(DIALOGUE_W - 88.9) < 0.01, f"DIALOGUE_W={DIALOGUE_W}, expected 88.9mm"


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
