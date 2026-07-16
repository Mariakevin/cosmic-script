"""Character extraction and lookup routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from cosmic_script.web.schemas import CharactersResponse, CharacterResponse, ErrorResponse
from cosmic_script.conversion.registry import CharacterRegistry

router = APIRouter(tags=["characters"])


class CharactersRequest(BaseModel):
    """Request body for character extraction."""

    text: str


@router.post(
    "/characters",
    response_model=CharactersResponse,
)
async def extract_characters(request: CharactersRequest):
    """Extract character names from text.

    Uses fuzzy matching to identify and merge similar character names.
    """
    if not request.text.strip():
        return CharactersResponse(characters=[])

    registry = CharacterRegistry()
    registry.update_from_text(request.text, chapter_number=1)

    return CharactersResponse(
        characters=[
            CharacterResponse(
                canonical_name=char.canonical_name,
                aliases=list(char.aliases),
                first_appearance=str(char.first_appearance) if char.first_appearance else None,
            )
            for char in registry.characters.values()
        ]
    )
