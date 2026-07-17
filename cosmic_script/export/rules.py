"""Fountain validator rule-check functions.

Each function checks for a specific type of error in Fountain text and
returns a list of error dictionaries. Functions are organized by error
code group (E1-E20).
"""

from __future__ import annotations

import re

from cosmic_script.export.errors import (
    E1,
    E2,
    E3,
    E4,
    E5,
    E6,
    E7,
    E8,
    E9,
    E10,
    E11,
    E12,
    E13,
    E14,
    E15,
    E16,
    E17,
    E18,
    E19,
    E20,
    make_error,
)

# ---------------------------------------------------------------------------
# Regex Constants
# ---------------------------------------------------------------------------

# Scene heading prefixes per Fountain spec
SCENE_PREFIXES = r"INT\.\s?/EXT\.|INT\.|EXT\.|I/E|INT/EXT\.?|INT\./EXT\."

SCENE_PREFIX_RE = re.compile(
    rf"^\s*({SCENE_PREFIXES})",
    re.IGNORECASE,
)

# Time-of-day patterns
TIME_OF_DAY_RE = re.compile(
    r"\b(DAWN|MORNING|AFTERNOON|DAY|DUSK|EVENING|NIGHT|MIDNIGHT|LATER|CONTINUOUS)\b",
    re.IGNORECASE,
)

# Character: a line in ALL CAPS, possibly with parenthetical extensions
CHARACTER_RE = re.compile(r"^[A-Z][A-Z\s\.\'\-]+(\([A-Z\.]+\))?$")

