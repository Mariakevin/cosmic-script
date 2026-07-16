"""Tests for the script coverage module.

Uses ``model="demo"`` to bypass LLM calls and return deterministic
placeholder coverage.
"""

import json
from unittest.mock import ANY, MagicMock, patch

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.analysis.coverage import (
    ScriptCoverage,
    generate_coverage,
    _parse_coverage_response,
    _clamp_rating,
    _normalize_recommendation,
)


class TestScriptCoverageDataclass:
    """Test suite for the ScriptCoverage data model."""

    def test_default_values(self):
        """ScriptCoverage has sensible defaults."""
        sc = ScriptCoverage()
        assert sc.logline == ""
        assert sc.synopsis == ""
        assert sc.strengths == []
        assert sc.weaknesses == []
        assert sc.rating == 5
        assert sc.recommendation == "Consider"
        assert sc.model_used == ""

    def test_custom_values(self):
        """ScriptCoverage stores custom values."""
        sc = ScriptCoverage(
            logline="A hero saves the day.",
            synopsis="The story of a hero.",
            strengths=["Strong characters"],
            weaknesses=["Weak pacing"],
            rating=7,
            recommendation="Strong Consider",
            genre="Action",
            target_audience="Adults",
            model_used="test-model",
        )
        assert sc.logline == "A hero saves the day."
        assert sc.rating == 7
        assert sc.recommendation == "Strong Consider"
        assert sc.model_used == "test-model"


class TestClampRating:
    """Test suite for _clamp_rating()."""

    def test_clamp_rating_in_range(self):
        """Rating within 1-10 stays unchanged."""
        assert _clamp_rating(5) == 5
        assert _clamp_rating(1) == 1
        assert _clamp_rating(10) == 10

    def test_clamp_rating_below_min(self):
        """Rating below 1 is clamped to 1."""
        assert _clamp_rating(0) == 1
        assert _clamp_rating(-5) == 1

    def test_clamp_rating_above_max(self):
        """Rating above 10 is clamped to 10."""
        assert _clamp_rating(11) == 10
        assert _clamp_rating(100) == 10

    def test_clamp_rating_invalid(self):
        """Invalid rating defaults to 5."""
        assert _clamp_rating("bad") == 5
        assert _clamp_rating(None) == 5


class TestNormalizeRecommendation:
    """Test suite for _normalize_recommendation()."""

    def test_valid_recommendations(self):
        """Valid recommendations pass through correctly."""
        assert _normalize_recommendation("Pass") == "Pass"
        assert _normalize_recommendation("Consider") == "Consider"
        assert _normalize_recommendation("Strong Consider") == "Strong Consider"

    def test_case_insensitive(self):
        """Case variations are normalized."""
        assert _normalize_recommendation("pass") == "Pass"
        assert _normalize_recommendation("STRONG CONSIDER") == "Strong Consider"

    def test_invalid_falls_back(self):
        """Invalid recommendation falls back to 'Consider'."""
        assert _normalize_recommendation("Buy") == "Consider"
        assert _normalize_recommendation("") == "Consider"
        assert _normalize_recommendation("Maybe") == "Consider"


