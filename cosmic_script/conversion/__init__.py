"""Screenplay conversion — AI-powered screenplay generation.

Public API:
    - ScreenplayConverter — main conversion class
    - convert() / convert_file() — pipeline entry points
    - ModelRouter — multi-provider model fallback
    - ConversionCache — content-hash LLM cache
    - GenreStyle / get_genre_style() / list_genres() — genre presets
"""

from __future__ import annotations

from cosmic_script.conversion.converter import (
    ConversionConfig,
    ScreenplayConverter,
)
from cosmic_script.conversion.pipeline import convert, convert_file
from cosmic_script.conversion.model_router import ModelRouter, get_router
from cosmic_script.conversion.cache import ConversionCache
from cosmic_script.conversion.genres import GenreStyle, get_genre_style, list_genres

__all__ = [
    "ConversionConfig",
    "ScreenplayConverter",
    "convert",
    "convert_file",
    "ModelRouter",
    "get_router",
    "ConversionCache",
    "GenreStyle",
    "get_genre_style",
    "list_genres",
]
