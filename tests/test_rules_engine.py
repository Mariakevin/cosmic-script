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
        text = "Sarah sat in the office.\n\nAt home, the phone rang loudly."
        scenes = self.detector.detect(text)
        assert len(scenes) >= 2

    def test_time_shift(self) -> None:
        """Time shift creates new scene."""
        text = "That evening they ate dinner.\n\nThe next morning, the sun rose."
        scenes = self.detector.detect(text)
        assert len(scenes) >= 2

    def test_no_shift(self) -> None:
        """Continuation keeps same scene."""
        text = "Sarah walked down the hall.\n\nShe continued toward the door."
        scenes = self.detector.detect(text)
        assert len(scenes) == 1

    def test_section_break(self) -> None:
        """Section break markers create new scene."""
        text = "The first part ended.\n\n***\n\nThe second part began."
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
        result = self.formatter.format_paragraph("He thought it was a good idea to leave.")
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
            "In the kitchen, Sarah chopped vegetables.\n\n"
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
        text = "The sun rose over the mountains.\n\nBirds sang in the early morning light."
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
            "In the office, Bob typed on his computer.\n\n"
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
        critical_errors = [e for e in result["errors"] if e["code"] in critical_codes]
        assert len(critical_errors) == 0, f"Critical Fountain errors: {critical_errors}"

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
        text = '"Hello there."\n\n"How are you?"\n\n"Fine, thanks."'
        screenplay = convert_with_rules(text)
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) >= 1

    def test_nested_quotes(self) -> None:
        """Nested quotes inside dialogue."""
        text = "He said, \"She told me, 'Go away'.\""
        screenplay = convert_with_rules(text)
        assert isinstance(screenplay, Screenplay)
        assert len(screenplay.scenes) >= 1

    def test_chapter_conversion(self) -> None:
        """convert_chapter_with_rules produces Scene list."""
        chapter = Chapter(
            number=1,
            text=(
                "In the kitchen, Alice cooked.\n\n"
                '"Hello," said Bob.\n\n'
                "At the park, they walked together."
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


# ═══════════════════════════════════════════════════════════════════════════
# 7. IMP-1: Expanded Dialogue Attribution Verbs
# ═══════════════════════════════════════════════════════════════════════════


class TestExpandedAttributionVerbs:
    """Tests for expanded dialogue attribution verb coverage."""

    def setup_method(self) -> None:
        self.extractor = DialogueExtractor()

    def test_soft_murmured(self) -> None:
        text = '"I don\'t know," Jane murmured.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "JANE"

    def test_soft_breathed(self) -> None:
        text = '"Careful," he breathed.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_soft_stammered(self) -> None:
        text = '"W-wait," Tom stammered.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "TOM"

    def test_loud_bellowed(self) -> None:
        text = '"Get out!" the captain bellowed.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "THE CAPTAIN"

    def test_loud_roared(self) -> None:
        text = '"No more!" Marcus roared.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "MARCUS"

    def test_loud_snapped(self) -> None:
        text = '"Enough!" she snapped.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_neutral_declared(self) -> None:
        text = '"It is done," the elder declared.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "THE ELDER"

    def test_neutral_proclaimed(self) -> None:
        text = '"We win!" he proclaimed.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_neutral_observed(self) -> None:
        text = '"Nice weather," she observed.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_emotional_sobbed(self) -> None:
        text = '"I can\'t," Mary sobbed.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "MARY"

    def test_emotional_gasped(self) -> None:
        text = '"Run!" he gasped.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_emotional_wept(self) -> None:
        text = '"It\'s over," she wept.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_quick_blurted(self) -> None:
        text = '"I love you," she blurted.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_quick_burst_out(self) -> None:
        text = '"I quit!" he burst out.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_quick_interjected(self) -> None:
        text = '"Wait," Sarah interjected.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SARAH"

    def test_formal_conceded(self) -> None:
        text = '"You\'re right," he conceded.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_formal_retorted(self) -> None:
        text = '"Not likely," she retorted.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_casual_grumbled(self) -> None:
        text = '"Fine," he grumbled.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_casual_complained(self) -> None:
        text = '"This is unfair," she complained.'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_before_pattern_stammered(self) -> None:
        text = 'Tom stammered, "I-I don\'t know."'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "TOM"

    def test_before_pattern_proclaimed(self) -> None:
        text = 'Marcus proclaimed, "Victory is ours!"'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "MARCUS"

    def test_before_pattern_blurted(self) -> None:
        text = 'She blurted, "I can\'t believe it!"'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "SHE"

    def test_before_pattern_retorted(self) -> None:
        text = 'He retorted, "No way."'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "HE"

    def test_before_pattern_grumbled(self) -> None:
        text = 'Bob grumbled, "Whatever."'
        results = self.extractor.extract(text)
        assert len(results) == 1
        assert results[0]["character"] == "BOB"


# ═══════════════════════════════════════════════════════════════════════════
# 8. IMP-2: Fountain Elements in Conversion
# ═══════════════════════════════════════════════════════════════════════════


class TestFountainElements:
    """Tests for Fountain element detection in _scene_to_elements."""

    def test_centered_text_detected(self) -> None:
        """Lines like >Title< become CENTERED elements."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content=">A Movie Title<")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        centered = [e for e in elements if e.element_type == ElementType.CENTERED]
        assert len(centered) == 1
        assert centered[0].text == ">A Movie Title<"

    def test_section_heading_detected(self) -> None:
        """Lines starting with # become SECTION elements."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content="# Act One")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        sections = [e for e in elements if e.element_type == ElementType.SECTION]
        assert len(sections) == 1
        assert sections[0].text == "# Act One"

    def test_synopsis_detected(self) -> None:
        """Lines starting with = become SYNOPSIS elements."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content="= This is a synopsis line")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        synopses = [e for e in elements if e.element_type == ElementType.SYNOPSIS]
        assert len(synopses) == 1
        assert synopses[0].text == "= This is a synopsis line"

    def test_lyric_detected(self) -> None:
        """Lines starting with ~ become LYRIC elements."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content="~ La la la")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        lyrics = [e for e in elements if e.element_type == ElementType.LYRIC]
        assert len(lyrics) == 1
        assert lyrics[0].text == "~ La la la"

    def test_page_break_detected(self) -> None:
        """Lines with === become PAGE_BREAK elements."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content="===")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        breaks = [e for e in elements if e.element_type == ElementType.PAGE_BREAK]
        assert len(breaks) == 1

    def test_normal_action_not_misclassified(self) -> None:
        """Normal action lines remain ACTION, not misclassified."""
        from cosmic_script.conversion.rules_engine import FountainAssembler
        from cosmic_script.models import Scene, ScreenplayElement, ElementType

        assembler = FountainAssembler(title="T", author="A")
        scene = Scene(heading="INT. ROOM - DAY", content="She walked across the room.")
        elements: list[ScreenplayElement] = []
        assembler._scene_to_elements(scene, elements)
        actions = [e for e in elements if e.element_type == ElementType.ACTION]
        assert len(actions) == 1

    def test_full_pipeline_with_section(self) -> None:
        """Full pipeline handles section markers in content."""
        text = "In the office, Bob typed.\n\n# Chapter Break\n\nAt the park, Alice ran."
        screenplay = convert_with_rules(text)
        section_elements = [e for e in screenplay.elements if e.element_type.value == "section"]
        assert len(section_elements) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 9. IMP-3: Action Line Condensation
# ═══════════════════════════════════════════════════════════════════════════


class TestActionCondensation:
    """Tests for ActionFormatter._condense_action."""

    def setup_method(self) -> None:
        self.formatter = ActionFormatter()

    def test_remove_filter_word_very(self) -> None:
        result = self.formatter._condense_action("She was very tired.")
        assert "very" not in result.lower().split()

    def test_remove_filter_word_really(self) -> None:
        result = self.formatter._condense_action("He was really fast.")
        assert "really" not in result.lower().split()

    def test_remove_filter_word_quite(self) -> None:
        result = self.formatter._condense_action("It was quite nice.")
        assert "quite" not in result.lower().split()

    def test_remove_filter_word_somewhat(self) -> None:
        result = self.formatter._condense_action("She was somewhat angry.")
        assert "somewhat" not in result.lower().split()

    def test_remove_filter_word_rather(self) -> None:
        result = self.formatter._condense_action("He was rather pleased.")
        assert "rather" not in result.lower().split()

    def test_remove_filter_word_fairly(self) -> None:
        result = self.formatter._condense_action("It was fairly obvious.")
        assert "fairly" not in result.lower().split()

    def test_remove_unnecessary_that(self) -> None:
        result = self.formatter._condense_action("He realized that she was gone.")
        assert "that" not in result.lower().split()

    def test_keep_necessary_that(self) -> None:
        """'that' as a demonstrative pronoun should be kept."""
        result = self.formatter._condense_action("He grabbed that book.")
        assert "that" in result.lower().split()

    def test_simplify_began_to(self) -> None:
        result = self.formatter._condense_action("He began to run.")
        assert "began" not in result.lower()
        assert "run" in result.lower()

    def test_simplify_started_to(self) -> None:
        result = self.formatter._condense_action("She started to sing.")
        assert "started" not in result.lower()
        assert "sing" in result.lower()

    def test_remove_redundant_adverb(self) -> None:
        result = self.formatter._condense_action("She whispered softly.")
        assert "softly" not in result.lower()
        assert "whispered" in result.lower()

    def test_limit_length(self) -> None:
        """Action lines should be around 58 chars or shorter."""
        long_text = "The very really incredibly quite extraordinarily long sentence went on and on about nothing important at all forever and ever amen."
        result = self.formatter._condense_action(long_text)
        # Should be truncated or condensed to ~58 chars
        assert len(result) <= 80  # Allow some margin

    def test_empty_input(self) -> None:
        assert self.formatter._condense_action("") == ""

    def test_whitespace_only(self) -> None:
        assert self.formatter._condense_action("   ") == ""

    def test_single_word(self) -> None:
        result = self.formatter._condense_action("Run!")
        assert result == "Run!"

    def test_format_paragraph_uses_condense(self) -> None:
        """format_paragraph should apply condensation."""
        result = self.formatter.format_paragraph("He began to run very quickly across the field.")
        assert "began" not in result.lower()
        assert "very" not in result.lower().split()


# ═══════════════════════════════════════════════════════════════════════════
# 10. IMP-4: Expanded Location Gazetteers
# ═══════════════════════════════════════════════════════════════════════════


class TestExpandedLocationKeywords:
    """Tests for expanded INT/EXT keyword gazetteers."""

    def setup_method(self) -> None:
        self.inferencer = LocationInferencer()

    def test_int_spaceship(self) -> None:
        heading = self.inferencer.infer(["Inside the spaceship, alarms blared."])
        assert heading.startswith("INT.")
        assert "SPACESHIP" in heading

    def test_int_cockpit(self) -> None:
        heading = self.inferencer.infer(["The pilot sat in the cockpit."])
        assert heading.startswith("INT.")
        assert "COCKPIT" in heading

    def test_int_laboratory(self) -> None:
        heading = self.inferencer.infer(["She worked in the lab all night."])
        assert heading.startswith("INT.")
        assert "LAB" in heading

    def test_int_courtroom(self) -> None:
        heading = self.inferencer.infer(["The trial was held in the courtroom."])
        assert heading.startswith("INT.")
        assert "COURTROOM" in heading

    def test_int_dressing_room(self) -> None:
        heading = self.inferencer.infer(["She changed in the dressing room."])
        assert heading.startswith("INT.")
        assert "DRESSING ROOM" in heading

    def test_int_green_room(self) -> None:
        heading = self.inferencer.infer(["The host waited in the green room."])
        assert heading.startswith("INT.")
        assert "GREEN ROOM" in heading

    def test_int_penthouse(self) -> None:
        heading = self.inferencer.infer(["They lived in the penthouse suite."])
        assert heading.startswith("INT.")
        assert "PENTHOUSE" in heading

    def test_int_boardroom(self) -> None:
        heading = self.inferencer.infer(["The meeting was in the boardroom."])
        assert heading.startswith("INT.")
        assert "BOARDROOM" in heading

    def test_int_cafeteria(self) -> None:
        heading = self.inferencer.infer(["They ate lunch in the cafeteria."])
        assert heading.startswith("INT.")
        assert "CAFETERIA" in heading

    def test_int_nursery(self) -> None:
        heading = self.inferencer.infer(["The baby slept in the nursery."])
        assert heading.startswith("INT.")
        assert "NURSERY" in heading

    def test_ext_plaza(self) -> None:
        heading = self.inferencer.infer(["They met at the plaza."])
        assert heading.startswith("EXT.")
        assert "PLAZA" in heading

    def test_ext_tunnel(self) -> None:
        heading = self.inferencer.infer(["The car entered the tunnel."])
        assert heading.startswith("EXT.")
        assert "TUNNEL" in heading

    def test_ext_pier(self) -> None:
        heading = self.inferencer.infer(["They fished from the pier."])
        assert heading.startswith("EXT.")
        assert "PIER" in heading

    def test_ext_harbor(self) -> None:
        heading = self.inferencer.infer(["Ships docked at the harbor."])
        assert heading.startswith("EXT.")
        assert "HARBOR" in heading

    def test_ext_marina(self) -> None:
        heading = self.inferencer.infer(["The boat was at the marina."])
        assert heading.startswith("EXT.")
        assert "MARINA" in heading

    def test_ext_trail(self) -> None:
        heading = self.inferencer.infer(["They hiked along the trail."])
        assert heading.startswith("EXT.")
        assert "TRAIL" in heading

    def test_ext_boardwalk(self) -> None:
        heading = self.inferencer.infer(["They walked the boardwalk at sunset."])
        assert heading.startswith("EXT.")
        assert "BOARDWALK" in heading

    def test_ext_causeway(self) -> None:
        heading = self.inferencer.infer(["They drove across the causeway."])
        assert heading.startswith("EXT.")
        assert "CAUSEWAY" in heading

    def test_ext_cul_de_sac(self) -> None:
        heading = self.inferencer.infer(["The kids played in the cul-de-sac."])
        assert heading.startswith("EXT.")
        assert "CUL-DE-SAC" in heading

    def test_ext_helipad(self) -> None:
        heading = self.inferencer.infer(["The helicopter landed on the helipad."])
        assert heading.startswith("EXT.")
        assert "HELIPAD" in heading

    def test_int_archive(self) -> None:
        heading = self.inferencer.infer(["She found the document in the archive."])
        assert heading.startswith("INT.")
        assert "ARCHIVE" in heading

    def test_int_bunker(self) -> None:
        heading = self.inferencer.infer(["They hid in the bunker."])
        assert heading.startswith("INT.")
        assert "BUNKER" in heading

    def test_ext_breakwater(self) -> None:
        heading = self.inferencer.infer(["Waves crashed against the breakwater."])
        assert heading.startswith("EXT.")
        assert "BREAKWATER" in heading

    def test_ext_levee(self) -> None:
        heading = self.inferencer.infer(["They walked along the levee."])
        assert heading.startswith("EXT.")
        assert "LEVEE" in heading

    def test_int_atelier(self) -> None:
        heading = self.inferencer.infer(["The artist worked in the atelier."])
        assert heading.startswith("INT.")
        assert "ATELIER" in heading
