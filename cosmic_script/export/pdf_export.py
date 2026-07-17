"""PDF export for screenplay format using fpdf2.

Renders a Screenplay object to a standard screenplay-format PDF
with proper margins, element positioning, title page, page numbers,
and continued markers.
"""

from __future__ import annotations

import logging
from typing import Optional

from fpdf import FPDF

from cosmic_script.export.fountain import generate_fountain
from cosmic_script.models import Screenplay, ScreenplayElement

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (all in millimetres)
# ---------------------------------------------------------------------------

IN_TO_MM = 25.4
PAGE_W = 8.5 * IN_TO_MM  # 215.9 mm
PAGE_H = 11.0 * IN_TO_MM  # 279.4 mm

LEFT_MARGIN = 1.5 * IN_TO_MM  # 38.1 mm
RIGHT_MARGIN = 1.0 * IN_TO_MM  # 25.4 mm
TOP_MARGIN = 1.0 * IN_TO_MM  # 25.4 mm
BOTTOM_MARGIN = 1.0 * IN_TO_MM  # 25.4 mm

CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN  # 152.4 mm (6")

# Element positioning (absolute x from left edge of page)
CHAR_X = 3.7 * IN_TO_MM  # 93.98 mm
DIALOGUE_X = 2.5 * IN_TO_MM  # 63.5 mm
DIALOGUE_W = 3.5 * IN_TO_MM  # 88.9 mm (from 2.5" to 6")
PAREN_X = 3.1 * IN_TO_MM  # 78.74 mm
PAREN_W = 1.4 * IN_TO_MM  # 35.56 mm

FONT_SIZE = 12  # pt
LINE_HEIGHT = 4.23  # mm (12 pt ~ 4.23 mm)
TITLE_FONT_SIZE = 16  # pt
HEADING_LINE_HEIGHT = 8.0  # mm blank line after scene heading / action blocks

# Maximum number of full-width (6-in) characters per line at Courier 12pt 10 CPI
_CHARS_PER_ACTION_LINE = 58
# Dialogue lines are narrower - approximately 3.5 inches wide at 10 CPI
_CHARS_PER_DIALOGUE_LINE = 35


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _mm(inches: float) -> float:
    """Convert inches to millimetres."""
    return inches * IN_TO_MM


# ---------------------------------------------------------------------------
# PDF class
# ---------------------------------------------------------------------------


