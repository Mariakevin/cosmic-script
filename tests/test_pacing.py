"""Tests for Scene Pacing Analysis."""
import pytest

from cosmic_script.models import Screenplay, Scene, ScreenplayElement
from cosmic_script.analysis.pacing import (
    ScenePacing,
    PacingReport,
    analyze_pacing,
    _classify_pacing,
    _detect_issues,
    _generate_recommendations,
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestClassifyPacing:
    """Coverage: boundary, input-variation."""

    def test_fast_short_scene(self) -> None:
        """Scene with <10 lines → fast."""
        assert _classify_pacing(5, 0.7) == "fast"

    def test_medium_scene(self) -> None:
        """Scene with 10-25 lines → medium."""
        assert _classify_pacing(15, 0.5) == "medium"

    def test_slow_long_scene(self) -> None:
        """Scene with >25 lines → slow."""
        assert _classify_pacing(30, 0.2) == "slow"

    def test_fast_high_dialogue_ratio(self) -> None:
        """Scene with high dialogue ratio (>60%) → fast regardless of length."""
        assert _classify_pacing(8, 0.7) == "fast"

    def test_slow_low_dialogue_ratio(self) -> None:
        """Scene with low dialogue ratio (<30%) and >25 lines → slow."""
        assert _classify_pacing(28, 0.2) == "slow"

    def test_boundary_fast_10_lines(self) -> None:
        """Boundary: exactly 10 lines → fast."""
        assert _classify_pacing(10, 0.6) == "fast"

    def test_boundary_medium_11_lines(self) -> None:
        """Boundary: exactly 11 lines → medium."""
        assert _classify_pacing(11, 0.5) == "medium"

    def test_boundary_slow_26_lines(self) -> None:
        """Boundary: exactly 26 lines → slow."""
        assert _classify_pacing(26, 0.2) == "slow"


class TestDetectIssues:
    """Coverage: happy-path, boundary, input-variation."""

    def test_too_long(self) -> None:
        """Scene >30 lines has 'too long' issue."""
        issues = _detect_issues(35, 10, 0.3)
        assert "too long" in issues

    def test_too_short(self) -> None:
        """Scene <3 lines has 'too short' issue."""
        issues = _detect_issues(2, 1, 0.5)
        assert "too short" in issues

    def test_no_dialogue(self) -> None:
        """Scene with 0 dialogue lines has 'no dialogue' issue."""
        issues = _detect_issues(20, 0, 0.0)
        assert "no dialogue" in issues

    def test_all_dialogue(self) -> None:
        """Scene with >90% dialogue has 'all dialogue' issue."""
        issues = _detect_issues(10, 10, 1.0)
        assert "all dialogue" in issues

    def test_multiple_issues(self) -> None:
        """Scene can have multiple issues simultaneously."""
        issues = _detect_issues(40, 0, 0.0)
        assert "too long" in issues
        assert "no dialogue" in issues

    def test_no_issues(self) -> None:
        """Well-balanced scene has no issues."""
        issues = _detect_issues(15, 7, 0.47)
        assert issues == []

    def test_boundary_3_lines(self) -> None:
        """Boundary: exactly 3 lines is not 'too short'."""
        issues = _detect_issues(3, 1, 0.33)
        assert "too short" not in issues

    def test_boundary_30_lines(self) -> None:
        """Boundary: exactly 30 lines is not 'too long'."""
        issues = _detect_issues(30, 10, 0.33)
        assert "too long" not in issues


class TestGenerateRecommendations:
    """Coverage: happy-path, boundary."""

    def test_split_long_scenes(self) -> None:
        """Scene with 'too long' issue gets split recommendation."""
        issues = ["too long"]
        recs = _generate_recommendations(issues)
        assert any("split" in r.lower() for r in recs)

    def test_add_dialogue(self) -> None:
        """Scene with 'no dialogue' issue gets add dialogue recommendation."""
        issues = ["no dialogue"]
        recs = _generate_recommendations(issues)
        assert any("add dialogue" in r.lower() for r in recs)

    def test_add_action(self) -> None:
        """Scene with 'all dialogue' issue gets add action recommendation."""
        issues = ["all dialogue"]
        recs = _generate_recommendations(issues)
        assert any("add action" in r.lower() for r in recs)

    def test_no_issues_no_recs(self) -> None:
        """Scene with no issues generates no recommendations."""
        recs = _generate_recommendations([])
        assert len(recs) == 0

    def test_multiple_issues_multiple_recs(self) -> None:
        """Multiple issues produce multiple recommendations."""
        issues = ["too long", "no dialogue", "all dialogue"]
        recs = _generate_recommendations(issues)
        assert len(recs) == 3


# ---------------------------------------------------------------------------
# ScenePacing dataclass
# ---------------------------------------------------------------------------

class TestScenePacingModel:
    """Coverage: happy-path, boundary."""

    def test_minimal_construction(self) -> None:
        """ScenePacing can be created with required fields."""
        sp = ScenePacing(
            scene_number=1, heading="INT. ROOM - DAY", line_count=10,
            dialogue_lines=4, action_lines=6, dialogue_ratio=0.4,
            pacing="medium", issues=[],
        )
        assert sp.scene_number == 1
        assert sp.pacing == "medium"

    def test_with_issues(self) -> None:
        """ScenePacing with issues."""
        sp = ScenePacing(
            scene_number=2, heading="EXT. FIELD - NIGHT", line_count=35,
            dialogue_lines=0, action_lines=35, dialogue_ratio=0.0,
            pacing="slow", issues=["too long", "no dialogue"],
        )
        assert len(sp.issues) == 2


class TestPacingReportModel:
    """Coverage: happy-path, boundary."""

    def test_minimal_construction(self) -> None:
        """PacingReport can be created with required fields."""
        pr = PacingReport(
            scenes=[], overall_pacing="medium", avg_scene_length=0.0,
            total_issues=0, recommendations=[],
        )
        assert pr.overall_pacing == "medium"
        assert pr.total_issues == 0

    def test_with_data(self) -> None:
        """PacingReport with full data."""
        scene = ScenePacing(
            scene_number=1, heading="INT. ROOM - DAY", line_count=10,
            dialogue_lines=4, action_lines=6, dialogue_ratio=0.4,
            pacing="fast", issues=[],
        )
        pr = PacingReport(
            scenes=[scene],
            overall_pacing="fast",
            avg_scene_length=10.0,
            total_issues=0,
            recommendations=[],
        )
        assert pr.scenes[0].heading == "INT. ROOM - DAY"


# ---------------------------------------------------------------------------
# Integration tests for analyze_pacing
# ---------------------------------------------------------------------------

class TestAnalyzePacing:
    """Coverage: happy-path, boundary, input-variation, invariant."""

    def _make_scene(self, heading: str, content: str) -> Scene:
        return Scene(heading=heading, content=content)

    def test_single_scene(self) -> None:
        """Happy-path: single scene produces a report with one entry."""
        sp = Screenplay(
            scenes=[self._make_scene("INT. ROOM - DAY", "JOHN\nHello.\nJOHN\nHow are you?")],
        )
        result = analyze_pacing(sp)
        assert isinstance(result, PacingReport)
        assert len(result.scenes) == 1
        assert result.scenes[0].scene_number == 1

    def test_multiple_scenes(self) -> None:
        """Happy-path: multiple scenes each get an entry."""
        sp = Screenplay(
            scenes=[
                self._make_scene("INT. A - DAY", "Some action."),
                self._make_scene("INT. B - DAY", "JOHN\nHi.\n\nSARAH\nHello."),
                self._make_scene("INT. C - DAY", "More action."),
            ],
        )
        result = analyze_pacing(sp)
        assert len(result.scenes) == 3
        assert result.scenes[0].heading == "INT. A - DAY"
        assert result.scenes[2].heading == "INT. C - DAY"

    def test_empty_screenplay(self) -> None:
        """Boundary: empty screenplay returns report with no scenes."""
        sp = Screenplay()
        result = analyze_pacing(sp)
        assert result.scenes == []
        assert result.overall_pacing == "medium"
        assert result.total_issues == 0

    def test_line_count_calculation(self) -> None:
        """Happy-path: line counts are calculated correctly."""
        sp = Screenplay(
            scenes=[self._make_scene("INT. ROOM - DAY", "JOHN\nHello.\n\nSARAH\nHi.")],
        )
        result = analyze_pacing(sp)
        scene = result.scenes[0]
        # 2 character cues + 2 dialogue lines = 4 lines
        assert scene.line_count == 4
        assert scene.dialogue_lines == 2
        assert scene.action_lines == 0

    def test_dialogue_ratio(self) -> None:
        """Happy-path: dialogue ratio is a float between 0 and 1."""
        sp = Screenplay(
            scenes=[self._make_scene("INT. ROOM - DAY", "JOHN\nHello.\n\nSARAH\nHi there.")],
        )
        result = analyze_pacing(sp)
        scene = result.scenes[0]
        assert 0 <= scene.dialogue_ratio <= 1

    def test_scene_with_action_and_dialogue(self) -> None:
        """Input-variation: mixed action and dialogue."""
        content = (
            "John walks into the room.\n"
            "He looks around.\n\n"
            "JOHN\nHello?\n\n"
            "SARAH\nOver here.\n\n"
            "John crosses to the window."
        )
        sp = Screenplay(
            scenes=[self._make_scene("INT. ROOM - DAY", content)],
        )
        result = analyze_pacing(sp)
        scene = result.scenes[0]
        assert scene.action_lines > 0
        assert scene.dialogue_lines > 0

    def test_overall_pacing_calculation(self) -> None:
        """Happy-path: overall pacing is derived from scene pacing modes."""
        sp = Screenplay(
            scenes=[
                self._make_scene("INT. A - DAY", "JOHN\nHi."),
                self._make_scene("INT. B - DAY", "JOHN\nHello again.\n\nSARAH\nHey."),
                self._make_scene("INT. C - DAY", "JOHN\nBye."),
            ],
        )
        result = analyze_pacing(sp)
        assert result.overall_pacing in ("fast", "medium", "slow")

    def test_recommendations_generated(self) -> None:
        """Happy-path: issues generate recommendations."""
        sp = Screenplay(
            scenes=[self._make_scene("INT. LONG - DAY", "A\nB\nC\nD\nE\nF\nG\nH\nI\nJ\nK\nL\nM\nN\nO\nP\nQ\nR\nS\nT\nU\nV\nW\nX\nY\nZ\nAA\nBB\nCC\nDD\nEE\nFF\nGG\nHH")],
        )
        result = analyze_pacing(sp)
        assert result.total_issues > 0
        assert len(result.recommendations) > 0

    def test_avg_scene_length(self) -> None:
        """Happy-path: avg_scene_length is mean of all scene line counts."""
        sp = Screenplay(
            scenes=[
                self._make_scene("INT. A - DAY", "JOHN\nHi."),
                self._make_scene("INT. B - DAY", "JOHN\nHello.\n\nSARAH\nHey.\n\nJOHN\nBye."),
            ],
        )
        result = analyze_pacing(sp)
        expected_avg = (2 + 6) / 2  # Scene 1: 2 lines, Scene 2: 6 lines
        assert result.avg_scene_length == expected_avg

    def test_dialogue_lines_from_elements(self) -> None:
        """Dialogue count works with ScreenplayElement-based screenplays."""
        sp = Screenplay(
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. ROOM - DAY"),
                ScreenplayElement(element_type="action", text="John enters."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello."),
                ScreenplayElement(element_type="character", text="SARAH"),
                ScreenplayElement(element_type="dialogue", text="Hi."),
            ],
        )
        result = analyze_pacing(sp)
        assert len(result.scenes) > 0
        scene = result.scenes[0]
        assert scene.dialogue_lines >= 2

    def test_scene_headings_integrity(self) -> None:
        """Invariant: all scene headings are preserved in report."""
        headings = ["INT. A - DAY", "EXT. B - NIGHT", "INT. C - DAWN"]
        sp = Screenplay(
            scenes=[self._make_scene(h, "JOHN\nHi.") for h in headings],
        )
        result = analyze_pacing(sp)
        result_headings = [s.heading for s in result.scenes]
        assert result_headings == headings


# ---------------------------------------------------------------------------
# Edge cases for analyze_pacing
# ---------------------------------------------------------------------------

class TestAnalyzePacingEdgeCases:

    def test_no_scenes_no_elements(self) -> None:
        """No scenes or elements returns empty report."""
        sp = Screenplay(title="Empty")
        result = analyze_pacing(sp)
        assert result.scenes == []
        assert result.total_issues == 0
        assert result.avg_scene_length == 0.0

    def test_scene_with_only_dialogue(self) -> None:
        """Scene with only dialogue (no action) counts correctly."""
        sp = Screenplay(
            scenes=[Scene(heading="INT. ROOM - DAY", content="JOHN\nHello.")],
        )
        result = analyze_pacing(sp)
        assert result.scenes[0].action_lines == 0
        assert result.scenes[0].dialogue_lines > 0

    def test_single_scene_overall_pacing(self) -> None:
        """Single scene overall_pacing matches that scene's pacing."""
        sp = Screenplay(
            scenes=[Scene(heading="INT. SHORT - DAY", content="JOHN\nHi.")],
        )
        result = analyze_pacing(sp)
        assert result.overall_pacing == result.scenes[0].pacing