class TestParseCoverageResponse:
    """Test suite for _parse_coverage_response()."""

    def test_happy_path_parse_valid_json(self):
        """Valid JSON is parsed correctly."""
        raw = json.dumps({
            "logline": "A detective solves a case.",
            "synopsis": "A detective story.",
            "strengths": ["Good dialogue"],
            "weaknesses": ["Slow pacing"],
            "rating": 7,
            "recommendation": "Consider",
            "genre": "Thriller",
            "target_audience": "Adults",
        })
        result = _parse_coverage_response(raw, "test-model")
        assert result.logline == "A detective solves a case."
        assert result.rating == 7
        assert result.recommendation == "Consider"
        assert result.model_used == "test-model"

    def test_parse_with_markdown_fences(self):
        """JSON wrapped in markdown fences is parsed correctly."""
        raw = """```json
{
    "logline": "A hero rises.",
    "synopsis": "Hero story.",
    "strengths": ["Action"],
    "weaknesses": ["Length"],
    "rating": 6,
    "recommendation": "Consider",
    "genre": "Action",
    "target_audience": "Teens"
}
```"""
        result = _parse_coverage_response(raw, "m")
        assert result.logline == "A hero rises."

    def test_parse_with_json_language_tag(self):
        """Fence with 'json' language tag is parsed."""
        raw = """```json
{"logline": "Test.", "synopsis": "Test.", "strengths": [], "weaknesses": [], "rating": 5, "recommendation": "Pass", "genre": "", "target_audience": ""}
```"""
        result = _parse_coverage_response(raw, "m")
        assert result.logline == "Test."

    def test_parse_invalid_json_fallback(self):
        """Invalid JSON returns partial coverage with error."""
        raw = "This is not JSON at all."
        result = _parse_coverage_response(raw, "test-model")
        assert result.logline == "(coverage generation failed)"
        assert len(result.weaknesses) >= 1
        assert "JSON parse error" in result.weaknesses[0]
        assert result.model_used == "test-model"

    def test_partial_json_uses_fallbacks(self):
        """Partial JSON uses defaults for missing fields."""
        raw = '{"logline": "Only a logline."}'
        result = _parse_coverage_response(raw, "m")
        assert result.logline == "Only a logline."
        assert result.synopsis == ""
        assert result.rating == 5
        assert result.recommendation == "Consider"


class TestGenerateCoverageDemo:
    """Test suite for generate_coverage() with model='demo'."""

    def test_demo_mode_returns_placeholder(self):
        """Demo mode returns hardcoded placeholder coverage."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
            ],
        )
        result = generate_coverage(screenplay, model="demo")
        assert isinstance(result, ScriptCoverage)
        assert result.logline == "A logline for the screenplay."
        assert result.model_used == "demo"
        assert len(result.strengths) >= 3
        assert len(result.weaknesses) >= 3

    def test_empty_screenplay_returns_empty_coverage(self):
        """Empty screenplay returns early with empty-coverage message."""
        screenplay = Screenplay()
        result = generate_coverage(screenplay, model="demo")
        assert result.logline == "(empty screenplay)"
        assert result.rating == 1
        assert result.recommendation == "Pass"


class TestGenerateCoverageMocked:
    """Test suite for generate_coverage() with mocked LLM."""

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_happy_path_mocked_llm(self, mock_get_router):
        """Mocked LLM returns parsed coverage."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (
            json.dumps({
                "logline": "A detective solves a mystery.",
                "synopsis": "A detective story with twists.",
                "strengths": ["Good dialogue", "Strong plot", "Great characters"],
                "weaknesses": ["Slow start", "Weak ending"],
                "rating": 7,
                "recommendation": "Consider",
                "genre": "Mystery",
                "target_audience": "Mystery fans",
            }),
            "test-model",
        )
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            title="Mystery",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="action", text="A room."),
                ScreenplayElement(element_type="character", text="DETECTIVE"),
                ScreenplayElement(element_type="dialogue", text="I solve cases."),
            ],
        )
        result = generate_coverage(screenplay, model="gemini/gemini-2.5-flash")
        assert result.logline == "A detective solves a mystery."
        assert result.rating == 7
        assert result.model_used == "test-model"
        assert len(result.strengths) == 3

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_mocked_llm_failure(self, mock_get_router):
        """LLM failure returns partial coverage with error info."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.side_effect = Exception("API error")
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="action", text="Something happens."),
            ],
        )
        result = generate_coverage(screenplay, model="gemini/gemini-2.5-flash")
        assert result.logline == "(coverage generation failed)"
        assert any("API error" in w for w in result.weaknesses)

    @patch("cosmic_script.conversion.model_router.get_router")
    def test_mocked_llm_sets_api_key(self, mock_get_router):
        """API key override is passed to the router."""
        mock_router = MagicMock()
        mock_router.call_with_fallback.return_value = (
            json.dumps({
                "logline": "Test.",
                "synopsis": "Test.",
                "strengths": [],
                "weaknesses": [],
                "rating": 5,
                "recommendation": "Pass",
                "genre": "",
                "target_audience": "",
            }),
            "test-model",
        )
        mock_get_router.return_value = mock_router

        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Action."),
            ],
        )
        generate_coverage(screenplay, model="test-model", api_key="test-key")
        assert mock_router.api_key == "test-key"
