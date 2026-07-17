"""Quality regression tests for screenplay conversion.

Tests that conversion output maintains quality baselines across
fixture files. Uses model="demo" (no API calls).

Each fixture is tested for:
- Valid Fountain output
- Minimum quality scores
- Element type distribution
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cosmic_script.models import Chapter, ElementType, Screenplay, ScreenplayElement, Scene
from cosmic_script.conversion.converter import ConversionConfig, ScreenplayConverter
from cosmic_script.conversion.registry import CharacterRegistry
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.analysis.quality_metrics import (
    QualityMetrics,
    compute_metrics,
    format_score,
    structure_score,
    dialogue_score,
    overall_quality,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> str:
    """Load a fixture file's text content."""
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture {name} not found")
    return path.read_text(encoding="utf-8")


def _convert_fixture_to_screenplay(name: str) -> Screenplay:
    """Convert a fixture file to a Screenplay using demo mode."""
    text = _load_fixture(name)
    chapter = Chapter(number=1, text=text)
    config = ConversionConfig(model="demo", no_cache=True)
    converter = ScreenplayConverter(config)
    registry = CharacterRegistry()
    scenes = converter.convert_chapter(chapter, registry)
    return Screenplay(
        title=f"Test: {name}",
        author="Regression Test",
        scenes=scenes,
    )


def _elements_to_screenplay(elements: list[ScreenplayElement]) -> Screenplay:
    """Wrap elements in a Screenplay object."""
    return Screenplay(
        title="Direct Test",
        author="Test",
        elements=elements,
    )


# ---------------------------------------------------------------------------
# Fixtures loading
# ---------------------------------------------------------------------------


class TestFixturesExist:
    """Verify all required fixture files exist."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_fixture_exists(self, fixture_name: str) -> None:
        """Each fixture file must exist."""
        path = FIXTURES_DIR / fixture_name
        assert path.exists(), f"Fixture {fixture_name} not found"

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_fixture_has_content(self, fixture_name: str) -> None:
        """Each fixture must have 50+ words."""
        text = _load_fixture(fixture_name)
        word_count = len(text.split())
        assert word_count >= 50, f"{fixture_name} has only {word_count} words"


# ---------------------------------------------------------------------------
# Fountain output validation
# ---------------------------------------------------------------------------


class TestFountainOutput:
    """Verify demo conversion produces valid Fountain output."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_produces_fountain_output(self, fixture_name: str) -> None:
        """Conversion must produce non-empty Fountain text."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        fountain = generate_fountain(screenplay)
        assert len(fountain) > 100, f"{fixture_name} produced too little output"

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_has_scene_heading(self, fixture_name: str) -> None:
        """Fountain output must contain at least one INT. or EXT. heading."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        fountain = generate_fountain(screenplay)
        has_heading = any(keyword in fountain for keyword in ["INT.", "EXT.", "INT/EXT.", "I/E."])
        assert has_heading, f"{fixture_name} missing scene heading"


# ---------------------------------------------------------------------------
# Quality score baselines
# ---------------------------------------------------------------------------


