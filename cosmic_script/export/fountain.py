"""Fountain format generator for cosmic-script.

Converts a Screenplay object into standard Fountain markup text
following the Fountain 1.1 specification conventions.
"""

from __future__ import annotations

from cosmic_script.models import Screenplay, Scene, ScreenplayElement


def _scenes_to_elements(scenes: list[Scene]) -> list[ScreenplayElement]:
    """Convert a list of Scene objects to ScreenplayElement objects.

    Each scene's content is treated as raw Fountain text. We parse it
    to extract scene headings, action, character cues, dialogue, etc.

    Args:
        scenes: List of Scene objects from the conversion pipeline.

    Returns:
        A list of ScreenplayElement objects for Fountain export.
    """
    elements: list[ScreenplayElement] = []

    for scene in scenes:
        # Add the scene heading
        elements.append(ScreenplayElement(
            element_type="scene_heading",
            text=scene.heading,
        ))

        # Parse the scene content line by line
        lines = scene.content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines
            if not line:
                i += 1
                continue

            # Skip the heading line if it appears in content
            if line.startswith(("INT.", "EXT.", "INT/EXT.", "I/E.")):
                i += 1
                continue

            # Check for character cue (UPPERCASE, typically 2-20 chars)
            if line.isupper() and len(line) <= 20 and not line.startswith("FADE"):
                elements.append(ScreenplayElement(
                    element_type="character",
                    text=line,
                ))
                i += 1
                # Next non-empty line(s) are dialogue
                while i < len(lines):
                    dial_line = lines[i].strip()
                    if not dial_line:
                        i += 1
                        continue
                    # If it looks like another character cue or heading, stop
                    if (dial_line.isupper() and len(dial_line) <= 20) or \
                       dial_line.startswith(("INT.", "EXT.", "INT/EXT.", "I/E.")):
                        break
                    # Check for parenthetical
                    if dial_line.startswith("(") and dial_line.endswith(")"):
                        elements.append(ScreenplayElement(
                            element_type="parenthetical",
                            text=dial_line[1:-1],
                        ))
                    else:
                        elements.append(ScreenplayElement(
                            element_type="dialogue",
                            text=dial_line,
                        ))
                    i += 1
                continue

            # Centered text
            if line.startswith(">") and line.endswith("<") and len(line) > 2:
                elements.append(ScreenplayElement(
                    element_type="centered",
                    text=line[1:-1].strip(),
                ))
                i += 1
                continue

            # Section (#)
            if line.startswith("#") and len(line) > 1 and line[1:].startswith(" "):
                elements.append(ScreenplayElement(
                    element_type="section",
                    text=line.lstrip("#").strip(),
                ))
                i += 1
                continue

            # Synopsis (=)
            if line.startswith("=") and len(line) > 1 and line[1:].startswith(" "):
                elements.append(ScreenplayElement(
                    element_type="synopsis",
                    text=line[1:].strip(),
                ))
                i += 1
                continue

            # Lyric (~)
            if line.startswith("~") and len(line) > 1:
                elements.append(ScreenplayElement(
                    element_type="lyric",
                    text=line[1:].strip(),
                ))
                i += 1
                continue

            # Page break (===)
            if line.strip() == "===":
                elements.append(ScreenplayElement(
                    element_type="page_break",
                    text="===",
                ))
                i += 1
                continue

            # Forced scene heading (.TEXT)
            if line.startswith(".") and len(line) > 1 and line[1].isupper():
                elements.append(ScreenplayElement(
                    element_type="scene_heading",
                    text=line[1:].strip(),
                ))
                i += 1
                continue

            # Forced action (!TEXT)
            if line.startswith("!") and len(line) > 1 and line[1].isupper():
                elements.append(ScreenplayElement(
                    element_type="action",
                    text=line[1:].strip(),
                ))
                i += 1
                continue

            # Forced character (@TEXT)
            if line.startswith("@") and len(line) > 1 and line[1].isupper():
                elements.append(ScreenplayElement(
                    element_type="character",
                    text=line[1:].strip(),
                ))
                i += 1
                continue

            # Check for transition
            if line.upper().endswith("TO:") or line.upper() == "FADE IN:":
                elements.append(ScreenplayElement(
                    element_type="transition",
                    text=line,
                ))
                i += 1
                continue

            # Default: action line
            elements.append(ScreenplayElement(
                element_type="action",
                text=line,
            ))
            i += 1

    return elements


