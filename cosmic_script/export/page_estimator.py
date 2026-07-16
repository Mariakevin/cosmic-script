"""Screenplay page-count estimator.

Estimates the number of pages a Screenplay would occupy in standard
Hollywood screenplay format (Courier 12pt, US Letter) using pure
calculation — no LLM calls needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from cosmic_script.models import Screenplay, ScreenplayElement, Scene

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Standard screenplay metrics
LINES_PER_PAGE = 55  # ~55 lines of action text per standard screenplay page
WORDS_PER_PAGE = 250  # ~250 words per page alternative metric

# Line-count contributions per element type
LINE_WEIGHTS: dict[str, int] = {
    "scene_heading": 1,
    "character": 1,
    "parenthetical": 1,
    "transition": 1,
}

# Characters per line for each element type (Courier 12pt, 10 CPI)
_CHARS_PER_LINE: dict[str, int] = {
    "action": 58,  # 6" wide at 10 CPI minus small buffer
    "dialogue": 18,  # ~2" wide at 10 CPI
    "scene_heading": 58,
    "character": 30,  # typically short
    "parenthetical": 14,  # ~1.4" wide at 10 CPI
    "transition": 58,
}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PageEstimate:
    """Structured page-count estimate for a screenplay.

    Attributes:
        estimated_pages: Estimated page count (float, may be fractional).
        total_lines: Total calculated line count before pagination.
        breakdown: Per-element-type line counts.
        confidence: Confidence level ("high", "medium", "low").
    """

    estimated_pages: float
    total_lines: int
    breakdown: dict[str, int] = field(default_factory=dict)
    confidence: str = "medium"


# ---------------------------------------------------------------------------
# Estimation logic
# ---------------------------------------------------------------------------


def _count_lines_for_element(element: ScreenplayElement) -> int:
    """Count the estimated number of printed lines for a single element.

    Accounts for text wrapping based on element type.  Each wrapped line
    consumes one vertical line of space.
    """
    text = element.text.strip()
    if not text:
        return 0

    et = element.element_type
    base = LINE_WEIGHTS.get(et, 1)

    # Determine the relevant characters-per-line for this type
    cpl = _CHARS_PER_LINE.get(et, 58)
    if cpl <= 0:
        cpl = 58

    # For types that wrap, count additional lines beyond the first
    total_chars = len(text)
    additional_lines = (total_chars // cpl) if cpl > 0 else 0

    if et == "action":
        # Action wraps fully; count every full cpl chunk as a line
        return max(1, math.ceil(total_chars / cpl))
    elif et == "dialogue":
        # Dialogue also wraps within its narrower column
        return max(1, math.ceil(total_chars / cpl))
    elif et == "scene_heading":
        # Typically one line, even if long it may wrap
        return max(1, math.ceil(total_chars / cpl))
    elif et == "character":
        # Almost always one line
        return 1
    elif et == "parenthetical":
        # Almost always one line
        return 1
    elif et == "transition":
        return 1
    else:
        # Unknown type — treat as action
        return max(1, math.ceil(total_chars / 58))


def _estimate_lines(screenplay: Screenplay) -> tuple[dict[str, int], int, int]:
    """Count total lines and per-type lines for a screenplay.

    Returns:
        Tuple of (breakdown dict, total_lines, total_word_count).
    """
    # Get elements
    if screenplay.elements:
        elements = screenplay.elements
    elif screenplay.scenes:
        from cosmic_script.export.fountain import _scenes_to_elements
        elements = _scenes_to_elements(screenplay.scenes)
    else:
        return {}, 0, 0

    breakdown: dict[str, int] = {}
    total_lines = 0
    total_words = 0

    prev_type: Optional[str] = None

    for element in elements:
        text = element.text.strip()
        if not text:
            continue

        et = element.element_type
        lines = _count_lines_for_element(element)
        word_count = len(text.split())

        # Accumulate
        breakdown[et] = breakdown.get(et, 0) + lines
        total_lines += lines
        total_words += word_count

        # Add blank-line overhead between different elements
        # (0.5 line per blank)
        if prev_type is not None and prev_type != et:
            total_lines += 0.5
        prev_type = et

    # Additional overhead: blank line before scene headings
    for element in elements:
        if element.element_type == "scene_heading":
            total_lines += 0.5  # blank line before heading

    return breakdown, total_lines, total_words


def estimate_pages(screenplay: Screenplay) -> PageEstimate:
    """Estimate the number of pages for a Screenplay.

    Uses the standard 55-lines-per-page metric with a 10% formatting
    buffer.  Confidence is determined by the screenplay's content
    completeness.

    Args:
        screenplay: The screenplay data model to estimate.

    Returns:
        A :class:`PageEstimate` with the estimated page count, breakdown,
        and confidence level.

    Example:
        >>> from cosmic_script.models import Screenplay, ScreenplayElement
        >>> sp = Screenplay(title="Test", elements=[
        ...     ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - DAY"),
        ...     ScreenplayElement(element_type="action", text="A quiet room."),
        ... ])
        >>> est = estimate_pages(sp)
        >>> est.estimated_pages > 0
        True
    """
    if not screenplay.elements and not screenplay.scenes:
        return PageEstimate(
            estimated_pages=0.0,
            total_lines=0,
            breakdown={},
            confidence="high",
        )

    breakdown, total_lines, total_words = _estimate_lines(screenplay)

    if total_lines <= 0:
        return PageEstimate(
            estimated_pages=0.0,
            total_lines=0,
            breakdown={},
            confidence="high",
        )

    # Apply 10% buffer for formatting / pagination overhead
    buffer_factor = 1.10
    raw_pages = total_lines / LINES_PER_PAGE
    estimated_pages = round(max(0.1, raw_pages * buffer_factor), 1)

    # Determine confidence
    has_reasonable_content = len(breakdown) >= 3
    has_scenes = breakdown.get("scene_heading", 0) > 0
    if has_reasonable_content and has_scenes:
        confidence = "high"
    elif total_lines > 10:
        confidence = "medium"
    else:
        confidence = "low"

    return PageEstimate(
        estimated_pages=estimated_pages,
        total_lines=total_lines,
        breakdown=breakdown,
        confidence=confidence,
    )