# Transition known words and pattern
KNOWN_TRANSITIONS = {
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
TRANSITION_RE = re.compile(
    r"^(TO BLACK|" + "|".join(re.escape(t) for t in KNOWN_TRANSITIONS) + r")"
    r"(\.|:)?\s*$",
    re.IGNORECASE,
)

# Scene number pattern: #alphanumeric#
SCENE_NUMBER_RE = re.compile(r"#([A-Za-z0-9]+)#")

# Boneyard delimiters
BONEYARD_START_RE = re.compile(r"/\*")
BONEYARD_END_RE = re.compile(r"\*/")

# Note delimiters
NOTE_START_RE = re.compile(r"\[\[")
NOTE_END_RE = re.compile(r"\]\]")

# Parenthetical
PARENTHETICAL_RE = re.compile(r"^\s*\([^)]*\)\s*$")

# Dialogue continuation detection (indented or after character/parenthetical)
DIALOGUE_INDENT_RE = re.compile(r"^\t|^  |^    ")

# Force transition ending
FORCE_TRANSITION_RE = re.compile(r"^>.*")

# Centered text pattern: >text<
CENTERED_RE = re.compile(r"^>.+<$")

# Section pattern: # / ## / ### prefixed lines
SECTION_RE = re.compile(r"^#{1,6}\s")

# Synopsis pattern: = prefixed lines
SYNOPSIS_RE = re.compile(r"^=\s")

# Lyric pattern: ~ prefixed lines
LYRIC_RE = re.compile(r"^~")

# Page break pattern: ===
PAGE_BREAK_RE = re.compile(r"^={3,}\s*$")

# Forced scene heading: .PREFIX
FORCED_SCENE_HEADING_RE = re.compile(r"^\.[A-Z]")

# Forced action: !PREFIX
FORCED_ACTION_RE = re.compile(r"^![A-Z]")

# Forced character: @PREFIX
FORCED_CHARACTER_RE = re.compile(r"^@[A-Z]")

# Emphasis patterns (bold, italic, underline)
BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*[^*]+\*(?!\*)")
UNDERLINE_RE = re.compile(r"_[^_]+_")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def is_likely_scene_heading(line: str) -> bool:
    """Check if a line looks like a scene heading.

    Returns True if the line starts with INT, EXT, or similar prefix.
    """
    stripped = line.strip()
    if not stripped:
        return False
    return bool(SCENE_PREFIX_RE.match(stripped))


def is_likely_transition(line: str) -> bool:
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
    if upper in {t.upper() for t in KNOWN_TRANSITIONS}:
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


def is_character_like(line: str) -> bool:
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
    return bool(CHARACTER_RE.match(stripped))


def extract_clean_character(text: str) -> str:
    """Extract clean character name without parenthetical extensions."""
    # Remove parenthetical like (V.O.)
    clean = re.sub(r"\([^)]*\)", "", text).strip()
    return clean.upper()


def is_character_candidate(stripped: str) -> bool:
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


def is_followed_by_dialogue(lines: list[str], idx: int) -> bool:
    """Check if the line at idx is followed by a dialogue-like line (within
    the next few non-blank lines)."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        nxt = lines[j].strip()
        if not nxt:
            continue
        # Scene heading / transition breaks the pattern
        if is_likely_scene_heading(nxt) or is_likely_transition(nxt):
            return False
        # A non-ALL-CAPS short-to-medium line = likely dialogue
        if nxt != nxt.upper() or len(nxt) <= 60:
            return True
        return False
    return False


# ---------------------------------------------------------------------------
# Check Functions: E1-E12 (Parsed element checks)
# ---------------------------------------------------------------------------


def check_boneyards(text: str) -> list[dict]:
    """Check for unclosed boneyards (E8).

    Args:
        text: The full Fountain text.

    Returns:
        List of error dicts for unclosed boneyards.
    """
    errors: list[dict] = []
    opens = BONEYARD_START_RE.findall(text)
    closes = BONEYARD_END_RE.findall(text)
    if len(opens) > len(closes):
        errors.append(
            make_error(
                code=E8,
                message="Unclosed boneyard (missing */)",
                text=text,
                line=0,
            )
        )
    return errors


def check_notes(text: str) -> list[dict]:
    """Check for unclosed notes (E9).

    Args:
        text: The full Fountain text.

    Returns:
        List of error dicts for unclosed notes.
    """
    errors: list[dict] = []
    opens = NOTE_START_RE.findall(text)
    closes = NOTE_END_RE.findall(text)
    if len(opens) > len(closes):
        errors.append(
            make_error(
                code=E9,
                message="Unclosed note (missing ]])",
                text=text,
                line=0,
            )
        )
    return errors


def check_scene_headings(elements: list[dict]) -> list[dict]:
    """Check scene heading format (E1, E2).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for scene heading issues.
    """
    errors: list[dict] = []
    for el in elements:
        if el["type"] != "scene_heading":
            continue
        text = el["text"]
        # E1: missing prefix
        if not SCENE_PREFIX_RE.match(text):
            errors.append(
                make_error(
                    code=E1,
                    message=f"Scene heading missing INT/EXT prefix: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
        # E2: missing time-of-day
        if not TIME_OF_DAY_RE.search(text):
            errors.append(
                make_error(
                    code=E2,
                    message=f"Scene heading missing time-of-day: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
    return errors


def check_characters(elements: list[dict]) -> list[dict]:
    """Check character formatting (E4).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for character formatting issues.
    """
    errors: list[dict] = []
    for el in elements:
        if el["type"] != "character":
            continue
        text = el["text"].rstrip("^").strip()
        # E4: not uppercase
        if text != text.upper():
            errors.append(
                make_error(
                    code=E4,
                    message=f"Character name not uppercase: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
    return errors


def check_transitions(elements: list[dict]) -> list[dict]:
    """Check transition formatting (E5, E6).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for transition formatting issues.
    """
    errors: list[dict] = []
    for el in elements:
        if el["type"] != "transition":
            continue
        text = el["text"].rstrip(".").strip()
        upper = text.upper()
        # E5: not ending with TO: (skip for known standard transitions)
        is_standard = upper in {t.upper() for t in KNOWN_TRANSITIONS}
        has_to = upper.endswith("TO:") or upper.endswith(" TO")
        if not is_standard and not has_to:
            errors.append(
                make_error(
                    code=E5,
                    message=f"Transition not ending with TO:: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
        # E6: not uppercase
        if text != upper:
            errors.append(
                make_error(
                    code=E6,
                    message=f"Transition not uppercase: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
    return errors


def check_dialogue_context(elements: list[dict]) -> list[dict]:
    """Check for orphaned dialogue without character (E3).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for orphaned dialogue.
    """
    errors: list[dict] = []
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
                make_error(
                    code=E3,
                    message=f"Orphaned dialogue (no preceding character): {el['text']!r}",
                    text=el["text"],
                    line=el["line"],
                )
            )
    return errors


def check_parentheticals(elements: list[dict]) -> list[dict]:
    """Check for parenthetical outside dialogue context (E7).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for misplaced parentheticals.
    """
    errors: list[dict] = []
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
                make_error(
                    code=E7,
                    message=f"Parenthetical outside dialogue context: {el['text']!r}",
                    text=el["text"],
                    line=el["line"],
                )
            )
    return errors


def check_scene_numbers(elements: list[dict]) -> list[dict]:
    """Check scene number format (E12).

    Valid scene numbers match the pattern ``#[A-Za-z0-9]+#``.
    Any ``#`` in a scene heading that does not follow this pattern
    is flagged.

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for invalid scene numbers.
    """
    errors: list[dict] = []
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
                make_error(
                    code=E12,
                    message=f"Invalid scene number format in: {text!r}",
                    text=text,
                    line=el["line"],
                )
            )
    return errors


def check_dual_dialogue(elements: list[dict]) -> list[dict]:
    """Check for unpaired dual dialogue markers (E11).

    Dual dialogue characters should come in pairs (two per dialogue
    exchange). An odd count means at least one character is unpaired.

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for unpaired dual dialogue markers.
    """
    errors: list[dict] = []
    dual_chars: list[dict] = [el for el in elements if el["type"] == "character" and el.get("dual")]

    if len(dual_chars) % 2 != 0:
        # The last unpaired dual character is flagged
        unpaired = dual_chars[-1]
        errors.append(
            make_error(
                code=E11,
                message="Dual dialogue marker '^' without matching second character",
                text=unpaired["text"],
                line=unpaired["line"],
            )
        )
    return errors


def check_character_consistency(elements: list[dict]) -> list[dict]:
    """Check for character name inconsistencies (E10).

    Flags when the same base character name appears with different
    full-name variants (e.g. JOHN vs JOHN DOE).

    Args:
        elements: List of parsed element dicts.

    Returns:
        List of error dicts for character name inconsistencies.
    """
    errors: list[dict] = []
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
                make_error(
                    code=E10,
                    message=f"Character name inconsistency: {' / '.join(variants)}",
                    text=" / ".join(variants),
                    line=0,
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Check Functions: E13-E20 (Raw line checks)
# ---------------------------------------------------------------------------


def check_centered_text(lines: list[str]) -> list[dict]:
    """Check centered text formatting (E13).

    Centered text must follow the ``>text<`` pattern with content
    between the angle brackets.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for centered text issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">") and stripped.endswith("<"):
            # Check there's actual content between markers
            inner = stripped[1:-1].strip()
            if not inner:
                errors.append(
                    make_error(
                        code=E13,
                        message="Centered text is empty (> <)",
                        text=stripped,
                        line=i + 1,
                    )
                )
            elif inner != inner.strip():
                errors.append(
                    make_error(
                        code=E13,
                        message="Centered text has extra whitespace around content",
                        text=stripped,
                        line=i + 1,
                    )
                )
    return errors


