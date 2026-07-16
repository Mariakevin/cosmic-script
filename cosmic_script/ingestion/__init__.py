"""Text ingestion module — load and split documents."""

from cosmic_script.ingestion.loader import load_document
from cosmic_script.ingestion.chapterizer import split_into_chapters

__all__ = [
    "load_document",
    "split_into_chapters",
]
