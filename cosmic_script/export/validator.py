"""Deterministic Fountain text validator.

Parses Fountain markup text and checks for common structural and formatting
errors defined by the Fountain 1.1 specification. Supports auto-fix for
certain correctable issues.
"""

from __future__ import annotations

import re

from cosmic_script.export.errors import E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12
from cosmic_script.export.errors import E13, E14, E15, E16, E17, E18, E19, E20
from cosmic_script.export.errors import W1, make_error, make_warning
from cosmic_script.export.rules import (
    SCENE_PREFIX_RE,
    TIME_OF_DAY_RE,
    PARENTHETICAL_RE,
    FORCE_TRANSITION_RE,
    PAGE_BREAK_RE,
    SECTION_RE,
    SYNOPSIS_RE,
    LYRIC_RE,
    is_likely_scene_heading,
    is_likely_transition,
    is_character_like,
    is_character_candidate,
    is_followed_by_dialogue,
    extract_clean_character,
    check_boneyards,
    check_notes,
    check_scene_headings,
    check_characters,
    check_transitions,
    check_dialogue_context,
    check_parentheticals,
    check_scene_numbers,
    check_dual_dialogue,
    check_character_consistency,
    check_centered_text,
    check_sections,
    check_synopses,
    check_lyrics,
    check_page_breaks,
    check_forced_elements,
    check_emphasis,
    check_raw_scene_heading_lines,
    check_raw_possible_characters,
    check_raw_transitions,
    check_raw_possible_dialogue,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class FountainValidator:
    """Validates Fountain markup text against extended error categories.

    Error codes:
        E1  - Missing scene heading prefix (INT/EXT)
        E2  - Scene heading missing time-of-day
        E3  - Orphaned dialogue (no preceding character)
        E4  - Character name not uppercase
        E5  - Transition not ending in TO:
        E6  - Transition not uppercase
        E7  - Parenthetical outside dialogue context
        E8  - Unclosed boneyard (/* without */)
        E9  - Unclosed note ([[ without ]])
        E10 - Character name inconsistency
        E11 - Dual dialogue without second character
        E12 - Invalid scene number format
        E13 - Centered text not properly formatted (>text<)
        E14 - Section heading formatting issue
        E15 - Synopsis formatting issue
        E16 - Lyric line formatting issue
        E17 - Page break formatting issue
        E18 - Forced scene heading issue
        E19 - Forced action/character/transition issue
        E20 - Emphasis formatting issue
    """

    def validate(self, fountain_text: str) -> dict:
        """Parse and validate Fountain text against error categories.

        Args:
            fountain_text: Raw Fountain markup text to validate.

        Returns:
            A dict with keys:
                - valid (bool): True if no errors found.
                - errors (list[dict]): Each error has code, line, column,
                  text, message.
                - warnings (list[dict]): Non-critical observations.
                - characters (list[str]): Unique character names extracted.
        """
        errors: list[dict] = []
        warnings: list[dict] = []
        characters: list[str] = []

        if not fountain_text or not fountain_text.strip():
            return {
                "valid": True,
                "errors": [],
                "warnings": [],
                "characters": [],
            }

        lines = fountain_text.split("\n")

        # Parse lines into elements
        parsed_elements = self._parse_fountain_lines(lines)

        # Run all checks and collect errors
        errors.extend(check_boneyards(fountain_text))
        errors.extend(check_notes(fountain_text))
        errors.extend(check_scene_headings(parsed_elements))
        errors.extend(check_characters(parsed_elements))
        errors.extend(check_transitions(parsed_elements))
        errors.extend(check_dialogue_context(parsed_elements))
        errors.extend(check_parentheticals(parsed_elements))
        errors.extend(check_scene_numbers(parsed_elements))
        errors.extend(check_dual_dialogue(parsed_elements))
        errors.extend(check_character_consistency(parsed_elements))

        # Extended Fountain 1.1 feature checks (E13-E20)
        errors.extend(check_centered_text(lines))
        errors.extend(check_sections(lines))
        errors.extend(check_synopses(lines))
        errors.extend(check_lyrics(lines))
        errors.extend(check_page_breaks(lines))
        errors.extend(check_forced_elements(lines))
        errors.extend(check_emphasis(lines))

        # Raw-line scans catch issues the parser misses
        errors.extend(check_raw_scene_heading_lines(lines))
        errors.extend(check_raw_possible_characters(lines))
        errors.extend(check_raw_possible_dialogue(lines))
        errors.extend(check_raw_transitions(lines))

        # Extract unique characters
        chars_seen: set[str] = set()
        for el in parsed_elements:
            if el["type"] == "character" and el["clean_name"]:
                chars_seen.add(el["clean_name"])
        characters = sorted(chars_seen)

        # Notes produce warnings
        for el in parsed_elements:
            if el["type"] == "note":
                warnings.append(
                    make_warning(
                        code=W1,
                        message="Note found in Fountain text",
                        text=el["text"],
                        line=el.get("line", 0),
                    )
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "characters": characters,
        }

    def auto_fix(self, fountain_text: str) -> str:
        """Apply rule-based fixes for common Fountain errors.

        Fixes applied:
            - Uppercase character names
            - Close unclosed boneyards
            - Close unclosed notes
            - Fix transition TO: endings (minimal)
            - Add missing INT./EXT. prefix
            - Add missing time-of-day (DAY)
            - Format unformatted transitions
            - Insert blank line before character after action
            - Collapse excessive blank lines
            - Strip trailing whitespace

        Args:
            fountain_text: The Fountain text to fix.

        Returns:
            Corrected Fountain text with automated fixes applied.
        """
        if not fountain_text:
            return fountain_text

        lines = fountain_text.split("\n")
        fixed_lines: list[str] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()

            # Rule 6: Strip trailing whitespace
            line = line.rstrip()

            # Rule 5: Collapse excessive blank lines (handled after loop)
            # Rule 4: Insert blank line before character (needs lookahead, handled separately)

            # Rule 3: Unformatted transitions
            if stripped.lower() == "cut to:":
                fixed_lines.append("CUT TO:")
                continue

            # Rule 2: Missing time-of-day in scene heading
            if SCENE_PREFIX_RE.match(stripped) and not TIME_OF_DAY_RE.search(stripped):
                # Add " - DAY" if no time-of-day
                fixed_lines.append(stripped + " - DAY")
                continue

            # Rule 1: Missing scene heading prefix
            # Heuristic: line matches pattern WORD - WORD with time-of-day
            # and not already a scene heading
            if (
                not SCENE_PREFIX_RE.match(stripped)
                and re.match(r"^[A-Za-z][A-Za-z\s\.]+-\s*[A-Za-z]+", stripped)
                and TIME_OF_DAY_RE.search(stripped)
            ):
                fixed_lines.append("INT. " + stripped)
                continue

            # Close unclosed boneyard on same line
            if "/*" in stripped and "*/" not in stripped:
                fixed_lines.append(line + " */")
                continue

            # Close unclosed note on same line
            if "[[" in stripped and "]]" not in stripped:
                fixed_lines.append(line + " ]]")
                continue

            # Check if this is a character line (uppercase or lowercase name)
            # that is NOT a scene heading / transition / parenthetical
            if (
                stripped
                and not is_likely_scene_heading(stripped)
                and not is_likely_transition(stripped)
                and not stripped.startswith("(")
                and is_character_candidate(stripped)
                and is_followed_by_dialogue(lines, idx)
            ):
                fixed_lines.append(stripped.upper())
                continue

            fixed_lines.append(line)

        # Rule 4: Insert blank line before character after action
        # This needs a second pass because we need to look at previous line
        final_lines: list[str] = []
        for i, line in enumerate(fixed_lines):
            stripped = line.strip()
            # Check if this line is a character (uppercase, not scene heading, etc.)
            if (
                i > 0
                and stripped
                and not is_likely_scene_heading(stripped)
                and not is_likely_transition(stripped)
                and is_character_like(stripped)
            ):
                # Check previous line is non-blank and not a scene heading / transition
                prev_stripped = fixed_lines[i - 1].strip()
                if (
                    prev_stripped
                    and not is_likely_scene_heading(prev_stripped)
                    and not is_likely_transition(prev_stripped)
                ):
                    # Insert blank line before character
                    final_lines.append("")  # blank line
            final_lines.append(line)

        # Rule 5: Collapse 3+ blank lines to 2
        collapsed_lines: list[str] = []
        blank_count = 0
        for line in final_lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 2:
                    collapsed_lines.append(line)
                # else skip extra blank lines
            else:
                blank_count = 0
                collapsed_lines.append(line)

        return "\n".join(collapsed_lines)

    # ------------------------------------------------------------------
    # Internal: Fountain line parser
    # ------------------------------------------------------------------

    def _parse_fountain_lines(
        self,
        lines: list[str],
    ) -> list[dict]:
        """Parse lines into structured element list with type classification.

        Args:
            lines: Split lines of Fountain text.

        Returns:
            List of element dicts with keys: type, text, line, clean_name.
        """
        elements: list[dict] = []
        i = 0

        # Track state for character/dialogue grouping
        last_char_line: int | None = None

        while i < len(lines):
            raw_line = lines[i]
            stripped = raw_line.strip()
            line_no = i + 1  # 1-indexed

            # Blank lines
            if not stripped:
                # Reset character tracking if blank line
                last_char_line = None
                i += 1
                continue

            # Boneyard (comment)
            if "/*" in stripped:
                boneyard_text = stripped
                j = i
                while j < len(lines) and "*/" not in lines[j]:
                    j += 1
                    if j < len(lines):
                        if j > i:
                            boneyard_text += "\n" + lines[j]
                elements.append(
                    {
                        "type": "boneyard",
                        "text": boneyard_text,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i = j + 1 if j < len(lines) else len(lines)
                continue

            # Note
            if "[[" in stripped:
                note_text = stripped
                j = i
                while j < len(lines) and "]]" not in lines[j]:
                    j += 1
                    if j < len(lines):
                        if j > i:
                            note_text += "\n" + lines[j]
                elements.append(
                    {
                        "type": "note",
                        "text": note_text,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i = j + 1 if j < len(lines) else len(lines)
                continue

            # Page break (===)
            if PAGE_BREAK_RE.match(stripped):
                elements.append(
                    {
                        "type": "page_break",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Centered text (>text<)
            if stripped.startswith(">") and stripped.endswith("<") and len(stripped) > 2:
                elements.append(
                    {
                        "type": "centered",
                        "text": stripped[1:-1].strip(),
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Section (##...)
            if SECTION_RE.match(stripped):
                elements.append(
                    {
                        "type": "section",
                        "text": stripped.lstrip("#").strip(),
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Synopsis (= text)
            if SYNOPSIS_RE.match(stripped):
                elements.append(
                    {
                        "type": "synopsis",
                        "text": stripped[1:].strip(),
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Lyric (~text)
            if LYRIC_RE.match(stripped):
                elements.append(
                    {
                        "type": "lyric",
                        "text": stripped[1:].strip(),
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Forced scene heading (.TEXT)
            if stripped.startswith(".") and len(stripped) > 1:
                text_after = stripped[1:].strip()
                if text_after:
                    elements.append(
                        {
                            "type": "scene_heading",
                            "text": text_after,
                            "line": line_no,
                            "clean_name": "",
                        }
                    )
                    i += 1
                    continue

            # Forced action (!TEXT)
            if stripped.startswith("!") and len(stripped) > 1:
                text_after = stripped[1:].strip()
                if text_after:
                    elements.append(
                        {
                            "type": "action",
                            "text": text_after,
                            "line": line_no,
                            "clean_name": "",
                        }
                    )
                    i += 1
                    continue

            # Forced character (@TEXT)
            if stripped.startswith("@") and len(stripped) > 1:
                text_after = stripped[1:].strip()
                if text_after:
                    elements.append(
                        {
                            "type": "character",
                            "text": text_after,
                            "line": line_no,
                            "clean_name": extract_clean_character(text_after),
                        }
                    )
                    last_char_line = line_no
                    i += 1
                    continue

            # Force transition (> prefix)
            if FORCE_TRANSITION_RE.match(stripped):
                elements.append(
                    {
                        "type": "transition",
                        "text": stripped.lstrip(">").strip(),
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Scene heading detection
            if is_likely_scene_heading(stripped):
                clean_name = extract_clean_character(stripped)
                elements.append(
                    {
                        "type": "scene_heading",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": clean_name,
                    }
                )
                i += 1
                continue

            # Transition detection
            if is_likely_transition(stripped):
                elements.append(
                    {
                        "type": "transition",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Character detection: ALL CAPS preceded by blank line or
            # start-of-file, not a scene heading / transition
            prev_blank = (
                i == 0
                or not lines[i - 1].strip()
                or (elements and elements[-1]["type"] in ("scene_heading", "transition"))
            )
            if (
                prev_blank
                and not is_likely_scene_heading(stripped)
                and not is_likely_transition(stripped)
                and is_character_like(stripped)
            ):
                # Check for dual dialogue marker
                is_dual = stripped.endswith("^")
                clean = stripped.rstrip("^").strip()
                elements.append(
                    {
                        "type": "character",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": extract_clean_character(clean),
                        "dual": is_dual,
                    }
                )
                last_char_line = line_no
                i += 1
                continue

            # Parenthetical
            if PARENTHETICAL_RE.match(stripped):
                elements.append(
                    {
                        "type": "parenthetical",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Dialogue (indented or follow character/parenthetical/dialogue)
            is_after_char = elements and elements[-1]["type"] in (
                "character",
                "parenthetical",
                "dialogue",
            )
            if is_after_char:
                elements.append(
                    {
                        "type": "dialogue",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": "",
                    }
                )
                i += 1
                continue

            # Action (default)
            elements.append(
                {
                    "type": "action",
                    "text": stripped,
                    "line": line_no,
                    "clean_name": "",
                }
            )
            i += 1

        return elements