def generate_fountain(screenplay: Screenplay) -> str:
    """Convert a Screenplay object to Fountain markup text.

    Produces valid Fountain 1.1 markup with title page, scene headings,
    action, character cues, dialogue, parentheticals, and transitions.

    Args:
        screenplay: The screenplay data model to convert.

    Returns:
        A string containing the complete Fountain markup text.
        Returns empty string for a screenplay with no content.

    Example:
        >>> from cosmic_script.models import Screenplay, ScreenplayElement
        >>> sp = Screenplay(
        ...     title="My Movie",
        ...     author="Me",
        ...     elements=[ScreenplayElement(element_type="scene_heading",
        ...                 text="INT. HOUSE - DAY")],
        ... )
        >>> text = generate_fountain(sp)
        >>> "INT. HOUSE - DAY" in text
        True
    """
    parts: list[str] = []

    # --- Title page ---
    title_lines: list[str] = []
    if screenplay.title:
        title_lines.append(f"Title: {screenplay.title}")
    if screenplay.author:
        title_lines.append(f"Author: {screenplay.author}")
    if title_lines:
        parts.append("\n".join(title_lines))

    # --- Content elements ---
    # If we have scenes but no elements, convert scenes to elements
    elements = screenplay.elements
    if not elements and screenplay.scenes:
        elements = _scenes_to_elements(screenplay.scenes)

    element_lines: list[str] = []
    prev_type: str | None = None

    for element in elements:
        text = element.text.strip()
        if not text:
            continue

        et = element.element_type

        if et == "scene_heading":
            # Blank line before scene heading (unless it's the first element
            # after the title page)
            _ensure_trailing_blank_line(element_lines)
            element_lines.append(text)
            _ensure_trailing_blank_line(element_lines)

        elif et == "action":
            # Blank line between character/dialogue and action
            if prev_type in (
                "character",
                "dialogue",
                "parenthetical",
                "action",
                "transition",
            ):
                _ensure_trailing_blank_line(element_lines)
            element_lines.append(text)

        elif et == "character":
            # Blank line before character (unless preceded by scene heading)
            if prev_type is not None and prev_type != "scene_heading":
                _ensure_trailing_blank_line(element_lines)
            element_lines.append(text.upper())

        elif et == "dialogue":
            # Indent dialogue under character
            element_lines.append(f"\t{text}")

        elif et == "parenthetical":
            # Indent parenthetical under character
            element_lines.append(f"\t({text})")

        elif et == "transition":
            # Blank line before and after transition
            _ensure_trailing_blank_line(element_lines)
            t = text.upper().rstrip(".")
            if not t.endswith("TO:"):
                t = t.rstrip(":") + " TO:"
            element_lines.append(t)
            _ensure_trailing_blank_line(element_lines)

        elif et == "centered":
            # Centered text: >text<
            _ensure_trailing_blank_line(element_lines)
            element_lines.append(f">{text}<")

        elif et == "section":
            # Section heading: # text
            _ensure_trailing_blank_line(element_lines)
            element_lines.append(f"# {text}")

        elif et == "synopsis":
            # Synopsis: = text
            _ensure_trailing_blank_line(element_lines)
            element_lines.append(f"= {text}")

        elif et == "lyric":
            # Lyric: ~text
            element_lines.append(f"~{text}")

        elif et == "page_break":
            # Page break: ===
            _ensure_trailing_blank_line(element_lines)
            element_lines.append("===")
            _ensure_trailing_blank_line(element_lines)

        prev_type = et

    if element_lines:
        parts.append("\n".join(element_lines))

    result = "\n\n".join(parts).strip()
    return result


def _ensure_trailing_blank_line(lines: list[str]) -> None:
    """Ensure the list ends with exactly one blank line.

    Appends an empty string if the last entry is not already empty.

    Args:
        lines: The list of text lines to check and potentially append to.
    """
    if not lines:
        lines.append("")
    elif lines[-1] != "":
        lines.append("")
