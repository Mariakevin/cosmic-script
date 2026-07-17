"""Multi-format screenplay export.

Provides unified export functionality supporting Fountain, plain-text,
and FDX formats with automatic validation and fix-up of output.
"""

from __future__ import annotations

import os

from cosmic_script.models import Screenplay
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.validator import FountainValidator

# Supported export formats and their file extensions.
SUPPORTED_FORMATS: dict[str, str] = {
    "fountain": ".fountain",
    "txt": ".txt",
    "fdx": ".fdx",
}


def export_screenplay(
    screenplay: Screenplay,
    output_path: str,
    fmt: str = "fountain",
) -> str:
    """Export a Screenplay to the specified format and save to disk.

    The function generates the output text, validates it, applies automatic
    fixes for detected issues, and writes the final result to ``output_path``.
    Parent directories are created if they do not exist.

    Args:
        screenplay: The screenplay data model to export.
        output_path: Filesystem path where the output file will be written.
        fmt: Output format identifier. Supported values are ``"fountain"``
            (default), ``"txt"``, and ``"fdx"``.

    Returns:
        The absolute path to the saved file.

    Raises:
        ValueError: If ``fmt`` is not a supported format.

    Example:
        >>> from cosmic_script.models import Screenplay
        >>> sp = Screenplay(title="My Movie")
        >>> export_screenplay(sp, "/tmp/my_movie.fountain")
        '/tmp/my_movie.fountain'
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {fmt!r}. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )

    # Generate output text
    if fmt == "fountain":
        raw_text = generate_fountain(screenplay)
    elif fmt == "txt":
        raw_text = _generate_plain_text(screenplay)
    elif fmt == "fdx":
        raw_text = _generate_fdx(screenplay)
    else:
        raise ValueError(f"Unsupported format: {fmt!r}")

    # Validate and auto-fix
    if raw_text.strip():
        validator = FountainValidator()
        validation = validator.validate(raw_text)
        if not validation["valid"]:
            raw_text = validator.auto_fix(raw_text)

    # Ensure parent directory exists
    output_path = os.path.abspath(output_path)
    parent = os.path.dirname(output_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    return output_path


def _generate_plain_text(screenplay: Screenplay) -> str:
    """Generate a plain-text rendering of the screenplay.

    Produces a readable screenplay format without Fountain markup. Suitable
    for reading or printing as a simple document.

    Args:
        screenplay: The screenplay data model.

    Returns:
        Plain-text string representation of the screenplay.
    """
    lines: list[str] = []

    # Header
    if screenplay.title:
        lines.append(screenplay.title)
        lines.append("=" * len(screenplay.title))
        lines.append("")
    if screenplay.author:
        lines.append(f"By {screenplay.author}")
        lines.append("")

    # Elements
    prev_type: str | None = None
    for element in screenplay.elements:
        text = element.text.strip()
        if not text:
            continue

        et = element.element_type
        if et == "scene_heading":
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text.upper())
            lines.append("")
        elif et == "action":
            _ensure_trailing_blank_line(lines, prev_type)
            lines.append(text)
        elif et == "character":
            _ensure_trailing_blank_line(lines, prev_type)
            lines.append(text.upper())
        elif et == "dialogue":
            lines.append(f"    {text}")
        elif et == "parenthetical":
            lines.append(f"    ({text})")
        elif et == "transition":
            _ensure_trailing_blank_line(lines, prev_type)
            lines.append(text.upper())
            lines.append("")

        prev_type = et

    return "\n".join(lines).strip()


def _ensure_trailing_blank_line(lines: list[str], prev_type: str | None) -> None:
    """Append a blank line when needed between blocks.

    Args:
        lines: The output lines accumulated so far.
        prev_type: The element type of the preceding line, if any.
    """
    if lines and lines[-1] != "":
        lines.append("")


def _generate_fdx(screenplay: Screenplay) -> str:
    """Generate an FDX (Final Draft XML) representation of the screenplay.

    Uses the ``screenplay-tools`` FDX.Writer to produce spec-compliant FDX XML.
    Maps our internal ScreenplayElement types to screenplay-tools Script elements.

    Args:
        screenplay: The screenplay data model to export.

    Returns:
        FDX XML string.
    """
    from screenplay_tools.fdx.writer import Writer
    from screenplay_tools.screenplay import (
        Script as StScript,
        SceneHeading as StSceneHeading,
        Action as StAction,
        Character as StCharacter,
        Dialogue as StDialogue,
        Parenthetical as StParenthetical,
        Transition as StTransition,
    )

    script = StScript()

    # Add title entry if available
    if screenplay.title:
        from screenplay_tools.screenplay import TitleEntry

        script.titleEntries.append(TitleEntry("Title", screenplay.title))
    if screenplay.author:
        from screenplay_tools.screenplay import TitleEntry

        script.titleEntries.append(TitleEntry("Author", screenplay.author))

    # Map our element types to screenplay-tools elements
    _ELEMENT_MAP = {
        "scene_heading": lambda text: StSceneHeading(text),
        "action": lambda text: StAction(text),
        "character": lambda text: StCharacter(text.upper()),
        "dialogue": lambda text: StDialogue(text),
        "parenthetical": lambda text: StParenthetical(text),
        "transition": lambda text: StTransition(text),
    }

    for element in screenplay.elements:
        text = element.text.strip()
        if not text:
            continue

        et = (
            element.element_type.value
            if hasattr(element.element_type, "value")
            else element.element_type
        )
        factory = _ELEMENT_MAP.get(et)
        if factory:
            script.add_element(factory(text))

    writer = Writer()
    xml_output = writer.write(script)

    # screenplay-tools Writer ignores titleEntries; inject them manually
    title_entries: list[tuple[str, str]] = []
    if screenplay.title:
        title_entries.append(("Title", screenplay.title))
    if screenplay.author:
        title_entries.append(("Author", screenplay.author))
    if title_entries:
        import re as _re

        title_page_parts: list[str] = []
        for key, value in title_entries:
            title_page_parts.append(
                f"        <Paragraph Type=\"$Title\">"
                f"<Text>{value}</Text></Paragraph>"
            )
        title_page_xml = (
            "    <TitlePage>\n"
            "        <Content>\n"
            + "\n".join(title_page_parts)
            + "\n        </Content>\n"
            "    </TitlePage>"
        )
        # Insert TitlePage before <Content> or <Content/>
        xml_output = xml_output.replace(
            "    <Content", title_page_xml + "\n    <Content"
        )

    return xml_output
