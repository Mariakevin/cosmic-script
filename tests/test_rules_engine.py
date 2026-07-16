"""Tests for the rule-based screenplay conversion engine.

Covers dialogue extraction, scene break detection, location inference,
full pipeline conversion, and edge cases.
"""

from __future__ import annotations

import pytest

from cosmic_script.conversion.registry import CharacterRegistry
from cosmic_script.conversion.rules_engine import (
    ActionFormatter,
    DialogueExtractor,
    FountainAssembler,
    LocationInferencer,
    SceneBreakDetector,
    convert_chapter_with_rules,
    convert_with_rules,
)
from cosmic_script.export.validator import FountainValidator
from cosmic_script.models import Chapter, Screenplay


# ═══════════════════════════════════════════════════════════════════════════
# 1. Dialogue Extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestDialogueExtraction:
    """Tests for DialogueExtractor."""

    def setup_method(self) -> None:
        self.extractor = DialogueExtractor()

    def test_basic_attribution_after(self) -> None:
        """Quoted dialogue with attribution after."""
        text = '"Hello," said Sarah.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SARAH"
        assert results[0]["text"] == "Hello,"
        assert results[0]["vo"] is False

    def test_attribution_before(self) -> None:
        """Character name appears before the quote."""
        text = 'Sarah said, "Hello there."'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SARAH"
        assert results[0]["text"] == "Hello there."

    def test_no_attribution(self) -> None:
        """Dialogue with no attribution character."""
        text = '"Just dialogue here."'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "UNKNOWN"
        assert results[0]["text"] == "Just dialogue here."

    def test_multi_sentence_dialogue(self) -> None:
        """Multiple sentences inside one quoted block."""
        text = '"First sentence. Second sentence." she said.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert "First sentence." in results[0]["text"]
        assert "Second sentence." in results[0]["text"]

    def test_interruption_preserved(self) -> None:
        """Em dash interruption in dialogue is preserved."""
        text = '"I was\u2014" she stopped.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert "\u2014" in results[0]["text"]

    def test_curly_quotes(self) -> None:
        """Curly (smart) quotes are handled."""
        text = "\u201cHello,\u201d said Sarah."
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SARAH"
        assert "Hello," in results[0]["text"]

    def test_vo_detection(self) -> None:
        """Thought/self-talk triggers V.O. detection."""
        text = '"I should leave." she thought to herself.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["vo"] is True

    def test_empty_text(self) -> None:
        """Empty input returns empty list."""
        assert self.extractor.extract("") == []
        assert self.extractor.extract("   ") == []

    def test_no_dialogue(self) -> None:
        """Text with no quotes returns empty list."""
        text = "Sarah walked into the room quietly."
        assert self.extractor.extract(text) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. Scene Break Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestSceneBreakDetection:
    """Tests for SceneBreakDetector."""

    def setup_method(self) -> None:
        self.detector = SceneBreakDetector()

    def test_location_shift(self) -> None:
        """Location shift creates new scene."""
        text = (
            "Sarah sat in the office.\n\n"
            "At home, the phone rang loudly."
        )
        scenes = self.detector.detect(text)
        assert len(scenes) >= 2

    def test_time_shift(self) -> None:
        """Time shift creates new scene."""
        text = (
            "That evening they ate dinner.\n\n"
            "The next morning, the sun rose."
        )
        scenes = self.detector.detect(text)
        assert len(scenes) >= 2

    def test_no_shift(self) -> None:
        """Continuation keeps same scene."""
        text = (
            "Sarah walked down the hall.\n\n"
            "She continued toward the door."
        )
        scenes = self.detector.detect(text)
        assert len(scenes) == 1

    def test_section_break(self) -> None:
        """Section break markers create new scene."""
        text = (
            "The first part ended.\n\n"
            "***\n\n"
            "The second part began."
        )
        scenes = self.detector.detect(text)
        assert len(scenes) >= 2

    def test_empty_text(self) -> None:
        """Empty input returns empty list."""
        assert self.detector.detect("") == []
        assert self.detector.detect("   ") == []

    def test_single_paragraph(self) -> None:
        """Single paragraph is one scene."""
        scenes = self.detector.detect("Just one paragraph here.")
        assert len(scenes) == 1
        assert len(scenes[0]["paragraphs"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. Location Inference
# ═══════════════════════════════════════════════════════════════════════════


class TestLocationInference:
    """Tests for LocationInferencer."""

    def setup_method(self) -> None:
        self.inferencer = LocationInferencer()

    def test_indoor_location(self) -> None:
        """Kitchen text infers INT."""
        heading = self.inferencer.infer(["She cooked in the kitchen."])
        assert heading.startswith("INT.")
        assert "KITCHEN" in heading

    def test_outdoor_location(self) -> None:
        """Park text infers EXT."""
        heading = self.inferencer.infer(["He ran through the park."])
        assert heading.startswith("EXT.")
        assert "PARK" in heading

    def test_time_of_day(self) -> None:
        """Night keyword infers NIGHT."""
        heading = self.inferencer.infer(["They met at night in the bar."])
        assert "NIGHT" in heading

    def test_default_inference(self) -> None:
        """No cues defaults to INT. LOCATION - DAY."""
        heading = self.inferencer.infer(["Something happened somewhere."])
        assert heading.startswith("INT.")
        assert "DAY" in heading

    def test_morning_keyword(self) -> None:
        """Morning keyword infers MORNING."""
        heading = self.inferencer.infer(["Early morning in the office."])
        assert "MORNING" in heading

    def test_evening_keyword(self) -> None:
        """Evening keyword infers EVENING."""
        heading = self.inferencer.infer(["In the evening at the beach."])
        assert "EVENING" in heading


# ═══════════════════════════════════════════════════════════════════════════
# 4. Action Formatting
# ═══════════════════════════════════════════════════════════════════════════


class TestActionFormatting:
    """Tests for ActionFormatter."""

    def setup_method(self) -> None:
        self.formatter = ActionFormatter()

    def test_strip_inner_thought(self) -> None:
        """Inner thought tags are stripped but surrounding text preserved."""
        result = self.formatter.format_paragraph(
            "He thought it was a good idea to leave."
        )
        # The regex strips "He thought " — remaining text is preserved
        assert "good idea" in result
        assert "leave" in result

    def test_preserves_paragraph(self) -> None:
        """Normal text passes through unchanged."""
        text = "Sarah walked into the room with purpose."
        assert self.formatter.format_paragraph(text) == text

    def test_empty_input(self) -> None:
        """Empty input returns empty string."""
        assert self.formatter.format_paragraph("") == ""
        assert self.formatter.format_paragraph("   ") == ""


# ═══════════════════════════════════════════════════════════════════════════
# 5. Full Pipeline
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """Tests for the complete conversion pipeline."""

    def test_short_story_with_dialogue(self) -> None:
        """Short story with dialogue produces valid Screenplay."""
        text = (
            'In the kitchen, Sarah chopped vegetables.\n\n'
            '"Hello," said John as he entered.\n\n'
            '"Hi there," Sarah replied.\n\n'
            "She continued cooking dinner."
        )
        screenplay = convert_with_rules(text, title="Test", author="Tester")
        assert isinstance(screenplay, Screenplay)
        assert screenplay.title == "Test"
        assert screenplay.author == "Tester"
        assert len(screenplay.scenes) >= 1
        assert len(screenplay.elements) > 0

    def test_no_dialogue(self) -> None:
        """Pure narration produces action-only screenplay."""
        text = (
            "The sun rose over the mountains.\n\n"
            "Birds sang in the early morning light."
        )
        screenplay = convert_with_rules(text)
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) >= 1
        # All elements should be action (no character/dialogue)
        for el in screenplay.elements:
            assert el.element_type.value in ("scene_heading", "action")

    def test_single_paragraph(self) -> None:
        """Single paragraph produces single scene."""
        text = "She walked into the room quietly."
        screenplay = convert_with_rules(text)
        assert len(screenplay.scenes) == 1

    def test_output_validates_fountain(self) -> None:
        """Output passes FountainValidator."""
        text = (
            'In the office, Bob typed on his computer.\n\n'
            '"Are you done yet?" asked Alice.\n\n'
            '"Almost," Bob replied.'
        )
        screenplay = convert_with_rules(text, title="Validation Test")

        # Build fountain text from elements
        from cosmic_script.export.fountain import generate_fountain
        fountain_text = generate_fountain(screenplay)

        validator = FountainValidator()
        result = validator.validate(fountain_text)
        # May have warnings but should be structurally valid
        # (no critical errors that break parsing)
        critical_codes = {"E1", "E2", "E3", "E4"}
        critical_errors = [
            e for e in result["errors"] if e["code"] in critical_codes
        ]
        assert len(critical_errors) == 0, (
            f"Critical Fountain errors: {critical_errors}"
        )

    def test_multi_scene_conversion(self) -> None:
        """Multiple scene breaks produce multiple scenes."""
        text = (
            "In the kitchen, Alice cooked.\n\n"
            "At the park, Bob ran.\n\n"
            "The next morning at the office, they met."
        )
        screenplay = convert_with_rules(text)
        assert len(screenplay.scenes) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# 6. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_text(self) -> None:
        """Empty text produces empty screenplay."""
        screenplay = convert_with_rules("")
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) == 0
        assert len(screenplay.elements) == 0

    def test_only_dialogue(self) -> None:
        """Text with only dialogue, no narration."""
        text = (
            '"Hello there."\n\n'
            '"How are you?"\n\n'
            '"Fine, thanks."'
        )
        screenplay = convert_with_rules(text)
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) >= 1

    def test_nested_quotes(self) -> None:
        """Nested quotes inside dialogue."""
        text = 'He said, "She told me, \'Go away\'."'
        screenplay = convert_with_rules(text)
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) >= 1

    def test_chapter_conversion(self) -> None:
        """convert_chapter_with_rules produces Scene list."""
        chapter = Chapter(
            number=1,
            text=(
                'In the kitchen, Alice cooked.\n\n'
                '"Hello," said Bob.\n\n'
                'At the park, they walked together.'
            ),
        )
        registry = CharacterRegistry()
        scenes = convert_chapter_with_rules(chapter, registry)
        assert len(scenes) >= 1
        assert all(s.heading.startswith(("INT.", "EXT.")) for s in scenes)

    def test_chapter_empty_text(self) -> None:
        """Empty chapter text returns empty list."""
        chapter = Chapter(number=1, text="")
        registry = CharacterRegistry()
        scenes = convert_chapter_with_rules(chapter, registry)
        assert scenes == []

    def test_registry_updated(self) -> None:
        """Character registry is updated after conversion."""
        chapter = Chapter(
            number=1,
            text='"Hello," said Alice. Bob replied, "Hi."',
        )
        registry = CharacterRegistry()
        convert_chapter_with_rules(chapter, registry)
        # At least one character should be registered
        assert len(registry.characters) > 0
