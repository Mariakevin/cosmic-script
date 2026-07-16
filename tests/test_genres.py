"""Tests for the genre/tone control module."""

import pytest

from cosmic_script.conversion.genres import GenreStyle, get_genre_style, list_genres


class TestGenreStyle:
    """Coverage: happy-path, invariant, boundary."""

    def test_minimal_genre_style(self) -> None:
        """Happy-path: create GenreStyle with only required fields."""
        g = GenreStyle(name="test", description="A test genre")
        assert g.name == "test"
        assert g.description == "A test genre"
        assert g.scene_length == "medium"
        assert g.dialogue_ratio == "balanced"

    def test_full_genre_style(self) -> None:
        """Happy-path: create GenreStyle with all fields."""
        g = GenreStyle(
            name="full",
            description="Full test",
            scene_length="short",
            dialogue_ratio="high",
            transition_style="heavy",
            parenthetical_guidance="frequent",
            action_style="cinematic",
            prompt_addition="Extra guidance text.",
        )
        assert g.scene_length == "short"
        assert g.dialogue_ratio == "high"
        assert g.transition_style == "heavy"
        assert g.parenthetical_guidance == "frequent"
        assert g.action_style == "cinematic"
        assert g.prompt_addition == "Extra guidance text."


class TestGetGenreStyle:
    """Coverage: happy-path, invariant, boundary, input-variation."""

    def test_classic_default(self) -> None:
        """Happy-path: default genre returns classic style."""
        style = get_genre_style(None)
        assert style.name == "classic"
        assert "balanced" in style.description.lower()

    def test_classic_explicit(self) -> None:
        """Happy-path: 'classic' genre returns classic style."""
        style = get_genre_style("classic")
        assert style.name == "classic"

    def test_action_genre(self) -> None:
        """Input-variation: action genre returns action style."""
        style = get_genre_style("action")
        assert style.name == "action"
        assert style.scene_length == "short"
        assert style.dialogue_ratio == "low"

    def test_noir_genre(self) -> None:
        """Input-variation: noir genre returns noir style."""
        style = get_genre_style("noir")
        assert style.name == "noir"
        assert style.action_style == "cinematic"

    def test_comedy_genre(self) -> None:
        """Input-variation: comedy genre returns comedy style."""
        style = get_genre_style("comedy")
        assert style.name == "comedy"
        assert style.scene_length == "short"
        assert style.transition_style == "heavy"

    def test_horror_genre(self) -> None:
        """Input-variation: horror genre returns horror style."""
        style = get_genre_style("horror")
        assert style.name == "horror"
        assert style.dialogue_ratio == "low"

    def test_tarantino_genre(self) -> None:
        """Input-variation: tarantino genre returns tarantino style."""
        style = get_genre_style("tarantino")
        assert style.name == "tarantino"
        assert style.scene_length == "long"

    def test_drama_genre(self) -> None:
        """Input-variation: drama genre returns drama style."""
        style = get_genre_style("drama")
        assert style.name == "drama"
        assert style.dialogue_ratio == "balanced"

    def test_modern_genre(self) -> None:
        """Input-variation: modern genre returns modern style."""
        style = get_genre_style("modern")
        assert style.name == "modern"
        assert style.transition_style == "heavy"

    def test_unknown_genre_falls_back_to_classic(self) -> None:
        """Boundary: unknown genre name returns classic."""
        style = get_genre_style("nonexistent")
        assert style.name == "classic"

    def test_empty_string_genre_returns_classic(self) -> None:
        """Boundary: empty string returns classic."""
        style = get_genre_style("")
        assert style.name == "classic"

    def test_case_insensitive(self) -> None:
        """Invariant: genre lookup is case-insensitive."""
        style1 = get_genre_style("ACTION")
        style2 = get_genre_style("action")
        style3 = get_genre_style("Action")
        assert style1.name == "action"
        assert style1 == style2
        assert style1 == style3

    def test_all_genres_have_prompt_addition(self) -> None:
        """Invariant: every preset genre has prompt_addition text."""
        for name in ["classic", "modern", "tarantino", "noir", "comedy", "horror", "action", "drama"]:
            style = get_genre_style(name)
            assert style.prompt_addition, f"Genre '{name}' is missing prompt_addition"


class TestListGenres:
    """Coverage: happy-path, invariant."""

    def test_list_genres_returns_all(self) -> None:
        """Happy-path: list_genres returns all 8 genres."""
        genres = list_genres()
        assert len(genres) == 8

    def test_list_genres_has_names_and_descriptions(self) -> None:
        """Invariant: each genre entry has name and description keys."""
        genres = list_genres()
        for g in genres:
            assert "name" in g
            assert "description" in g
            assert g["name"]
            assert g["description"]

    def test_list_genres_includes_classic(self) -> None:
        """Happy-path: classic is in the list."""
        names = [g["name"] for g in list_genres()]
        assert "classic" in names


class TestBuildUserPromptGenre:
    """Coverage: genre integration with build_user_prompt."""

    def test_genre_in_prompt(self) -> None:
        """Happy-path: genre parameter adds genre guidance to prompt."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=1,
            chapter_text="Test.",
            genre="action",
        )
        assert "Genre:" in result
        assert "action" in result.lower()

    def test_no_genre_no_additions(self) -> None:
        """Boundary: no genre does not add genre section."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=1,
            chapter_text="Test.",
        )
        assert "Genre Guidance" not in result

    def test_genre_with_title_and_tone(self) -> None:
        """Happy-path: genre combines with title and tone."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=2,
            chapter_text="Test.",
            title="My Film",
            tone="dark",
            genre="noir",
        )
        assert "Title: My Film" in result
        assert "Tone: dark" in result
        assert "Genre:" in result
        assert "Chapter 2:" in result
