"""Deterministic Fountain text validator.

Parses Fountain markup text and checks for common structural and formatting
errors defined by the Fountain 1.1 specification. Supports auto-fix for
certain correctable issues.
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Scene heading prefixes per Fountain spec
_SCENE_PREFIXES = r"INT\.\s?/EXT\.|INT\.|EXT\.|I/E|INT/EXT\.?|INT\./EXT\."

_SCENE_PREFIX_RE = re.compile(
    rf"^\s*({_SCENE_PREFIXES})",
    re.IGNORECASE,
)

# Time-of-day patterns
_TIME_OF_DAY_RE = re.compile(
    r"\b(DAWN|MORNING|AFTERNOON|DAY|DUSK|EVENING|NIGHT|MIDNIGHT|LATER|CONTINUOUS)\b",
    re.IGNORECASE,
)

# Character: a line in ALL CAPS, possibly with parenthetical extensions
_CHARACTER_RE = re.compile(r"^[A-Z][A-Z\s\.\'\-]+(\([A-Z\.]+\))?$")

# Transition known words and pattern
_KNOWN_TRANSITIONS = {
    "FADE IN",
    "FADE OUT",
    "FADE TO BLACK",
    "DISSOLVE TO",
    "CUT TO",
    "CUT TO BLACK",
    "SMASH CUT TO",
    "MATCH CUT TO",
    "JUMP CUT TO",
    "IRIS IN",
    "IRIS OUT",
    "INTERCUT WITH",
    "INTERCUT",
    "BACK TO",
    "TIME CUT",
    "TITLE CUT TO",
    "WIPE TO",
    "FADE THROUGH BLACK TO",
}
_TRANSITION_RE = re.compile(
    r"^(TO BLACK|" + "|".join(re.escape(t) for t in _KNOWN_TRANSITIONS) + r")"
    r"(\.|:)?\s*$",
    re.IGNORECASE,
)

# Scene number pattern: #alphanumeric#
_SCENE_NUMBER_RE = re.compile(r"#([A-Za-z0-9]+)#")

# Boneyard delimiters
_BONEYARD_START_RE = re.compile(r"/\*")
_BONEYARD_END_RE = re.compile(r"\*/")

# Note delimiters
_NOTE_START_RE = re.compile(r"\[\[")
_NOTE_END_RE = re.compile(r"\]\]")

# Parenthetical
_PARENTHETICAL_RE = re.compile(r"^\s*\([^)]*\)\s*$")

# Dialogue continuation detection (indented or after character/parenthetical)
_DIALOGUE_INDENT_RE = re.compile(r"^\t|^  |^    ")

# Force transition ending
_FORCE_TRANSITION_RE = re.compile(r"^>.*")

# Centered text pattern: >text<
_CENTERED_RE = re.compile(r"^>.+<$")

# Section pattern: # / ## / ### prefixed lines
_SECTION_RE = re.compile(r"^#{1,6}\s")

# Synopsis pattern: = prefixed lines
_SYNOPSIS_RE = re.compile(r"^=\s")

# Lyric pattern: ~ prefixed lines
_LYRIC_RE = re.compile(r"^~")

# Page break pattern: ===
_PAGE_BREAK_RE = re.compile(r"^={3,}\s*$")

# Forced scene heading: .PREFIX
_FORCED_SCENE_HEADING_RE = re.compile(r"^\.[A-Z]")

# Forced action: !PREFIX
_FORCED_ACTION_RE = re.compile(r"^![A-Z]")

# Forced character: @PREFIX
_FORCED_CHARACTER_RE = re.compile(r"^@[A-Z]")

# Emphasis patterns (bold, italic, underline)
_BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*[^*]+\*(?!\*)")
_UNDERLINE_RE = re.compile(r"_[^_]+_")

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

        # State machine state
        parsed_elements = self._parse_fountain_lines(lines, errors)
        self._check_boneyards(fountain_text, errors)
        self._check_notes(fountain_text, errors)
        self._check_scene_headings(parsed_elements, errors)
        self._check_characters(parsed_elements, errors, characters)
        self._check_transitions(parsed_elements, errors)
        self._check_dialogue_context(parsed_elements, errors)
        self._check_parentheticals(parsed_elements, errors)
        self._check_scene_numbers(parsed_elements, errors)
        self._check_dual_dialogue(parsed_elements, errors)
        self._check_character_consistency(parsed_elements, errors)
        # Extended Fountain 1.1 feature checks (E13-E20)
        self._check_centered_text(lines, errors)
        self._check_sections(lines, errors)
        self._check_synopses(lines, errors)
        self._check_lyrics(lines, errors)
        self._check_page_breaks(lines, errors)
        self._check_forced_elements(lines, errors)
        self._check_emphasis(lines, errors)

        # Raw-line scans catch issues the parser misses
        self._check_raw_scene_heading_lines(lines, errors)
        self._check_raw_possible_characters(lines, errors)
        self._check_raw_possible_dialogue(lines, errors)
        self._check_raw_transitions(lines, errors)

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
                    {
                        "code": "W1",
                        "message": "Note found in Fountain text",
                        "text": el["text"],
                        "line": el.get("line", 0),
                    }
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
            if _SCENE_PREFIX_RE.match(stripped) and not _TIME_OF_DAY_RE.search(stripped):
                # Add " - DAY" if no time-of-day
                fixed_lines.append(stripped + " - DAY")
                continue

            # Rule 1: Missing scene heading prefix
            # Heuristic: line matches pattern WORD - WORD with time-of-day
            # and not already a scene heading
            if (
                not _SCENE_PREFIX_RE.match(stripped)
                and re.match(r"^[A-Za-z][A-Za-z\s\.]+-\s*[A-Za-z]+", stripped)
                and _TIME_OF_DAY_RE.search(stripped)
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
                and not _is_likely_scene_heading(stripped)
                and not _is_likely_transition(stripped)
                and not stripped.startswith("(")
                and _is_character_candidate(stripped)
                and _is_followed_by_dialogue(lines, idx)
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
                and not _is_likely_scene_heading(stripped)
                and not _is_likely_transition(stripped)
                and _is_character_like(stripped)
            ):
                # Check previous line is non-blank and not a scene heading / transition
                prev_stripped = fixed_lines[i - 1].strip()
                if (
                    prev_stripped
                    and not _is_likely_scene_heading(prev_stripped)
                    and not _is_likely_transition(prev_stripped)
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
        errors: list[dict],
    ) -> list[dict]:
        """Parse lines into structured element list with type classification.

        Args:
            lines: Split lines of Fountain text.
            errors: Error list to append to (mutable).

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
            if _PAGE_BREAK_RE.match(stripped):
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
            if _SECTION_RE.match(stripped):
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
            if _SYNOPSIS_RE.match(stripped):
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
            if _LYRIC_RE.match(stripped):
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
                            "clean_name": _extract_clean_character(text_after),
                        }
                    )
                    last_char_line = line_no
                    i += 1
                    continue

            # Force transition (> prefix)
            if _FORCE_TRANSITION_RE.match(stripped):
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
            if _is_likely_scene_heading(stripped):
                clean_name = _extract_clean_character(stripped)
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
            if _is_likely_transition(stripped):
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
                and not _is_likely_scene_heading(stripped)
                and not _is_likely_transition(stripped)
                and _is_character_like(stripped)
            ):
                # Check for dual dialogue marker
                is_dual = stripped.endswith("^")
                clean = stripped.rstrip("^").strip()
                elements.append(
                    {
                        "type": "character",
                        "text": stripped,
                        "line": line_no,
                        "clean_name": _extract_clean_character(clean),
                        "dual": is_dual,
                    }
                )
                last_char_line = line_no
                i += 1
                continue

            # Parenthetical
            if _PARENTHETICAL_RE.match(stripped):
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

    # ------------------------------------------------------------------
    # Internal: Error checks
    # ------------------------------------------------------------------

    def _check_boneyards(self, text: str, errors: list[dict]) -> None:
        """Check for unclosed boneyards (E8).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        opens = _BONEYARD_START_RE.findall(text)
        closes = _BONEYARD_END_RE.findall(text)
        if len(opens) > len(closes):
            errors.append(
                {
                    "code": "E8",
                    "message": "Unclosed boneyard (missing */)",
                    "text": text,
                    "line": 0,
                }
            )

    def _check_notes(self, text: str, errors: list[dict]) -> None:
        """Check for unclosed notes (E9).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        opens = _NOTE_START_RE.findall(text)
        closes = _NOTE_END_RE.findall(text)
        if len(opens) > len(closes):
            errors.append(
                {
                    "code": "E9",
                    "message": "Unclosed note (missing ]])",
                    "text": text,
                    "line": 0,
                }
            )

    def _check_scene_headings(self, elements: list[dict], errors: list[dict]) -> None:
        """Check scene heading format (E1, E2).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for el in elements:
            if el["type"] != "scene_heading":
                continue
            text = el["text"]
            # E1: missing prefix
            if not _SCENE_PREFIX_RE.match(text):
                errors.append(
                    {
                        "code": "E1",
                        "message": f"Scene heading missing INT/EXT prefix: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )
            # E2: missing time-of-day
            if not _TIME_OF_DAY_RE.search(text):
                errors.append(
                    {
                        "code": "E2",
                        "message": f"Scene heading missing time-of-day: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )

    def _check_characters(
        self,
        elements: list[dict],
        errors: list[dict],
        characters: list[str],
    ) -> None:
        """Check character formatting (E4).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for el in elements:
            if el["type"] != "character":
                continue
            text = el["text"].rstrip("^").strip()
            # E4: not uppercase
            if text != text.upper():
                errors.append(
                    {
                        "code": "E4",
                        "message": f"Character name not uppercase: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )

    def _check_transitions(self, elements: list[dict], errors: list[dict]) -> None:
        """Check transition formatting (E5, E6).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for el in elements:
            if el["type"] != "transition":
                continue
            text = el["text"].rstrip(".").strip()
            upper = text.upper()
            # E5: not ending with TO: (skip for known standard transitions)
            is_standard = upper in {t.upper() for t in _KNOWN_TRANSITIONS}
            has_to = upper.endswith("TO:") or upper.endswith(" TO")
            if not is_standard and not has_to:
                errors.append(
                    {
                        "code": "E5",
                        "message": f"Transition not ending with TO:: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )
            # E6: not uppercase
            if text != upper:
                errors.append(
                    {
                        "code": "E6",
                        "message": f"Transition not uppercase: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )

    def _check_dialogue_context(self, elements: list[dict], errors: list[dict]) -> None:
        """Check for orphaned dialogue without character (E3).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, el in enumerate(elements):
            if el["type"] != "dialogue":
                continue
            # Check if there is a character somewhere before this dialogue
            # within the same dialogue block (no blank-line separator in
            # elements means they're one block)
            has_char_before = False
            for j in range(i - 1, -1, -1):
                prev = elements[j]
                if prev["type"] == "character":
                    has_char_before = True
                    break
                if prev["type"] in (
                    "scene_heading",
                    "transition",
                    "action",
                ):
                    break
            if not has_char_before:
                errors.append(
                    {
                        "code": "E3",
                        "message": f"Orphaned dialogue (no preceding character): {el['text']!r}",
                        "text": el["text"],
                        "line": el["line"],
                    }
                )

    def _check_parentheticals(self, elements: list[dict], errors: list[dict]) -> None:
        """Check for parenthetical outside dialogue context (E7).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, el in enumerate(elements):
            if el["type"] != "parenthetical":
                continue
            # A parenthetical should be preceded by character or dialogue
            # and followed by dialogue
            prev_type = elements[i - 1]["type"] if i > 0 else None
            next_type = elements[i + 1]["type"] if i + 1 < len(elements) else None

            valid_prev = prev_type in ("character", "dialogue", None)
            valid_next = next_type in ("dialogue", "parenthetical", None)

            if not (valid_prev and valid_next):
                errors.append(
                    {
                        "code": "E7",
                        "message": (f"Parenthetical outside dialogue context: {el['text']!r}"),
                        "text": el["text"],
                        "line": el["line"],
                    }
                )

    def _check_scene_numbers(self, elements: list[dict], errors: list[dict]) -> None:
        """Check scene number format (E12).

        Valid scene numbers match the pattern ``#[A-Za-z0-9]+#``.
        Any ``#`` in a scene heading that does not follow this pattern
        is flagged.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for el in elements:
            if el["type"] != "scene_heading":
                continue
            text = el["text"]
            if "#" not in text:
                continue
            # Find all # characters
            hash_positions = [i for i, c in enumerate(text) if c == "#"]
            # Check that every # is part of a valid #alnum# pair
            valid_pairs = re.findall(r"#[A-Za-z0-9]+#", text)
            valid_hashes = sum(2 for _ in valid_pairs)  # 2 # per pair
            if len(hash_positions) != valid_hashes:
                errors.append(
                    {
                        "code": "E12",
                        "message": f"Invalid scene number format in: {text!r}",
                        "text": text,
                        "line": el["line"],
                    }
                )

    def _check_dual_dialogue(self, elements: list[dict], errors: list[dict]) -> None:
        """Check for unpaired dual dialogue markers (E11).

        Dual dialogue characters should come in pairs (two per dialogue
        exchange). An odd count means at least one character is unpaired.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        dual_chars: list[dict] = [
            el for el in elements if el["type"] == "character" and el.get("dual")
        ]

        if len(dual_chars) % 2 != 0:
            # The last unpaired dual character is flagged
            unpaired = dual_chars[-1]
            errors.append(
                {
                    "code": "E11",
                    "message": ("Dual dialogue marker '^' without matching second character"),
                    "text": unpaired["text"],
                    "line": unpaired["line"],
                }
            )

    def _check_character_consistency(self, elements: list[dict], errors: list[dict]) -> None:
        """Check for character name inconsistencies (E10).

        Flags when the same base character name appears with different
        full-name variants (e.g. JOHN vs JOHN DOE).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        char_map: dict[str, list[str]] = {}
        for el in elements:
            if el["type"] != "character":
                continue
            name = el["clean_name"]
            if not name:
                continue
            # Derive a short key from the first token
            tokens = name.split()
            if not tokens:
                continue
            key = tokens[0].upper()
            if key not in char_map:
                char_map[key] = []
            if name.upper() not in char_map[key]:
                char_map[key].append(name.upper())

        for key, variants in char_map.items():
            if len(variants) > 1:
                errors.append(
                    {
                        "code": "E10",
                        "message": (f"Character name inconsistency: {' / '.join(variants)}"),
                        "text": " / ".join(variants),
                        "line": 0,
                    }
                )

    # ------------------------------------------------------------------
    # Extended Fountain 1.1 feature checks (E13-E20)
    # ------------------------------------------------------------------

    def _check_centered_text(self, lines: list[str], errors: list[dict]) -> None:
        """Check centered text formatting (E13).

        Centered text must follow the ``>text<`` pattern with content
        between the angle brackets.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">") and stripped.endswith("<"):
                # Check there's actual content between markers
                inner = stripped[1:-1].strip()
                if not inner:
                    errors.append(
                        {
                            "code": "E13",
                            "message": "Centered text is empty (> <)",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                elif inner != inner.strip():
                    errors.append(
                        {
                            "code": "E13",
                            "message": "Centered text has extra whitespace around content",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )

    def _check_sections(self, lines: list[str], errors: list[dict]) -> None:
        """Check section heading formatting (E14).

        Sections start with ``#`` followed by a space and text.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or not stripped.startswith("#"):
                continue
            if _SECTION_RE.match(stripped):
                # Valid section - ensure it has text after the #
                text_after = stripped.lstrip("#").strip()
                if not text_after:
                    errors.append(
                        {
                            "code": "E14",
                            "message": "Section heading is empty",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
            elif stripped.startswith("#") and not _SECTION_RE.match(stripped):
                # Hash without space
                errors.append(
                    {
                        "code": "E14",
                        "message": "Section heading missing space after #",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    def _check_synopses(self, lines: list[str], errors: list[dict]) -> None:
        """Check synopsis formatting (E15).

        Synopses start with ``=`` followed by a space and text.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or not stripped.startswith("="):
                continue
            if _SYNOPSIS_RE.match(stripped):
                text_after = stripped[1:].strip()
                if not text_after:
                    errors.append(
                        {
                            "code": "E15",
                            "message": "Synopsis text is empty",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
            elif stripped.startswith("=") and not _SYNOPSIS_RE.match(stripped):
                errors.append(
                    {
                        "code": "E15",
                        "message": "Synopsis missing space after =",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    def _check_lyrics(self, lines: list[str], errors: list[dict]) -> None:
        """Check lyric line formatting (E16).

        Lyrics start with ``~`` followed immediately by text.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or not stripped.startswith("~"):
                continue
            text_after = stripped[1:].strip()
            if not text_after:
                errors.append(
                    {
                        "code": "E16",
                        "message": "Lyric text is empty",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    def _check_page_breaks(self, lines: list[str], errors: list[dict]) -> None:
        """Check page break formatting (E17).

        Page breaks are denoted by a line containing ``===``.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if "===" in stripped and not _PAGE_BREAK_RE.match(stripped):
                errors.append(
                    {
                        "code": "E17",
                        "message": "Page break must be exactly === on its own line",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    def _check_forced_elements(self, lines: list[str], errors: list[dict]) -> None:
        """Check forced element formatting (E18-E19).

        Forced scene heading: ``.TEXT``
        Forced action: ``!TEXT``
        Forced character: ``@TEXT``
        Forced transition: ``> TEXT``

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Forced scene heading (.PREFIX)
            if stripped.startswith("."):
                text_after = stripped[1:].strip()
                if not text_after:
                    errors.append(
                        {
                            "code": "E18",
                            "message": "Forced scene heading is empty after '.'",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                elif not text_after[0].isupper():
                    errors.append(
                        {
                            "code": "E18",
                            "message": "Forced scene heading should start with uppercase letter",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                continue

            # Forced action (!PREFIX)
            if stripped.startswith("!"):
                text_after = stripped[1:].strip()
                if not text_after:
                    errors.append(
                        {
                            "code": "E19",
                            "message": "Forced action is empty after '!'",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                continue

            # Forced character (@PREFIX)
            if stripped.startswith("@"):
                text_after = stripped[1:].strip()
                if not text_after:
                    errors.append(
                        {
                            "code": "E19",
                            "message": "Forced character is empty after '@'",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                elif text_after[0].isalpha() and not text_after[0].isupper():
                    errors.append(
                        {
                            "code": "E19",
                            "message": "Forced character name should start with uppercase",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )
                continue

    def _check_emphasis(self, lines: list[str], errors: list[dict]) -> None:
        """Check emphasis formatting (E20).

        Bold: ``**text**``
        Italic: ``*text*``
        Underline: ``_text_``

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Check for unclosed bold
            bold_starts = [m.start() for m in re.finditer(r"\*\*", stripped)]
            if len(bold_starts) % 2 != 0:
                errors.append(
                    {
                        "code": "E20",
                        "message": "Unclosed bold formatting (**)",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

            # Check for unclosed italic
            italic_starts = [m.start() for m in re.finditer(r"(?<!\*)\*(?!\*)", stripped)]
            if len(italic_starts) % 2 != 0:
                errors.append(
                    {
                        "code": "E20",
                        "message": "Unclosed italic formatting (*)",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

            # Check for unclosed underline
            under_starts = [m.start() for m in re.finditer(r"_", stripped)]
            if len(under_starts) % 2 != 0:
                errors.append(
                    {
                        "code": "E20",
                        "message": "Unclosed underline formatting (_)",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    # ------------------------------------------------------------------
    # Internal: Raw-line scans (catches what the parser misses)
    # ------------------------------------------------------------------

    def _check_raw_scene_heading_lines(self, lines: list[str], errors: list[dict]) -> None:
        """Scan all lines for text that looks like a scene heading but
        lacks the INT/EXT prefix (E1).

        A likely scene heading is a line that matches the pattern
        ``WORD - WORD`` or ``WORD WORD - WORD`` (location - time-of-day)
        but does not start with a known prefix.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip if already starts with a valid prefix
            if _SCENE_PREFIX_RE.match(stripped):
                continue
            # Skip title-page key:value lines
            if re.match(
                r"^(Title|Author|Source|Draft|Date|Contact|Copyright):", stripped, re.IGNORECASE
            ):
                continue
            # Check for "WORD - WORD" or "WORD WORD - WORD" pattern
            # (looks like LOCATION - TIME)
            if re.match(
                r"^[A-Za-z][A-Za-z\s\.]+-\s*[A-Za-z]+", stripped
            ) and _TIME_OF_DAY_RE.search(stripped):
                errors.append(
                    {
                        "code": "E1",
                        "message": f"Scene heading missing INT/EXT prefix: {stripped!r}",
                        "text": stripped,
                        "line": i + 1,
                    }
                )

    def _check_raw_possible_characters(self, lines: list[str], errors: list[dict]) -> None:
        """Scan for lines that look like lowercase character names (E4).

        A likely character name is a short line (1-3 words), capitalized
        or all-lowercase (typo), preceded by a blank line (or scene heading
        / transition boundary), and followed by a line that looks like
        dialogue.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Must NOT be ALL CAPS (already valid)
            if stripped == stripped.upper():
                continue
            # Short: 1-4 words max
            words = stripped.split()
            if not words or len(words) > 4:
                continue
            # Skip title-page key:value lines
            if re.match(
                r"^(Title|Author|Source|Draft|Date|Contact|Copyright):", stripped, re.IGNORECASE
            ):
                continue
            # Skip if it's a scene heading, transition, or parenthetical
            if _is_likely_scene_heading(stripped):
                continue
            if _is_likely_transition(stripped):
                continue
            if stripped.startswith("("):
                continue
            # Must be preceded by blank line or scene heading / transition
            prev_blank = (
                i == 0 or not lines[i - 1].strip() or _is_likely_scene_heading(lines[i - 1].strip())
            )
            if not prev_blank:
                continue
            # Must be followed by non-blank, non-ALL-CAPS text (dialogue)
            if i + 1 < len(lines) and lines[i + 1].strip():
                next_text = lines[i + 1].strip()
                if next_text != next_text.upper() or len(next_text) > 50:
                    # This looks like a character name that isn't uppercase
                    errors.append(
                        {
                            "code": "E4",
                            "message": f"Character name not uppercase: {stripped!r}",
                            "text": stripped,
                            "line": i + 1,
                        }
                    )

    def _check_raw_transitions(self, lines: list[str], errors: list[dict]) -> None:
        """Scan raw lines for potential transitions that E5/E6 apply to.

        Catches ALL CAPS lines that look like transitions but were not
        classified as such by the parser (e.g., non-standard transitions).

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Must be ALL CAPS
            if stripped != stripped.upper():
                continue
            # Must not be a scene heading
            if _is_likely_scene_heading(stripped):
                continue
            # Must be preceded by blank line or start of section
            prev_blank = (
                i == 0 or not lines[i - 1].strip() or _is_likely_scene_heading(lines[i - 1].strip())
            )
            if not prev_blank:
                continue
            # Skip short lines (likely character names like "JOHN")
            if len(stripped) <= 5:
                continue
            # Skip lines with parenthetical extensions (character names)
            if "(" in stripped:
                continue
            # Strip trailing punctuation for comparison
            clean = stripped.rstrip(".!:;")
            upper = clean.upper()
            is_standard = upper in {t.upper() for t in _KNOWN_TRANSITIONS}
            has_to = upper.endswith("TO:") or upper.endswith(" TO")
            # E5: not ending with TO: (skip standard transitions)
            if not is_standard and not has_to:
                errors.append(
                    {
                        "code": "E5",
                        "message": (f"Transition not ending with TO:: {stripped!r}"),
                        "text": stripped,
                        "line": i + 1,
                    }
                )
            # E6: not uppercase (already checked above, so won't fire here)

    def _check_raw_possible_dialogue(self, lines: list[str], errors: list[dict]) -> None:
        """Scan for text that looks like dialogue but has no character (E3).

        Walks backwards past blank lines to check if a line follows a scene
        heading. Flags strong dialogue indicators (quotes, questions,
        exclamations) that appear without a preceding character name.

        SIDE EFFECT: Appends error dicts to the ``errors`` list.
        """
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip if it is itself a scene heading / transition / character
            if _is_likely_scene_heading(stripped):
                continue
            if _is_likely_transition(stripped):
                continue
            if _is_character_like(stripped):
                continue
            # Walk backwards past blank lines to find a scene heading
            follows_heading = False
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if not prev:
                    j -= 1
                    continue
                if _is_likely_scene_heading(prev):
                    follows_heading = True
                break
            if not follows_heading:
                continue
            # Skip very long lines (they're action, not dialogue)
            if len(stripped) > 120:
                continue
            # Strong dialogue indicators:
            #   - Wrapped in quotes
            #   - Ends with ? or !
            #   - Starts with an interjection or conversational words
            is_dialogue_like = (
                stripped.startswith(('"', "'", "``"))
                or stripped.endswith(('"', "'", "''"))
                or stripped.endswith(("?", "!"))
                or re.match(
                    r"^(Well|Oh|Hey|Hi|Hello|Yeah|No|Yes|Okay|Sure|Sorry|"
                    r"Please|Thanks|Wait|Listen|Look|So|But|And|Then|"
                    r"Actually|Really|Right|Hmm|Um|Ah)",
                    stripped,
                    re.IGNORECASE,
                )
            )
            if is_dialogue_like:
                errors.append(
                    {
                        "code": "E3",
                        "message": (f"Orphaned dialogue (no preceding character): {stripped!r}"),
                        "text": stripped,
                        "line": i + 1,
                    }
                )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_likely_scene_heading(line: str) -> bool:
    """Check if a line looks like a scene heading.

    Returns True if the line starts with INT, EXT, or similar prefix.
    """
    stripped = line.strip()
    if not stripped:
        return False
    return bool(_SCENE_PREFIX_RE.match(stripped))


def _is_likely_transition(line: str) -> bool:
    """Check if a line looks like a transition.

    Matches known transition words, ALL CAPS ending with TO:,
    or ALL CAPS lines that contain common transition vocabulary
    (CUT, FADE, DISSOLVE, SMASH, MATCH, IRIS, WIPE, etc.).
    """
    stripped = line.strip()
    if not stripped:
        return False
    upper = stripped.upper()
    # Force transition (> prefix)
    if stripped.startswith(">"):
        return True
    # Known transitions
    if upper in {t.upper() for t in _KNOWN_TRANSITIONS}:
        return True
    # ALL CAPS ending with TO: or TO
    if upper.endswith(" TO:") or (upper.endswith(" TO") and upper == stripped):
        return True
    # ALL CAPS line matching broader transition pattern
    if upper == stripped and len(stripped) > 5:
        if re.match(
            r"^(FADE|DISSOLVE|CUT|SMASH|MATCH|JUMP|IRIS|WIPE|"
            r"PULL|PUSH|ROLL|SWISH|SPLIT|DOOR|FREEZE|HELICOPTER)",
            stripped,
        ):
            return True
        # Contains known transition words
        transition_keywords = {"TO:", "TO BLACK", "IN:", "OUT:", "CUT:", "FADE:"}
        for kw in transition_keywords:
            if kw in upper:
                return True
    return False


def _is_character_like(line: str) -> bool:
    """Check if a line resembles a character cue.

    Returns True for ALL CAPS lines (including with parenthetical
    extensions like (V.O.)).
    """
    stripped = line.strip().rstrip("^").strip()
    if not stripped:
        return False
    # Exclude extremely short lines (single letter)
    if len(stripped) < 2:
        return False
    # Must be all uppercase with allowed punctuation
    return bool(_CHARACTER_RE.match(stripped))


def _extract_clean_character(text: str) -> str:
    """Extract clean character name without parenthetical extensions."""
    # Remove parenthetical like (V.O.)
    clean = re.sub(r"\([^)]*\)", "", text).strip()
    return clean.upper()


def _is_character_candidate(stripped: str) -> bool:
    """Check if a stripped line could be a character name (case-insensitive).

    Accepts lines consisting of 1-4 words that could represent a character
    name, with optional parenthetical extension like (V.O.).
    Excludes title-page key:value lines.
    """
    # Exclude title page key-value lines
    if re.match(
        r"^(Title|Author|Source|Draft|Date|Contact|Copyright):",
        stripped,
        re.IGNORECASE,
    ):
        return False
    # Remove parenthetical extension
    core = re.sub(r"\([^)]*\)", "", stripped).strip()
    if not core:
        return False
    words = core.split()
    if len(words) > 4:
        return False
    # Must start with a letter
    if not core[0].isalpha():
        return False
    # ALL CAPS names (already valid)
    if core == core.upper():
        return True
    # Accept any line that looks like a simple phrase
    # (all-lowercase or capitalized first letter)
    return len(core) > 1


def _is_followed_by_dialogue(lines: list[str], idx: int) -> bool:
    """Check if the line at idx is followed by a dialogue-like line (within
    the next few non-blank lines)."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        nxt = lines[j].strip()
        if not nxt:
            continue
        # Scene heading / transition breaks the pattern
        if _is_likely_scene_heading(nxt) or _is_likely_transition(nxt):
            return False
        # A non-ALL-CAPS short-to-medium line = likely dialogue
        if nxt != nxt.upper() or len(nxt) <= 60:
            return True
        return False
    return False
