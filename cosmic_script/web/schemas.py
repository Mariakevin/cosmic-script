"""Pydantic request/response models for the FastAPI web layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Error ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Standard error payload returned on failures."""

    error: str
    detail: str | None = None
    line: int | None = None


# ── Upload / Document ────────────────────────────────────────────────────────


class UploadResponse(BaseModel):
    """Response after uploading a document."""

    filename: str
    text: str
    word_count: int
    char_count: int
    char_count_no_spaces: int


# ── Chapters ─────────────────────────────────────────────────────────────────


class ChapterResponse(BaseModel):
    """A single chapter preview returned to the client."""

    number: int
    title: str | None = None
    text_preview: str


class ChaptersResponse(BaseModel):
    """List of chapters for a document."""

    chapters: list[ChapterResponse]


# ── Conversion ───────────────────────────────────────────────────────────────


class ConvertRequest(BaseModel):
    """Request body for converting text to screenplay."""

    text: str
    title: str | None = None
    author: str | None = None
    model: str | None = None
    genre: str | None = None
    mode: str | None = Field(default="ai", description="Conversion mode: 'ai' or 'rules'")


class SceneResponse(BaseModel):
    """A single scene within a screenplay."""

    heading: str
    content: str


class ElementResponse(BaseModel):
    """A single structural element of a screenplay."""

    element_type: str = Field(alias="type")
    text: str

    class Config:
        populate_by_name = True


class ScreenplayResponse(BaseModel):
    """Full screenplay response with metadata and structural data."""

    title: str | None = None
    author: str | None = None
    scenes: list[SceneResponse] = Field(default_factory=list)
    elements: list[ElementResponse] = Field(default_factory=list)


# ── Export ───────────────────────────────────────────────────────────────────


class ExportRequest(BaseModel):
    """Request body for exporting a screenplay."""

    screenplay: ScreenplayResponse
    format: str


class ExportResponse(BaseModel):
    """Response containing exported screenplay content."""

    content: str
    format: str


# ── Validation ───────────────────────────────────────────────────────────────


class ValidationItem(BaseModel):
    """A single validation message."""

    line: int | None = None
    message: str
    severity: str  # "error" | "warning" | "info"
    code: str | None = None


class ValidationResponse(BaseModel):
    """Aggregated validation results."""

    errors: list[ValidationItem] = Field(default_factory=list)
    warnings: list[ValidationItem] = Field(default_factory=list)
    infos: list[ValidationItem] = Field(default_factory=list)


# ── Characters ───────────────────────────────────────────────────────────────


class CharacterResponse(BaseModel):
    """A character with aliases and appearance info."""

    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    first_appearance: str | None = None


class CharactersResponse(BaseModel):
    """List of extracted characters."""

    characters: list[CharacterResponse] = Field(default_factory=list)
