"""Chapter detection — split text into chapters via regex or fallback chunks."""

from __future__ import annotations

import math
import re
from typing import Optional

from cosmic_script.models import Chapter


# ── Roman numeral helpers ──────────────────────────────────

_ROMAN_MAP: dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}


def _roman_to_int(roman: str) -> int:
    """Convert a Roman numeral string to an integer.

    Only handles I through X (matching the accepted patterns).
    Returns 0 for unrecognised input.
    """
    return _ROMAN_MAP.get(roman.upper(), 0)


# ── Chapter heading regex patterns ─────────────────────────

# Combined pattern: match chapter/part headings at line start
_CHAPTER_RE = re.compile(
    r"^(?P<heading>"
    r"(?:Chapter|CHAPTER)\s+(?P<num_arabic>\d+)(?:\s*[:\-–]\s*(?P<title_arabic>.*?))?"
    r"|"
    r"(?:Chapter|CHAPTER)\s+(?P<num_roman>X|IX|VIII|VII|VI|V|IV|III|II|I)\b(?:\s*[:\-–]\s*(?P<title_roman>.*?))?"
    r"|"
    r"(?:Part|PART)\s+(?P<num_part>\d+)(?:\s*[:\-–]\s*(?P<title_part>.*?))?"
    r")"
    r"\s*$",
    re.MULTILINE,
)


def _parse_heading(line: str) -> Optional[tuple[int, Optional[str]]]:
    """Try to parse a single line as a chapter heading.

    Returns:
        ``(chapter_number, chapter_title_or_None)`` if matched, else ``None``.
    """
    m = _CHAPTER_RE.match(line)
    if not m:
        return None

    if m.lastgroup == "heading":
        # Determine which group actually matched
        if m.group("num_arabic") is not None:
            num = int(m.group("num_arabic"))
            title = m.group("title_arabic")
        elif m.group("num_roman") is not None:
            num = _roman_to_int(m.group("num_roman"))
            title = m.group("title_roman")
        elif m.group("num_part") is not None:
            num = int(m.group("num_part"))
            title = m.group("title_part")
        else:
            return None

        # Clean up title (strip leftover whitespace)
        clean_title = title.strip() if title else None
        return (num, clean_title)

    return None


# ── Fallback chunking ──────────────────────────────────────

_DEFAULT_CHUNK_COUNT = 5
_MIN_CHUNK_SIZE = 100  # characters


def _fallback_chapters(text: str) -> list[Chapter]:
    """Split text into roughly equal-sized chunks when no chapter headings exist.

    Uses word-boundary-aware splitting to avoid cutting mid-sentence.
    """
    text = text.strip()
    if not text:
        return []

    total_len = len(text)
    if total_len < _MIN_CHUNK_SIZE:
        # Too short to split — return as a single chapter
        return [Chapter(number=1, text=text)]

    num_chunks = min(_DEFAULT_CHUNK_COUNT, max(1, total_len // _MIN_CHUNK_SIZE))
    target_size = total_len // num_chunks

    chapters: list[Chapter] = []
    start = 0
    ch_num = 1

    for _ in range(num_chunks - 1):
        # Find a good split point near target_size
        end = start + target_size
        if end >= total_len:
            end = total_len
        else:
            # Try to break at a newline or space
            # Look backward from end for a paragraph break, then line break, then space
            search_start = max(start, end - 50)
            search_region = text[search_start:end]
            # Prefer paragraph break (\n\n)
            pbreak = search_region.rfind("\n\n")
            if pbreak != -1:
                end = search_start + pbreak + 2  # include the newlines
            else:
                # Prefer line break (\n)
                lbreak = search_region.rfind("\n")
                if lbreak != -1:
                    end = search_start + lbreak + 1
                else:
                    # Fall back to space
                    sp = search_region.rfind(" ")
                    if sp != -1:
                        end = search_start + sp + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chapters.append(Chapter(number=ch_num, text=chunk_text))
            ch_num += 1
        start = end

    # Remaining text
    remaining = text[start:].strip()
    if remaining:
        chapters.append(Chapter(number=ch_num, text=remaining))

    return chapters or [Chapter(number=1, text=text.strip())]


# ── Public API ─────────────────────────────────────────────


def split_into_chapters(text: str) -> list[Chapter]:
    """Detect chapter boundaries and split text into ``Chapter`` objects.

    Detection is based on common chapter/part heading patterns at the
    beginning of lines (see module-level ``_CHAPTER_RE``).  If no
    headings are found the text is split into roughly equal-sized chunks
    as a fallback.

    Args:
        text: The full plain-text document body.

    Returns:
        A list of :class:`Chapter` objects.  Returns an empty list when
        *text* is empty or whitespace-only.
    """
    if not text or not text.strip():
        return []

    # Collect all heading matches with their positions
    matches: list[tuple[int, int, Optional[str]]] = []  # (start_pos, number, title)
    for m in _CHAPTER_RE.finditer(text):
        parsed = _parse_heading(m.group(0))
        if parsed is not None:
            num, title = parsed
            matches.append((m.start(), num, title))

    if not matches:
        # Fallback to equal-size chunks
        return _fallback_chapters(text)

    # Build chapters from heading positions
    chapters: list[Chapter] = []
    for i, (start_pos, expected_num, title) in enumerate(matches):
        # Determine end of this chapter (start of next heading or end of text)
        if i + 1 < len(matches):
            end_pos = matches[i + 1][0]
        else:
            end_pos = len(text)

        # Extract body from after the heading line to before the next heading
        # Find the end of the heading line
        heading_end = text.index("\n", start_pos) if "\n" in text[start_pos:] else len(text)
        if heading_end < end_pos:
            body_start = heading_end + 1
        else:
            body_start = end_pos

        body = text[body_start:end_pos].strip()

        # Re-number sequentially
        chapters.append(Chapter(number=i + 1, title=title, text=body))

    return chapters