class TestQualityScores:
    """Regression baselines for quality metrics.

    Thresholds are set conservatively to allow demo output variation
    while catching real regressions.
    """

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_format_score_baseline(self, fixture_name: str) -> None:
        """Format score must be at least 70/100."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        score = format_score(screenplay)
        assert score >= 70.0, f"{fixture_name} format_score={score:.1f}, expected >= 70"

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_structure_score_baseline(self, fixture_name: str) -> None:
        """Structure score must be at least 60/100."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        score = structure_score(screenplay)
        assert score >= 60.0, f"{fixture_name} structure_score={score:.1f}, expected >= 60"

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_dialogue_score_baseline(self, fixture_name: str) -> None:
        """Dialogue score must be at least 50/100."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        score = dialogue_score(screenplay)
        assert score >= 50.0, f"{fixture_name} dialogue_score={score:.1f}, expected >= 50"

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_dialogue_heavy.txt",
            "fixture_action_heavy.txt",
            "fixture_mixed.txt",
            "fixture_multi_character.txt",
            "fixture_single_scene.txt",
        ],
    )
    def test_overall_quality_baseline(self, fixture_name: str) -> None:
        """Overall quality must be at least 60/100."""
        screenplay = _convert_fixture_to_screenplay(fixture_name)
        score = overall_quality(screenplay)
        assert score >= 60.0, f"{fixture_name} overall={score:.1f}, expected >= 60"


# ---------------------------------------------------------------------------
# Element type distribution
# ---------------------------------------------------------------------------


class TestElementDistribution:
    """Verify element type counts are reasonable for each fixture type."""

    def test_dialogue_heavy_has_dialogue(self) -> None:
        """Dialogue-heavy fixture must have significant dialogue."""
        screenplay = _convert_fixture_to_screenplay("fixture_dialogue_heavy.txt")
        metrics = compute_metrics(screenplay)
        dialogue = metrics.element_counts.get("dialogue", 0)
        assert dialogue >= 5, f"Expected >= 5 dialogue elements, got {dialogue}"

    def test_action_heavy_has_action(self) -> None:
        """Action-heavy fixture must have significant action."""
        screenplay = _convert_fixture_to_screenplay("fixture_action_heavy.txt")
        metrics = compute_metrics(screenplay)
        action = metrics.element_counts.get("action", 0)
        assert action >= 3, f"Expected >= 3 action elements, got {action}"

    def test_multi_character_has_characters(self) -> None:
        """Multi-character fixture must have 3+ speaking characters."""
        screenplay = _convert_fixture_to_screenplay("fixture_multi_character.txt")
        metrics = compute_metrics(screenplay)
        characters = metrics.element_counts.get("character", 0)
        assert characters >= 3, f"Expected >= 3 character cues, got {characters}"

    def test_single_scene_has_one_scene(self) -> None:
        """Single-scene fixture must produce 1-2 scenes."""
        screenplay = _convert_fixture_to_screenplay("fixture_single_scene.txt")
        metrics = compute_metrics(screenplay)
        scenes = metrics.element_counts.get("scene_heading", 0)
        assert 1 <= scenes <= 3, f"Expected 1-3 scene headings, got {scenes}"

    def test_mixed_has_both_elements(self) -> None:
        """Mixed fixture must have both dialogue and action."""
        screenplay = _convert_fixture_to_screenplay("fixture_mixed.txt")
        metrics = compute_metrics(screenplay)
        dialogue = metrics.element_counts.get("dialogue", 0)
        action = metrics.element_counts.get("action", 0)
        assert dialogue >= 3, f"Expected >= 3 dialogue, got {dialogue}"
        assert action >= 2, f"Expected >= 2 action, got {action}"


# ---------------------------------------------------------------------------
# quality_metrics unit tests
# ---------------------------------------------------------------------------


class TestFormatScore:
    """Direct tests for format_score function."""

    def test_empty_screenplay(self) -> None:
        """Empty screenplay is trivially valid."""
        sp = Screenplay()
        assert format_score(sp) == 100.0

    def test_valid_fountain_elements(self) -> None:
        """Well-formed elements score high."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="John sits at desk."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="JOHN"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello there."),
            ]
        )
        score = format_score(sp)
        assert score >= 90.0

    def test_scene_heading_present(self) -> None:
        """Screenplay with scene heading passes format check."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
            ]
        )
        assert format_score(sp) >= 80.0

    def test_no_scene_heading_penalized(self) -> None:
        """Screenplay without scene heading is penalized."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.ACTION, text="Some action."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="BOB"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hi."),
            ]
        )
        score = format_score(sp)
        assert score <= 80.0


class TestStructureScore:
    """Direct tests for structure_score function."""

    def test_empty_screenplay(self) -> None:
        """Empty screenplay is trivially valid."""
        sp = Screenplay()
        assert structure_score(sp) == 100.0

    def test_single_scene(self) -> None:
        """Single scene gets moderate score."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action."),
            ]
        )
        score = structure_score(sp)
        assert 60.0 <= score <= 100.0

    def test_multiple_scenes(self) -> None:
        """Multiple scenes score well."""
        sp = Screenplay(
            scenes=[
                Scene(heading="INT. ROOM - DAY", content="Action line 1.\nAction line 2."),
                Scene(heading="EXT. GARDEN - NIGHT", content="Stars twinkle."),
                Scene(heading="INT. HALL - DAY", content="Quiet hall."),
            ]
        )
        score = structure_score(sp)
        assert score >= 70.0


class TestDialogueScore:
    """Direct tests for dialogue_score function."""

    def test_empty_screenplay(self) -> None:
        """Empty screenplay gets neutral score."""
        sp = Screenplay()
        assert dialogue_score(sp) == 100.0

    def test_balanced_dialogue(self) -> None:
        """Balanced dialogue/action scores well."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="BOB"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello."),
                ScreenplayElement(element_type=ElementType.ACTION, text="More action."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="ALICE"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hi there."),
            ]
        )
        score = dialogue_score(sp)
        assert score >= 70.0

    def test_all_action_no_dialogue(self) -> None:
        """All action, no dialogue gets penalized."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action 1."),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action 2."),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action 3."),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action 4."),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action 5."),
            ]
        )
        score = dialogue_score(sp)
        assert score < 80.0

    def test_dialogue_without_characters(self) -> None:
        """Dialogue without character cues is penalized."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello."),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="World."),
            ]
        )
        score = dialogue_score(sp)
        assert score < 70.0


