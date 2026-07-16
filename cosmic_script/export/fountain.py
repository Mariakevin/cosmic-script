"""Fountain format generator for cosmic-script.

Converts a Screenplay object into standard Fountain markup text
following the Fountain 1.1 specification conventions.
"""

from __future__ import annotations

from screenplay_tools.fountain.parser import Parser as FountainParser
from screenplay_tools.fountain.parser import (
    ElementType as StElementType,
    SceneHeading as StSceneHeading,
    Action as StAction,
    Character as StCharacter,
    Dialogue as StDialogue,
    Transition as StTransition,
    Parenthetical as StParenthetical,
)

from cosmic_script.models import Screenplay, Scene, ScreenplayElement


def _scenes_to_elements(scenes: list[Scene]) -> list[ScreenplayElement]:
    """Convert a list of Scene objects to ScreenplayElement objects.

    Uses ``screenplay-tools`` for spec-compliant Fountain parsing, then
    maps the parsed elements to our internal ``ScreenplayElement`` model.

    Args:
        scenes: List of Scene objects from the conversion pipeline.

    Returns:
        A list of ScreenplayElement objects for Fountain export.
    """
    elements: list[ScreenplayElement] = []

    # Map screenplay-tools ElementType to our element_type strings
    _TYPE_MAP = {
        StElementType.HEADING: "scene_heading",
        StElementType.ACTION: "action",
        StElementType.CHARACTER: "character",
        StElementType.DIALOGUE: "dialogue",
        StElementType.PARENTHETICAL: "parenthetical",
        StElementType.TRANSITION: "transition",
        StElementType.LYRIC: "lyric",
        StElementType.PAGEBREAK: "page_break",
        StElementType.SECTION: "section",
        StElementType.SYNOPSIS: "synopsis",
    }

    for scene in scenes:
        try:
            parser = FountainParser()
            parser.add_text(scene.content)
            script = parser.script

            if script and script.elements:
                for el in script.elements:
                    et = _TYPE_MAP.get(el.type)
                    if et is None:
                        continue  # Skip TITLEENTRY, NOTE, BONEYARD

                    # Extract text — Character uses .name, others use ._text
                    if isinstance(el, StCharacter):
                        text = el.name
                        if el.extension:
                            text += f" ({el.extension})"
                    else:
                        text = getattr(el, "_text", "")

                    # Centered action
                    if isinstance(el, StAction) and el.centered:
                        et = "centered"

                    if text:
                        elements.append(ScreenplayElement(
                            element_type=et,
                            text=text.strip(),
                        ))
                continue  # Scene parsed successfully
        except Exception:
            pass  # Fall through to manual parsing

        # Fallback: manual parsing for scenes that screenplay-tools can't handle
        elements.append(ScreenplayElement(
            element_type="scene_heading",
            text=scene.heading,
        ))

        lines = scene.content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith(("INT.", "EXT.", "INT/EXT.", "I/E.")):
                i += 1
                continue
            # Character cue
            if line.isupper() and len(line) <= 20 and not line.startswith("FADE"):
                elements.append(ScreenplayElement(
                    element_type="character",
                    text=line,
                ))
                i += 1
                while i < len(lines):
                    dial_line = lines[i].strip()
                    if not dial_line:
                        i += 1
                        continue
                    if (dial_line.isupper() and len(dial_line) <= 20) or \
                       dial_line.startswith(("INT.", "EXT.", "INT/EXT.", "I/E.")):
                        break
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
            # Transition
            if line.upper().endswith("TO:") or line.upper() == "FADE IN:":
                elements.append(ScreenplayElement(
                    element_type="transition",
                    text=line,
                ))
                i += 1
                continue
            # Default: action
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
