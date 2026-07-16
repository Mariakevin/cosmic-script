"""Conversion pipeline - orchestrates ingestion, conversion, and export."""

from __future__ import annotations

from cosmic_script.models import Screenplay
from cosmic_script.ingestion.loader import load_document
from cosmic_script.ingestion.chapterizer import split_into_chapters
from cosmic_script.conversion.converter import ScreenplayConverter, ConversionConfig
from cosmic_script.export.fountain import generate_fountain


def convert(
    text: str,
    model: str = "auto",
    api_key: str | None = None,
    title: str = "Untitled",
    author: str = "Unknown",
    genre: str | None = None,
) -> Screenplay:
    """Convert text content to a Screenplay object.

    This is the main entry point for the conversion pipeline.

    Args:
        text: The raw text content to convert.
        model: LLM model name (default: ``"auto"`` = automatic fallback).
            Pass ``"demo"`` for mock output without API calls.
        api_key: API key for the LLM provider.
        title: Screenplay title.
        author: Screenplay author.
        genre: Genre preset key (e.g. ``"action"``, ``"noir"``).

    Returns:
        A Screenplay object with converted scenes.
    """
    config = ConversionConfig(model=model, api_key=api_key, genre=genre)
    converter = ScreenplayConverter(config)

    chapters = split_into_chapters(text)
    screenplay = converter.convert_novel(chapters, title=title, author=author)

    return screenplay


def convert_file(
    filepath: str,
    model: str = "auto",
    api_key: str | None = None,
    title: str | None = None,
    author: str = "Unknown",
    genre: str | None = None,
) -> tuple[Screenplay, str]:
    """Load a file and convert it to a screenplay.

    Args:
        filepath: Path to the input file.
        model: LLM model name.
        api_key: API key for the LLM provider.
        title: Screenplay title (derived from filename if None).
        author: Screenplay author.
        genre: Genre preset key (e.g. ``"action"``, ``"noir"``).

    Returns:
        Tuple of (Screenplay, Fountain text).
    """
    from pathlib import Path

    text = load_document(filepath)

    if title is None:
        path = Path(filepath)
        title = path.stem.replace("_", " ").replace("-", " ").strip().title()

    screenplay = convert(text, model=model, api_key=api_key, title=title, author=author, genre=genre)
    fountain_text = generate_fountain(screenplay)

    return screenplay, fountain_text
