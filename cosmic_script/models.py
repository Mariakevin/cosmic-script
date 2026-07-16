"""Data models for cosmic-script screenplays."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ElementType(str, Enum):
    """Types of screenplay elements in Fountain format.

    Inherits from ``str`` so that ``ElementType.SCENE_HEADING == "scene_heading"``
    evaluates to ``True`` — preserving backward compatibility with code that
    compares against plain strings.
    """

    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    PARENTHETICAL = "parenthetical"
    TRANSITION = "transition"
    CENTERED = "centered"
    SECTION = "section"
    SYNOPSIS = "synopsis"
    LYRIC = "lyric"
    PAGE_BREAK = "page_break"


class Chapter(BaseModel):
    """A single chapter or section of a story.

    Attributes:
        number: Sequential chapter number (1-indexed).
        title: Optional chapter title (e.g. "The Beginning").
        text: Plain-text body of the chapter.
    """

    number: int
    title: Optional[str] = None
    text: str


class Scene(BaseModel):
    """A single scene within a screenplay.

    Attributes:
        heading: Scene heading (e.g. "INT. HOUSE - DAY").
        content: Fountain-format body of the scene.
    """

    heading: str
    content: str


class ScreenplayElement(BaseModel):
    """A single element in a screenplay.

    Attributes:
        element_type: Type of element (scene_heading, action, character,
            dialogue, parenthetical, transition, centered, section,
            synopsis, lyric, page_break).
        text: The text content of the element.
    """

    element_type: ElementType
    text: str


class Screenplay(BaseModel):
    """Represents a complete screenplay with metadata and structural elements.

    Attributes:
        title: The screenplay title (optional).
        author: The screenplay author (optional).
        scenes: List of Scene objects (for chapter-by-chapter conversion).
        elements: Ordered list of structural elements (for element-based export).
    """

    title: str | None = None
    author: str | None = None
    scenes: list[Scene] = Field(default_factory=list)
    elements: list[ScreenplayElement] = Field(default_factory=list)
