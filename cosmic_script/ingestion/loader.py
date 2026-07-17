"""Unified document loader — reads .txt, .md, .pdf, .epub, .docx, .fdx into plain text."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

try:
    import chardet
except ImportError:
    chardet = None  # type: ignore


def load_document(filepath: str) -> str:
    """Detect file extension and load the document as plain text.

    Supports:
        - .txt  — read directly
        - .md   — strip Markdown syntax
        - .pdf  — extract text via PyMuPDF (``fitz``)
        - .epub — extract text via ``ebooklib`` + ``BeautifulSoup``
        - .docx — extract text via ``mammoth``
        - .fdx  — extract text via ``screenplay-tools`` FDX.Parser

    Args:
        filepath: Path to the source document.

    Returns:
        Plain-text content of the document.

    Raises:
        FileNotFoundError: The file does not exist.
        ValueError: Unsupported file extension.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = path.suffix.lower()

    if ext == ".txt":
        return _load_txt(path)
    elif ext == ".md":
        return _load_md(path)
    elif ext == ".pdf":
        return _load_pdf(path)
    elif ext == ".epub":
        return _load_epub(path)
    elif ext == ".docx":
        return _load_docx(path)
    elif ext == ".fdx":
        return _load_fdx(path)
    else:
        raise ValueError(
            f"Unsupported file extension: '{ext}' — expected .txt, .md, .pdf, .epub, .docx, or .fdx"
        )


# ── Internal loaders ────────────────────────────────────────


def _load_txt(path: Path) -> str:
    """Read a plain-text file with encoding detection."""
    # Try UTF-8 first (most common)
    try:
        return path.read_text(encoding="utf-8").lstrip("\ufeff")
    except UnicodeDecodeError:
        pass
    # If chardet available, detect encoding
    if chardet is not None:
        raw = path.read_bytes()
        detection = chardet.detect(raw)
        if detection and detection.get("encoding"):
            try:
                return raw.decode(detection["encoding"]).lstrip("\ufeff")
            except (UnicodeDecodeError, LookupError):
                pass
    # Fallback to latin-1 (never fails)
    return path.read_bytes().decode("latin-1").lstrip("\ufeff")


def _load_md(path: Path) -> str:
    """Read a Markdown file and strip common formatting syntax."""
    text = path.read_text(encoding="utf-8")

    # Remove fenced code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove image tags  ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Remove links [text](url) — keep only the text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove Markdown heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers ** ** or __ __ or * * or _ _
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    # Remove table rows (lines containing | used as separators)
    text = re.sub(r"^[|\s:-]+$", "", text, flags=re.MULTILINE)
    # Remove list markers (-, *, +, 1.)
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    return text.strip()


def _load_pdf(path: Path) -> str:
    """Extract text from a PDF using PyMuPDF (``fitz``)."""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise ImportError(
            "PyMuPDF is required to load PDF files. Install it with: pip install pymupdf"
        )

    doc = fitz.open(str(path))
    pages: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages).strip()


def _load_epub(path: Path) -> str:
    """Extract text from an EPUB using ``ebooklib`` and ``xml.etree``."""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        raise ImportError(
            "ebooklib is required to load EPUB files. Install it with: pip install ebooklib"
        )

    book = epub.read_epub(str(path))
    items = list(book.get_items())

    text_parts: list[str] = []
    for item in items:
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_body_content()
            if content:
                # Strip HTML tags for plain text
                decoded = content.decode("utf-8", errors="replace")
                plain = re.sub(r"<[^>]+>", "", decoded)
                plain = re.sub(r"\s+", " ", plain).strip()
                if plain:
                    text_parts.append(plain)

    return "\n\n".join(text_parts).strip()


def _load_docx(path: Path) -> str:
    """Extract text from a DOCX file using ``mammoth``.

    Mammoth converts DOCX to clean HTML, then strips tags for plain text.
    Preserves paragraph structure by converting ``<p>`` tags to newlines.
    """
    try:
        import mammoth
    except ImportError:
        raise ImportError(
            "mammoth is required to load DOCX files. Install it with: pip install mammoth"
        )

    with open(path, "rb") as f:
        result = mammoth.convert_to_markdown(f)

    text = result.value
    # Clean up markdown artifacts from mammoth conversion
    # Remove bold/italic markers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Remove heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove image tags
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Remove links — keep text only
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    return text.strip()


def _load_fdx(path: Path) -> str:
    """Extract text from an FDX file using ``screenplay-tools`` FDX.Parser.

    Parses the Final Draft XML and converts elements to a readable
    Fountain-like plain-text format with scene headings, character names,
    dialogue, and action lines.
    """
    try:
        from screenplay_tools.fdx.parser import Parser
        from screenplay_tools.screenplay import ElementType as StElementType
    except ImportError:
        raise ImportError(
            "screenplay-tools is required to load FDX files. "
            "Install it with: pip install screenplay-tools"
        )

    xml_content = path.read_text(encoding="utf-8")
    parser = Parser()
    script = parser.parse(xml_content)

    lines: list[str] = []
    for element in script.elements:
        et = element.type
        text = element.text if hasattr(element, "text") else ""

        if et == StElementType.HEADING:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text)
            lines.append("")
        elif et == StElementType.ACTION:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text)
        elif et == StElementType.CHARACTER:
            if lines and lines[-1] != "":
                lines.append("")
            name = element.name if hasattr(element, "name") else text
            if hasattr(element, "extension") and element.extension:
                name += f" ({element.extension})"
            lines.append(name)
        elif et == StElementType.DIALOGUE:
            lines.append(f"    {text}")
        elif et == StElementType.PARENTHETICAL:
            ptext = text.strip()
            if not ptext.startswith("("):
                ptext = f"({ptext})"
            lines.append(f"    {ptext}")
        elif et == StElementType.TRANSITION:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(text.upper())
            lines.append("")

    return "\n".join(lines).strip()
