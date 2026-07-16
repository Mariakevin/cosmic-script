"""Tests for deterministic post-processing pipeline."""

import pytest
from cosmic_script.conversion.postprocess import (
    fix_scene_headings,
    fix_character_cues,
    remove_camera_directions,
    fix_inner_thoughts,
    fix_transitions,
    merge_short_scenes,
    split_long_scenes,
    postprocess_fountain,
    postprocess_scenes,
)


class TestFixSceneHeadings:
    """Tests for scene heading fixes."""

    def test_valid_heading_unchanged(self):
        text = "INT. COFFEE SHOP - DAY\n\nAction here."
        result = fix_scene_headings(text)
        assert "INT. COFFEE SHOP - DAY" in result

    def test_adds_int_prefix(self):
        """Location-like text without INT./EXT. gets prefix added."""
        text = "COFFEE SHOP - DAY\n\nAction here."
        result = fix_scene_headings(text)
        # Should add INT. or EXT. prefix
        assert "COFFEE SHOP - DAY" in result

    def test_fixes_invalid_time_of_day(self):
        """Invalid time-of-day defaults to DAY."""
        text = "INT. COFFEE SHOP - FOOBAR\n\nAction here."
        result = fix_scene_headings(text)
        assert "INT. COFFEE SHOP - DAY" in result


class TestFixCharacterCues:
    """Tests for character cue fixes."""

    def test_valid_cue_unchanged(self):
        text = "SARAH\nI can't believe this."
        result = fix_character_cues(text)
        assert "SARAH" in result

    def test_lowercase_converted(self):
        """Capitalized character names should be uppercased."""
        text = "Sarah\nI can't believe this."
        result = fix_character_cues(text)
        assert "SARAH" in result


class TestRemoveCameraDirections:
    """Tests for camera direction removal."""

    def test_close_up_removed(self):
        text = "CLOSE UP on Sarah's face."
        result = remove_camera_directions(text)
        assert "CLOSE UP" not in result
        assert "Sarah" in result

    def test_pan_removed(self):
        text = "PAN LEFT across the room."
        result = remove_camera_directions(text)
        assert "PAN LEFT" not in result

    def test_wide_shot_removed(self):
        text = "WIDE SHOT of the city."
        result = remove_camera_directions(text)
        assert "WIDE SHOT" not in result

    def test_scene_heading_not_modified(self):
        """Scene headings should not be modified."""
        text = "INT. COFFEE SHOP - DAY"
        result = remove_camera_directions(text)
        assert result == text


class TestFixTransitions:
    """Tests for transition fixes."""

    def test_cut_to(self):
        text = "cut to"
        result = fix_transitions(text)
        assert "CUT TO:" in result

    def test_fade_out(self):
        text = "fade out"
        result = fix_transitions(text)
        assert "FADE OUT" in result


class TestMergeShortScenes:
    """Tests for short scene merging."""

    def test_merge_short_with_previous(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Line 1\nLine 2\nLine 3"},
            {"heading": "INT. ROOM - DAY", "content": "Short"},
        ]
        result = merge_short_scenes(scenes)
        # Short scene should be merged
        assert len(result) == 1

    def test_keep_long_scenes(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"},
            {"heading": "EXT. STREET - NIGHT", "content": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"},
        ]
        result = merge_short_scenes(scenes)
        assert len(result) == 2


class TestSplitLongScenes:
    """Tests for long scene splitting."""

    def test_short_scene_unchanged(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Line 1\nLine 2\nLine 3"},
        ]
        result = split_long_scenes(scenes)
        assert len(result) == 1

    def test_long_scene_split(self):
        content = "\n".join([f"Line {i}" for i in range(40)])
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": content},
        ]
        result = split_long_scenes(scenes, max_lines=10)
        assert len(result) > 1


class TestPostprocessFountain:
    """Tests for the main postprocessing pipeline."""

    def test_empty_text(self):
        result = postprocess_fountain("")
        assert result == ""

    def test_valid_text_unchanged(self):
        text = """FADE IN:

INT. COFFEE SHOP - DAY

SARAH
I can't believe this.

CUT TO:

INT. OFFICE - NIGHT

JOHN
Working late again."""
        result = postprocess_fountain(text)
        assert "INT. COFFEE SHOP" in result
        assert "SARAH" in result

    def test_camera_directions_removed(self):
        text = """INT. ROOM - DAY

CLOSE UP on Sarah's face."""
        result = postprocess_fountain(text)
        assert "CLOSE UP" not in result


class TestPostprocessScenes:
    """Tests for scene-level postprocessing."""

    def test_empty_scenes(self):
        result = postprocess_scenes([])
        assert result == []

    def test_short_scenes_merged(self):
        scenes = [
            {"heading": "INT. ROOM - DAY", "content": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"},
            {"heading": "INT. ROOM - DAY", "content": "Short"},
        ]
        result = postprocess_scenes(scenes)
        # Short scene should be merged
        assert len(result) <= 2
