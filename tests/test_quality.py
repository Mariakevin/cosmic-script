"""Tests for algorithmic quality analysis."""

import pytest
from cosmic_script.conversion.quality import (
    analyze_dialogue_ratio,
    analyze_scene_pacing,
    analyze_character_appearance,
    analyze_formatting,
    analyze_quality,
    QualityReport,
)


class TestDialogueRatio:
    """Tests for dialogue ratio analysis."""

    def test_empty_scenes(self):
        result = analyze_dialogue_ratio([])
        assert result["dialogue_ratio"] == 0.0

    def test_all_dialogue(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "    Hello there.\n    Hi!"},
        ]
        result = analyze_dialogue_ratio(scenes)
        assert result["dialogue_ratio"] > 0.5

    def test_all_action(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Sarah walks in.\nShe looks around."},
        ]
        result = analyze_dialogue_ratio(scenes)
        assert result["action_ratio"] > 0.5

    def test_high_dialogue_warning(self):
        """Very high dialogue ratio should trigger warning."""
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "    Line 1\n    Line 2\n    Line 3\n    Line 4\n    Line 5"},
        ]
        result = analyze_dialogue_ratio(scenes)
        assert len(result["warnings"]) > 0


class TestScenePacing:
    """Tests for scene pacing analysis."""

    def test_empty_scenes(self):
        result = analyze_scene_pacing([])
        assert result["scene_count"] == 0

    def test_good_pacing(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "\n".join([f"Line {i}" for i in range(10)])}
            for _ in range(5)
        ]
        result = analyze_scene_pacing(scenes)
        assert result["scene_count"] == 5
        assert result["pacing_score"] >= 7.0

    def test_short_scene_warning(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Short"},
        ]
        result = analyze_scene_pacing(scenes)
        assert len(result["warnings"]) > 0

    def test_long_scene_warning(self):
        content = "\n".join([f"Line {i}" for i in range(35)])
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": content},
        ]
        result = analyze_scene_pacing(scenes)
        assert len(result["warnings"]) > 0


class TestCharacterAppearance:
    """Tests for character appearance analysis."""

    def test_empty_registry(self):
        result = analyze_character_appearance([], set())
        assert result["warnings"] == []

    def test_character_never_appears(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "SARAH\nHello."},
        ]
        result = analyze_character_appearance(scenes, {"SARAH", "JOHN"})
        suggestions = result["suggestions"]
        assert any("JOHN" in s for s in suggestions)

    def test_character_appears(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "SARAH\nHello.\n\nJOHN\nHi there."},
        ]
        result = analyze_character_appearance(scenes, {"SARAH", "JOHN"})
        assert result["character_appearances"]["SARAH"] > 0
        assert result["character_appearances"]["JOHN"] > 0

    def test_dict_input(self):
        """Should handle dict input (registry.characters type)."""
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "SARAH\nHello."},
        ]
        registry = {"SARAH": None, "JOHN": None}
        result = analyze_character_appearance(scenes, registry)
        assert result["character_appearances"]["SARAH"] > 0


class TestFormatting:
    """Tests for formatting analysis."""

    def test_empty_text(self):
        result = analyze_formatting("")
        assert result["formatting_score"] == 10.0

    def test_valid_formatting(self):
        text = """FADE IN:

INT. COFFEE SHOP - DAY

SARAH
Hello there.

CUT TO:

INT. OFFICE - NIGHT

JOHN
Working late."""
        result = analyze_formatting(text)
        assert result["formatting_score"] >= 8.0

    def test_camera_direction_penalty(self):
        text = """INT. ROOM - DAY

CLOSE UP on Sarah."""
        result = analyze_formatting(text)
        assert result["formatting_score"] < 10.0
        assert len(result["issues"]) > 0

    def test_we_see_penalty(self):
        text = """INT. ROOM - DAY

We see Sarah enter."""
        result = analyze_formatting(text)
        assert result["formatting_score"] < 10.0


class TestQualityReport:
    """Tests for QualityReport dataclass."""

    def test_overall_score(self):
        report = QualityReport(pacing_score=8.0, formatting_score=6.0)
        assert report.overall_score == 7.0

    def test_empty_report(self):
        report = QualityReport()
        assert report.overall_score == 0.0


class TestAnalyzeQuality:
    """Tests for the main quality analysis pipeline."""

    def test_empty_input(self):
        report = analyze_quality("", [])
        assert report.scene_count == 0

    def test_valid_screenplay(self):
        text = """FADE IN:

INT. COFFEE SHOP - DAY

SARAH
Hello there.

JOHN
Hi!

CUT TO:

INT. OFFICE - NIGHT

SARAH
Working late."""
        scenes = [
            {"heading": "INT. COFFEE SHOP - DAY", "content": "SARAH\nHello there.\n\nJOHN\nHi!"},
            {"heading": "INT. OFFICE - NIGHT", "content": "SARAH\nWorking late."},
        ]
        report = analyze_quality(text, scenes, {"SARAH", "JOHN"})
        assert report.scene_count == 2
        assert report.character_count > 0
        assert report.formatting_score > 0
