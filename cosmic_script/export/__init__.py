"""Screenplay export to Fountain, plain-text, PDF, and validation.

Public API:
    - generate_fountain(screenplay) -> str
    - export_screenplay(screenplay, path, fmt) -> str
    - export_pdf(screenplay, path) -> str
    - estimate_pages(screenplay) -> PageEstimate
    - FountainValidator
"""

from __future__ import annotations

from cosmic_script.export.exporter import export_screenplay
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.page_estimator import PageEstimate, estimate_pages
from cosmic_script.export.pdf_export import export_pdf
from cosmic_script.export.validator import FountainValidator

__all__ = [
    "export_screenplay",
    "export_pdf",
    "generate_fountain",
    "estimate_pages",
    "FountainValidator",
    "PageEstimate",
]
