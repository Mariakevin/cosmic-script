"""Screenplay export routes (Fountain, PDF, TXT)."""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from cosmic_script.web.schemas import (
    ExportRequest,
    ExportResponse,
    ValidationResponse,
    ValidationItem,
    ErrorResponse,
)
from cosmic_script.models import Screenplay, Scene, ScreenplayElement
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.validator import FountainValidator

router = APIRouter(tags=["export"])


def _response_to_screenplay(screenplay_data) -> Screenplay:
    """Convert API ScreenplayResponse back to internal Screenplay model."""
    return Screenplay(
        title=screenplay_data.title,
        author=screenplay_data.author,
        scenes=[
            Scene(heading=s.heading, content=s.content)
            for s in (screenplay_data.scenes or [])
        ],
        elements=[
                ScreenplayElement(element_type=e.element_type, text=e.text)
                for e in (screenplay_data.elements or [])
            ],
    )


@router.post("/export", response_model=ExportResponse)
async def export_screenplay(request: ExportRequest):
    """Export a screenplay to the specified format.

    Supports 'fountain' and 'txt' formats.
    """
    screenplay = _response_to_screenplay(request.screenplay)

    if request.format == "fountain":
        content = generate_fountain(screenplay)
        return ExportResponse(content=content, format="fountain")
    elif request.format == "txt":
        # Plain text export - just the Fountain content without title page
        content = generate_fountain(screenplay)
        # Remove title page if present
        if "\n\n" in content:
            content = content.split("\n\n", 1)[-1]
        return ExportResponse(content=content, format="txt")
    elif request.format == "pdf":
        # PDF export - generate in memory, return as base64
        try:
            from cosmic_script.export.pdf_export import ScreenplayPDF

            pdf = ScreenplayPDF()
            pdf.render_screenplay(screenplay)

            buf = io.BytesIO()
            pdf.output(buf)
            pdf_bytes = buf.getvalue()
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            return ExportResponse(content=pdf_b64, format="pdf")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"PDF export failed: {e}",
            )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format: {request.format}. Use 'fountain', 'txt', or 'pdf'.",
        )


@router.post("/validate", response_model=ValidationResponse)
async def validate_fountain(request: dict):
    """Validate Fountain text for structural correctness."""
    text = request.get("text", "")
    if not text.strip():
        return ValidationResponse()

    validator = FountainValidator()
    result = validator.validate(text)

    # Convert to response format
    errors = []
    warnings = []
    infos = []

    for item in result.get("errors", []):
        errors.append(
            ValidationItem(
                line=item.get("line"),
                message=item["message"],
                severity="error",
                code=item.get("code"),
            )
        )

    for item in result.get("warnings", []):
        warnings.append(
            ValidationItem(
                line=item.get("line"),
                message=item["message"],
                severity="warning",
                code=item.get("code"),
            )
        )

    for item in result.get("infos", []):
        infos.append(
            ValidationItem(
                line=item.get("line"),
                message=item["message"],
                severity="info",
                code=item.get("code"),
            )
        )

    return ValidationResponse(errors=errors, warnings=warnings, infos=infos)