class ScreenplayPDF(FPDF):
    """Custom PDF class that renders a Screenplay in standard Hollywood format.

    Uses the built-in Courier font (monospace, fixed-pitch) that ships
    with fpdf2 — no external font files needed.
    """

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_auto_page_break(auto=True, margin=BOTTOM_MARGIN)
        self.set_margins(LEFT_MARGIN, TOP_MARGIN, RIGHT_MARGIN)
        self.set_font("Courier", "", FONT_SIZE)

        # Internal state for continued markers
        self._current_character: Optional[str] = None
        self._has_more_marker: bool = False
        self._is_title_page: bool = False

    # ------------------------------------------------------------------
    # Header / Footer
    # ------------------------------------------------------------------

    def header(self) -> None:
        """Page number at top right, starting from page 2 (title page unnumbered)."""
        if self._is_title_page or self.page_no() <= 1:
            return
        self.set_y(_mm(0.5))
        self.set_font("Courier", "", FONT_SIZE)
        self.cell(0, LINE_HEIGHT, str(self.page_no()), align="R", new_x="LMARGIN", new_y="NEXT")
        # Reset y position back to top margin after header
        self.set_y(TOP_MARGIN)

    def footer(self) -> None:
        """No footer in standard screenplay format."""
        pass

    # ------------------------------------------------------------------
    # Title page
    # ------------------------------------------------------------------

    def render_title_page(
        self,
        title: str,
        author: Optional[str] = None,
        credit: Optional[str] = None,
        source: Optional[str] = None,
        draft_date: Optional[str] = None,
    ) -> None:
        """Render a centred title page.

        Args:
            title: The screenplay title.
            author: The author name (optional).
            credit: Writing credit line (e.g. "Written by").
            source: Source material credit.
            draft_date: Draft date string.
        """
        self._is_title_page = True
        self.add_page()

        # Vertically centre the content
        self.set_y(PAGE_H / 3)

        # Title in larger font
        self.set_font("Courier", "", TITLE_FONT_SIZE)
        self.multi_cell(0, LINE_HEIGHT, title.upper(), align="C")

        self.ln(LINE_HEIGHT * 2)

        # Credit / author block
        self.set_font("Courier", "", FONT_SIZE)
        credit_line = credit or "Written by"
        if author:
            lines = [credit_line, author]
            for line in lines:
                self.multi_cell(0, LINE_HEIGHT, line, align="C")
                self.ln(LINE_HEIGHT)

        # Optional metadata
        if source:
            self.ln(LINE_HEIGHT)
            self.multi_cell(0, LINE_HEIGHT, f"Based on: {source}", align="C")
        if draft_date:
            self.ln(LINE_HEIGHT)
            self.multi_cell(0, LINE_HEIGHT, draft_date, align="C")

        self._is_title_page = False

    # ------------------------------------------------------------------
    # Element rendering
    # ------------------------------------------------------------------

    def render_scene_heading(self, text: str) -> None:
        """Render a scene heading (ALL CAPS, left-aligned), preceded by a blank line."""
        self._check_page_break()
        # Add blank line before scene heading (unless at top of page)
        if self.get_y() > TOP_MARGIN + 0.01:
            self.ln(LINE_HEIGHT)
        self.set_x(LEFT_MARGIN)
        self.multi_cell(CONTENT_W, LINE_HEIGHT, text.upper(), align="L")
        self.ln(HEADING_LINE_HEIGHT)

    def render_action(self, text: str) -> None:
        """Render an action line (left-aligned, full width)."""
        self._check_page_break()
        self.set_x(LEFT_MARGIN)
        self.multi_cell(CONTENT_W, LINE_HEIGHT, text, align="L")

    def render_character(self, text: str) -> None:
        """Render a character cue (left-aligned at ~3.7" from left), preceded by a blank line."""
        self._check_page_break()
        # Add blank line before character name
        if self.get_y() > TOP_MARGIN + 0.01:
            self.ln(LINE_HEIGHT)
        self._current_character = text.upper().strip()
        self._has_more_marker = False
        self.set_x(CHAR_X)
        self.multi_cell(CONTENT_W - (CHAR_X - LEFT_MARGIN), LINE_HEIGHT, text.upper(), align="L")

    def render_dialogue(self, text: str) -> None:
        """Render a dialogue line (indented under character)."""
        self._check_dialogue_break(text)
        self.set_x(DIALOGUE_X)
        self.multi_cell(DIALOGUE_W, LINE_HEIGHT, text, align="L")

    def render_parenthetical(self, text: str) -> None:
        """Render a parenthetical (indented under character)."""
        self._check_page_break()
        # Wrap in parentheses for display
        display = f"({text})"
        self.set_x(PAREN_X)
        self.multi_cell(PAREN_W, LINE_HEIGHT, display, align="L")

    def render_transition(self, text: str) -> None:
        """Render a transition (right-aligned)."""
        self._check_page_break()
        self.set_x(LEFT_MARGIN)
        # Right-align by padding or using cell with align="R"
        self.cell(CONTENT_W, LINE_HEIGHT, text.upper(), align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(HEADING_LINE_HEIGHT)

    # ------------------------------------------------------------------
    # Page-break helpers
    # ------------------------------------------------------------------

    def _check_page_break(self) -> None:
        """Check if we need a page break; reset character tracking if so."""
        if self.get_y() + LINE_HEIGHT > PAGE_H - BOTTOM_MARGIN:
            self._current_character = None
            self._has_more_marker = False

    def _check_dialogue_break(self, text: str) -> None:
        """Insert ``(MORE)`` and carry character name when dialogue wraps.

        If the remaining space on the current page is insufficient for the
        dialogue *text*, write ``(MORE)`` now, add a new page, and re-print
        the character name with ``(CONT'D)``.
        """
        # Rough estimate: each dialogue line is 18 chars, line height = LINE_HEIGHT
        num_lines = max(1, (len(text) // _CHARS_PER_DIALOGUE_LINE) + 1)
        needed_height = num_lines * LINE_HEIGHT

        if self.get_y() + needed_height > PAGE_H - BOTTOM_MARGIN and not self._has_more_marker:
            # Write (MORE) at current position
            self.set_x(DIALOGUE_X)
            self.multi_cell(DIALOGUE_W, LINE_HEIGHT, "(MORE)", align="L")
            self._has_more_marker = True

            # New page
            self.add_page()

            # Re-print character with (CONT'D)
            if self._current_character:
                contd_name = f"{self._current_character} (CONT'D)"
                self.set_x(CHAR_X)
                self.multi_cell(
                    CONTENT_W - (CHAR_X - LEFT_MARGIN), LINE_HEIGHT, contd_name, align="L"
                )

    # ------------------------------------------------------------------
    # Bulk rendering
    # ------------------------------------------------------------------

    def render_screenplay(self, screenplay: Screenplay) -> None:
        """Render a complete Screenplay object to the PDF.

        Generates the title page (if metadata present) and then renders
        each screenplay element in order.

        Args:
            screenplay: The screenplay data model to render.
        """
        # Ensure we have elements
        fountain_text = generate_fountain(screenplay)
        if not fountain_text.strip():
            return

        # Title page
        if screenplay.title:
            self.render_title_page(
                title=screenplay.title,
                author=screenplay.author,
            )

        # Use elements from the model (already converted by generate_fountain)
        elements = screenplay.elements[:] if screenplay.elements else []
        if not elements and screenplay.scenes:
            from cosmic_script.export.fountain import _scenes_to_elements

            elements = _scenes_to_elements(screenplay.scenes)

        for element in elements:
            text = element.text.strip()
            if not text:
                continue

            et = element.element_type
            if et == "scene_heading":
                self.render_scene_heading(text)
            elif et == "action":
                self.render_action(text)
            elif et == "character":
                self.render_character(text)
            elif et == "dialogue":
                self.render_dialogue(text)
            elif et == "parenthetical":
                self.render_parenthetical(text)
            elif et == "transition":
                self.render_transition(text)
            else:
                # Fallback — render as action
                logger.debug("Unknown element type %r, rendering as action", et)
                self.render_action(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_pdf(screenplay: Screenplay, output_path: str) -> str:
    """Export a Screenplay to a properly formatted screenplay PDF.

    Args:
        screenplay: The screenplay data model to export.
        output_path: Absolute or relative path where the PDF will be saved.

    Returns:
        The absolute path to the saved PDF file.

    Raises:
        RuntimeError: If the PDF cannot be written.
    """
    import os

    pdf = ScreenplayPDF()
    pdf.render_screenplay(screenplay)

    # Ensure parent directory exists
    output_path = os.path.abspath(output_path)
    parent = os.path.dirname(output_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    pdf.output(output_path)
    logger.info("PDF exported to %s", output_path)
    return output_path