def check_sections(lines: list[str]) -> list[dict]:
    """Check section heading formatting (E14).

    Sections start with ``#`` followed by a space and text.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for section heading issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not stripped.startswith("#"):
            continue
        if SECTION_RE.match(stripped):
            # Valid section - ensure it has text after the #
            text_after = stripped.lstrip("#").strip()
            if not text_after:
                errors.append(
                    make_error(
                        code=E14,
                        message="Section heading is empty",
                        text=stripped,
                        line=i + 1,
                    )
                )
        elif stripped.startswith("#") and not SECTION_RE.match(stripped):
            # Hash without space
            errors.append(
                make_error(
                    code=E14,
                    message="Section heading missing space after #",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


def check_synopses(lines: list[str]) -> list[dict]:
    """Check synopsis formatting (E15).

    Synopses start with ``=`` followed by a space and text.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for synopsis issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not stripped.startswith("="):
            continue
        if SYNOPSIS_RE.match(stripped):
            text_after = stripped[1:].strip()
            if not text_after:
                errors.append(
                    make_error(
                        code=E15,
                        message="Synopsis text is empty",
                        text=stripped,
                        line=i + 1,
                    )
                )
        elif stripped.startswith("=") and not SYNOPSIS_RE.match(stripped):
            errors.append(
                make_error(
                    code=E15,
                    message="Synopsis missing space after =",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


def check_lyrics(lines: list[str]) -> list[dict]:
    """Check lyric line formatting (E16).

    Lyrics start with ``~`` followed immediately by text.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for lyric issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not stripped.startswith("~"):
            continue
        text_after = stripped[1:].strip()
        if not text_after:
            errors.append(
                make_error(
                    code=E16,
                    message="Lyric text is empty",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


def check_page_breaks(lines: list[str]) -> list[dict]:
    """Check page break formatting (E17).

    Page breaks are denoted by a line containing ``===``.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for page break issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if "===" in stripped and not PAGE_BREAK_RE.match(stripped):
            errors.append(
                make_error(
                    code=E17,
                    message="Page break must be exactly === on its own line",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


def check_forced_elements(lines: list[str]) -> list[dict]:
    """Check forced element formatting (E18-E19).

    Forced scene heading: ``.TEXT``
    Forced action: ``!TEXT``
    Forced character: ``@TEXT``
    Forced transition: ``> TEXT``

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for forced element issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Forced scene heading (.PREFIX)
        if stripped.startswith("."):
            text_after = stripped[1:].strip()
            if not text_after:
                errors.append(
                    make_error(
                        code=E18,
                        message="Forced scene heading is empty after '.'",
                        text=stripped,
                        line=i + 1,
                    )
                )
            elif not text_after[0].isupper():
                errors.append(
                    make_error(
                        code=E18,
                        message="Forced scene heading should start with uppercase letter",
                        text=stripped,
                        line=i + 1,
                    )
                )
            continue

        # Forced action (!PREFIX)
        if stripped.startswith("!"):
            text_after = stripped[1:].strip()
            if not text_after:
                errors.append(
                    make_error(
                        code=E19,
                        message="Forced action is empty after '!'",
                        text=stripped,
                        line=i + 1,
                    )
                )
            continue

        # Forced character (@PREFIX)
        if stripped.startswith("@"):
            text_after = stripped[1:].strip()
            if not text_after:
                errors.append(
                    make_error(
                        code=E19,
                        message="Forced character is empty after '@'",
                        text=stripped,
                        line=i + 1,
                    )
                )
            elif text_after[0].isalpha() and not text_after[0].isupper():
                errors.append(
                    make_error(
                        code=E19,
                        message="Forced character name should start with uppercase",
                        text=stripped,
                        line=i + 1,
                    )
                )
            continue
    return errors


def check_emphasis(lines: list[str]) -> list[dict]:
    """Check emphasis formatting (E20).

    Bold: ``**text**``
    Italic: ``*text*``
    Underline: ``_text_``

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for emphasis issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check for unclosed bold
        bold_starts = [m.start() for m in re.finditer(r"\*\*", stripped)]
        if len(bold_starts) % 2 != 0:
            errors.append(
                make_error(
                    code=E20,
                    message="Unclosed bold formatting (**)",
                    text=stripped,
                    line=i + 1,
                )
            )

        # Check for unclosed italic
        italic_starts = [m.start() for m in re.finditer(r"(?<!\*)\*(?!\*)", stripped)]
        if len(italic_starts) % 2 != 0:
            errors.append(
                make_error(
                    code=E20,
                    message="Unclosed italic formatting (*)",
                    text=stripped,
                    line=i + 1,
                )
            )

        # Check for unclosed underline
        under_starts = [m.start() for m in re.finditer(r"_", stripped)]
        if len(under_starts) % 2 != 0:
            errors.append(
                make_error(
                    code=E20,
                    message="Unclosed underline formatting (_)",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Raw-line scan functions (catch issues the parser misses)
# ---------------------------------------------------------------------------


def check_raw_scene_heading_lines(lines: list[str]) -> list[dict]:
    """Scan all lines for text that looks like a scene heading but
    lacks the INT/EXT prefix (E1).

    A likely scene heading is a line that matches the pattern
    ``WORD - WORD`` or ``WORD WORD - WORD`` (location - time-of-day)
    but does not start with a known prefix.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for missing scene heading prefixes.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip if already starts with a valid prefix
        if SCENE_PREFIX_RE.match(stripped):
            continue
        # Skip title-page key:value lines
        if re.match(
            r"^(Title|Author|Source|Draft|Date|Contact|Copyright):", stripped, re.IGNORECASE
        ):
            continue
        # Check for "WORD - WORD" or "WORD WORD - WORD" pattern
        # (looks like LOCATION - TIME)
        if re.match(r"^[A-Za-z][A-Za-z\s\.]+-\s*[A-Za-z]+", stripped) and TIME_OF_DAY_RE.search(
            stripped
        ):
            errors.append(
                make_error(
                    code=E1,
                    message=f"Scene heading missing INT/EXT prefix: {stripped!r}",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors


def check_raw_possible_characters(lines: list[str]) -> list[dict]:
    """Scan for lines that look like lowercase character names (E4).

    A likely character name is a short line (1-3 words), capitalized
    or all-lowercase (typo), preceded by a blank line (or scene heading
    / transition boundary), and followed by a line that looks like
    dialogue.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for lowercase character names.
    """
    errors: list[dict] = []
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
        if is_likely_scene_heading(stripped):
            continue
        if is_likely_transition(stripped):
            continue
        if stripped.startswith("("):
            continue
        # Must be preceded by blank line or scene heading / transition
        prev_blank = (
            i == 0 or not lines[i - 1].strip() or is_likely_scene_heading(lines[i - 1].strip())
        )
        if not prev_blank:
            continue
        # Must be followed by non-blank, non-ALL-CAPS text (dialogue)
        if i + 1 < len(lines) and lines[i + 1].strip():
            next_text = lines[i + 1].strip()
            if next_text != next_text.upper() or len(next_text) > 50:
                # This looks like a character name that isn't uppercase
                errors.append(
                    make_error(
                        code=E4,
                        message=f"Character name not uppercase: {stripped!r}",
                        text=stripped,
                        line=i + 1,
                    )
                )
    return errors


def check_raw_transitions(lines: list[str]) -> list[dict]:
    """Scan raw lines for potential transitions that E5/E6 apply to.

    Catches ALL CAPS lines that look like transitions but were not
    classified as such by the parser (e.g., non-standard transitions).

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for transition issues.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Must be ALL CAPS
        if stripped != stripped.upper():
            continue
        # Must not be a scene heading
        if is_likely_scene_heading(stripped):
            continue
        # Must be preceded by blank line or start of section
        prev_blank = (
            i == 0 or not lines[i - 1].strip() or is_likely_scene_heading(lines[i - 1].strip())
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
        is_standard = upper in {t.upper() for t in KNOWN_TRANSITIONS}
        has_to = upper.endswith("TO:") or upper.endswith(" TO")
        # E5: not ending with TO: (skip standard transitions)
        if not is_standard and not has_to:
            errors.append(
                make_error(
                    code=E5,
                    message=f"Transition not ending with TO:: {stripped!r}",
                    text=stripped,
                    line=i + 1,
                )
            )
        # E6: not uppercase (already checked above, so won't fire here)
    return errors


def check_raw_possible_dialogue(lines: list[str]) -> list[dict]:
    """Scan for text that looks like dialogue but has no character (E3).

    Walks backwards past blank lines to check if a line follows a scene
    heading. Flags strong dialogue indicators (quotes, questions,
    exclamations) that appear without a preceding character name.

    Args:
        lines: List of raw Fountain text lines.

    Returns:
        List of error dicts for orphaned dialogue-like text.
    """
    errors: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip if it is itself a scene heading / transition / character
        if is_likely_scene_heading(stripped):
            continue
        if is_likely_transition(stripped):
            continue
        if is_character_like(stripped):
            continue
        # Walk backwards past blank lines to find a scene heading
        follows_heading = False
        j = i - 1
        while j >= 0:
            prev = lines[j].strip()
            if not prev:
                j -= 1
                continue
            if is_likely_scene_heading(prev):
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
                make_error(
                    code=E3,
                    message=f"Orphaned dialogue (no preceding character): {stripped!r}",
                    text=stripped,
                    line=i + 1,
                )
            )
    return errors
