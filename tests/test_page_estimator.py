"""Tests for the screenplay page-count estimator."""

import pytest

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.export.page_estimator import estimate_pages, PageEstimate


class TestEstimatePages:
    """Test suite for estimate_pages()."""

    # --- Happy path ---

    def test_happy_path_simple_screenplay(self):
        """Screenplay with a few elements produces a positive page estimate."""
        screenplay = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - DAY"),
                ScreenplayElement(element_type="action", text="A quiet room with soft morning light filtering through the curtains."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Good morning."),
            ],
        )
        result = estimate_pages(screenplay)
        assert isinstance(result, PageEstimate)
        assert result.estimated_pages > 0
        assert result.total_lines > 0
        assert result.confidence in ("high", "medium", "low")

    def test_happy_path_with_breakdown(self):
        """Breakdown dict contains per-element-type counts."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="action", text="Someone walks in."),
                ScreenplayElement(element_type="character", text="BOB"),
                ScreenplayElement(element_type="dialogue", text="Hi."),
            ],
        )
        result = estimate_pages(screenplay)
        assert "action" in result.breakdown
        assert "dialogue" in result.breakdown
        assert "scene_heading" in result.breakdown
        assert "character" in result.breakdown

    # --- Edge cases ---

    def test_empty_screenplay(self):
        """Empty screenplay returns zero estimate with high confidence."""
        screenplay = Screenplay()
        result = estimate_pages(screenplay)
        assert result.estimated_pages == 0.0
        assert result.total_lines == 0
        assert result.confidence == "high"

    def test_title_only(self):
        """Screenplay with only title has no content to estimate."""
        screenplay = Screenplay(title="My Movie")
        result = estimate_pages(screenplay)
        assert result.estimated_pages == 0.0

    def test_single_scene_heading(self):
        """Single scene heading produces a minimal page count."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. CAR - NIGHT"),
            ],
        )
        result = estimate_pages(screenplay)
        assert result.estimated_pages > 0
        assert result.breakdown.get("scene_heading", 0) >= 1

    # --- Input variation ---

    def test_action_heavy_screenplay(self):
        """Screenplay with lots of action text estimates more pages."""
        long_action = " ".join(["word"] * 200)  # 200 words
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. FIELD - DAY"),
                ScreenplayElement(element_type="action", text=long_action),
            ],
        )
        result = estimate_pages(screenplay)
        # 200 words of action should be more than a few lines
        assert result.total_lines > 2

    def test_dialogue_heavy_screenplay(self):
        """Screenplay with lots of dialogue estimates more pages."""
        long_dialogue = " ".join(["word"] * 100)
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="character", text="JANE"),
                ScreenplayElement(element_type="dialogue", text=long_dialogue),
            ],
        )
        result = estimate_pages(screenplay)
        # Dialogue lines should be counted
        assert result.breakdown.get("dialogue", 0) >= 1

    def test_multiple_scenes(self):
        """Multiple scenes produce a higher page count."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. A - DAY"),
                ScreenplayElement(element_type="action", text="Action A."),
                ScreenplayElement(element_type="scene_heading", text="EXT. B - NIGHT"),
                ScreenplayElement(element_type="action", text="Action B."),
                ScreenplayElement(element_type="scene_heading", text="INT. C - DAY"),
                ScreenplayElement(element_type="action", text="Action C."),
            ],
        )
        result = estimate_pages(screenplay)
        assert result.breakdown.get("scene_heading", 0) >= 3

    # --- Invariant ---

    def test_invariant_returns_page_estimate_type(self):
        """Function always returns a PageEstimate instance."""
        screenplay = Screenplay()
        result = estimate_pages(screenplay)
        assert isinstance(result, PageEstimate)

    def test_invariant_estimated_pages_never_negative(self):
        """Estimated pages is never negative."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Hello."),
            ],
        )
        result = estimate_pages(screenplay)
        assert result.estimated_pages >= 0

    def test_invariant_breakdown_keys_are_strings(self):
        """Breakdown dict keys are element type strings."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. X - DAY"),
                ScreenplayElement(element_type="action", text="Do stuff."),
            ],
        )
        result = estimate_pages(screenplay)
        for key in result.breakdown:
            assert isinstance(key, str)

    # --- State transition ---

    def test_scenes_to_elements_consistency(self):
        """Screenplay with scenes produces same shape as with elements."""
        from cosmic_script.models import Scene
        screenplay_with_scenes = Screenplay(
            title="Test",
            scenes=[
                Scene(heading="INT. HOUSE - DAY", content="John enters.\n\nJOHN\nHello."),
            ],
        )
        screenplay_with_elements = Screenplay(
            title="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - DAY"),
                ScreenplayElement(element_type="action", text="John enters."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
            ],
        )
        result_scenes = estimate_pages(screenplay_with_scenes)
        result_elements = estimate_pages(screenplay_with_elements)
        # Both should produce positive estimates
        assert result_scenes.estimated_pages > 0
        assert result_elements.estimated_pages > 0

    # --- Confidence ---

    def test_confidence_high_for_complete_screenplay(self):
        """Full screenplay with multiple element types gets high confidence."""
        screenplay = Screenplay(
            title="Full",
            author="Test",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. A - DAY"),
                ScreenplayElement(element_type="action", text="Action."),
                ScreenplayElement(element_type="character", text="BOB"),
                ScreenplayElement(element_type="dialogue", text="Line."),
                ScreenplayElement(element_type="transition", text="CUT TO:"),
                ScreenplayElement(element_type="scene_heading", text="EXT. B - NIGHT"),
                ScreenplayElement(element_type="action", text="More action."),
            ],
        )
        result = estimate_pages(screenplay)
        assert result.confidence == "high"

    def test_confidence_low_for_single_line(self):
        """Single line screenplay gets low confidence."""
        screenplay = Screenplay(
            elements=[
                ScreenplayElement(element_type="action", text="Hi."),
            ],
        )
        result = estimate_pages(screenplay)
        assert result.confidence == "low"


class TestPageEstimateDataclass:
    """Test suite for the PageEstimate data model."""

    def test_default_values(self):
        """PageEstimate has sensible defaults."""
        pe = PageEstimate(
            estimated_pages=0.0,
            total_lines=0,
        )
        assert isinstance(pe.breakdown, dict)
        assert pe.confidence == "medium"

    def test_custom_values(self):
        """PageEstimate accepts and stores custom values."""
        pe = PageEstimate(
            estimated_pages=5.5,
            total_lines=275,
            breakdown={"action": 200, "dialogue": 75, "scene_heading": 10},
            confidence="high",
        )
        assert pe.estimated_pages == 5.5
        assert pe.total_lines == 275
        assert pe.breakdown["action"] == 200
        assert pe.confidence == "high"
