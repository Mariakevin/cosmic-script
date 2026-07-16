"""Tests for the logline generator module.

Uses ``model="demo"`` to bypass LLM calls and return a deterministic
placeholder logline.
"""

from unittest.mock import MagicMock, patch

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.analysis.logline import generate_logline


class TestGenerateLoglineDemo:
    """Test suite for generate_logline() with model='demo'."""

    def test_demo_mode_returns_placeholder(self):
        """Demo mode returns a hardcoded placeholder logline."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
            ],
        )
        result = generate_logline(screenplay, model="demo")
        assert isinstance(result, str)
        assert len(result) > 10
        assert "detective" in result.lower() or "clues" in result.lower()

    def test_empty_screenplay_returns_empty_message(self):
        """Empty screenplay returns a descriptive message."""
        screenplay = Screenplay()
        result = generate_logline(screenplay, model="demo")
        assert result == "(empty screenplay)"

    def test_demo_logline_length(self):
        """Demo logline is within reasonable length."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="action", text="Something happens."),
            ],
        )
        result = generate_logline(screenplay, model="demo")
        # Should be a reasonable logline length
        assert 20 <= len(result) <= 200


class TestGenerateLoglineMocked:
    """Test suite for generate_logline() with mocked LLM."""

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_happy_path_mocked_llm(self, mock_get_router):
        """Mocked LLM returns logline correctly."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (
            "A small-town sheriff must uncover the truth before time runs out.",
            "test-model",
        )
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            title="Western",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="EXT. TOWN - DAY"),
                ScreenplayElement(element_type="action", text="A dusty town."),
                ScreenplayElement(element_type="character", text="SHERIFF"),
                ScreenplayElement(element_type="dialogue", text="This town ain't big enough."),
            ],
        )
        result = generate_logline(screenplay, model="gemini/gemini-2.5-flash")
        assert "sheriff" in result.lower()
        assert len(result) > 10

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_mocked_llm_failure(self, mock_get_router):
        """LLM failure returns error message."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.side_effect = Exception("API error")
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="action", text="A scene."),
            ],
        )
        result = generate_logline(screenplay, model="gemini/gemini-2.5-flash")
        assert "logline generation failed" in result

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_mocked_llm_sets_api_key(self, mock_get_router):
        """API key is passed to router when provided."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (
            "A logline.",
            "test-model",
        )
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Do stuff."),
            ],
        )
        generate_logline(screenplay, model="test-model", api_key="custom-key")
        assert mock_router.api_key == "custom-key"

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_logline_truncated_to_50_words(self, mock_get_router):
        """Overly long logline is truncated to 50 words."""
        long_logline = " ".join(["word"] * 60)
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (long_logline, "test-model")
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Scene."),
            ],
        )
        result = generate_logline(screenplay, model="gemini/gemini-2.5-flash")
        words = result.split()
        assert len(words) <= 51  # Allow for period

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_logline_quotes_stripped(self, mock_get_router):
        """Surrounding quotes are stripped from response."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (
            '"A hero saves the day."',
            "test-model",
        )
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Scene."),
            ],
        )
        result = generate_logline(screenplay, model="gemini/gemini-2.5-flash")
        assert not result.startswith('"')
        assert not result.endswith('"')


class TestGenerateLoglineEdgeCases:
    """Edge-case tests for generate_logline()."""

    def test_single_element_screenplay(self):
        """Single-element screenplay works with demo mode."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. VOID - NIGHT"),
            ],
        )
        result = generate_logline(screenplay, model="demo")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_screenplay_with_elements_only(self):
        """Screenplay with only elements works."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="character", text="BOB"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
            ],
        )
        result = generate_logline(screenplay, model="demo")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_screenplay_with_scenes(self):
        """Screenplay populated via scenes works."""
        from cosmic_script.models import Scene
        screenplay = Screenplay(
            title="Scene Test",
            scenes=[
                Scene(heading="INT. HOUSE - DAY", content="A house.\n\nJOHN\nHi."),
            ],
        )
        result = generate_logline(screenplay, model="demo")
        assert isinstance(result, str)
        assert len(result) > 0