class TestOverallQuality:
    """Direct tests for overall_quality function."""

    def test_empty_screenplay(self) -> None:
        """Empty screenplay returns 100."""
        sp = Screenplay()
        assert overall_quality(sp) == 100.0

    def test_weighted_combination(self) -> None:
        """Overall is weighted avg of component scores."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="BOB"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello."),
            ]
        )
        overall = overall_quality(sp)
        fmt = format_score(sp)
        struct = structure_score(sp)
        dial = dialogue_score(sp)
        expected = round(fmt * 0.4 + struct * 0.3 + dial * 0.3, 2)
        assert overall == expected


class TestComputeMetrics:
    """Direct tests for compute_metrics function."""

    def test_returns_quality_metrics(self) -> None:
        """compute_metrics returns a QualityMetrics instance."""
        sp = Screenplay()
        result = compute_metrics(sp)
        assert isinstance(result, QualityMetrics)

    def test_element_counts_populated(self) -> None:
        """Element counts are populated for non-empty screenplay."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.SCENE_HEADING, text="INT. ROOM - DAY"),
                ScreenplayElement(element_type=ElementType.ACTION, text="Action."),
                ScreenplayElement(element_type=ElementType.CHARACTER, text="BOB"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello."),
            ]
        )
        result = compute_metrics(sp)
        assert result.element_counts.get("scene_heading", 0) >= 1
        assert result.element_counts.get("action", 0) >= 1

    def test_warnings_for_missing_elements(self) -> None:
        """Warnings generated for suspicious element patterns."""
        sp = _elements_to_screenplay(
            [
                ScreenplayElement(element_type=ElementType.CHARACTER, text="BOB"),
                ScreenplayElement(element_type=ElementType.DIALOGUE, text="Hello."),
            ]
        )
        result = compute_metrics(sp)
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Regression baselines: score ranges
# ---------------------------------------------------------------------------


class TestRegressionBaselines:
    """Ensure scores stay within expected ranges across runs.

    These tests use tight ranges to catch accidental regressions
    while allowing for minor implementation variations.
    """

    def test_dialogue_heavy_overall_range(self) -> None:
        """Dialogue-heavy fixture overall score in [65, 100]."""
        screenplay = _convert_fixture_to_screenplay("fixture_dialogue_heavy.txt")
        score = overall_quality(screenplay)
        assert 65.0 <= score <= 100.0, f"Expected [65, 100], got {score}"

    def test_action_heavy_overall_range(self) -> None:
        """Action-heavy fixture overall score in [60, 100]."""
        screenplay = _convert_fixture_to_screenplay("fixture_action_heavy.txt")
        score = overall_quality(screenplay)
        assert 60.0 <= score <= 100.0, f"Expected [60, 100], got {score}"

    def test_mixed_overall_range(self) -> None:
        """Mixed fixture overall score in [65, 100]."""
        screenplay = _convert_fixture_to_screenplay("fixture_mixed.txt")
        score = overall_quality(screenplay)
        assert 65.0 <= score <= 100.0, f"Expected [65, 100], got {score}"

    def test_multi_character_overall_range(self) -> None:
        """Multi-character fixture overall score in [60, 100]."""
        screenplay = _convert_fixture_to_screenplay("fixture_multi_character.txt")
        score = overall_quality(screenplay)
        assert 60.0 <= score <= 100.0, f"Expected [60, 100], got {score}"

    def test_single_scene_overall_range(self) -> None:
        """Single-scene fixture overall score in [60, 100]."""
        screenplay = _convert_fixture_to_screenplay("fixture_single_scene.txt")
        score = overall_quality(screenplay)
        assert 60.0 <= score <= 100.0, f"Expected [60, 100], got {score}"
