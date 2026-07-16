"""Chapter extraction and listing routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cosmic_script.web.schemas import ChaptersResponse, ChapterResponse, ErrorResponse
from cosmic_script.ingestion.chapterizer import split_into_chapters

router = APIRouter(tags=["chapters"])


class ChaptersRequest(BaseModel):
    """Request body for chapter extraction."""

    text: str


@router.post(
    "/chapters",
    response_model=ChaptersResponse,
    responses={400: {"model": ErrorResponse}},
)
async def extract_chapters(request: ChaptersRequest):
    """Extract chapters from text content.

    Analyzes the text and splits it into chapters based on headings.
    Returns chapter list with preview text (first 500 chars).
    """
    if not request.text.strip():
        return ChaptersResponse(chapters=[])

    chapters = split_into_chapters(request.text)

    return ChaptersResponse(
        chapters=[
            ChapterResponse(
                number=ch.number,
                title=ch.title,
                text_preview=ch.text[:500] + "..." if len(ch.text) > 500 else ch.text,
            )
            for ch in chapters
        ]
    )
