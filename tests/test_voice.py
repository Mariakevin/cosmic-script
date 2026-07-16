"""Tests for Character Voice Analysis."""
import pytest

from cosmic_script.models import Screenplay, Scene, ScreenplayElement
from cosmic_script.analysis.voice import CharacterVoice, analyze_voices, _classify_speaking_style, _classify_emotional_tone


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestClassifySpeakingStyle:
    """Coverage: boundary, input-variation."""

    def test_terse_short_lines(self) -> None:
        """Short average line length → terse."""
        assert _classify_speaking_style(3.0) == "terse"

    def test_casual_medium_lines(self) -> None:
        """Medium average line length → casual."""
        assert _classify_speaking_style(8.0) == "casual"

    def test_verbose_long_lines(self) -> None:
        """Long average line length → verbose."""
        assert _classify_speaking_style(25.0) == "verbose"

    def test_formal_very_long_lines(self) -> None:
        """Very long average line length → formal."""
        assert _classify_speaking_style(60.0) == "formal"

    def test_boundary_terse(self) -> None:
        """Boundary: exactly 5 words → terse."""
        assert _classify_speaking_style(5.0) == "terse"

    def test_boundary_casual(self) -> None:
        """Boundary: exactly 6 words → casual."""
        assert _classify_speaking_style(6.0) == "casual"

    def test_boundary_verbose(self) -> None:
        """Boundary: exactly 20 words → verbose."""
        assert _classify_speaking_style(20.0) == "verbose"


class TestClassifyEmotionalTone:
    """Coverage: happy-path, boundary, input-variation."""

    def test_neutral_text(self) -> None:
        """Text without emotional markers → neutral."""
        text = "I went to the store and bought some bread."
        assert _classify_emotional_tone(text) == "neutral"

    def test_angry_text(self) -> None:
        """Text with anger markers → angry."""
        text = "I hate this! You infuriate me with your arrogance!"
        assert _classify_emotional_tone(text) == "angry"

    def test_sad_text(self) -> None:
        """Text with sadness markers → sad."""
        text = "I'm so sorry. I miss you terribly. This is heartbreaking."
        assert _classify_emotional_tone(text) == "sad"

    def test_happy_text(self) -> None:
        """Text with joy markers → happy."""
        text = "I love this! What a wonderful, beautiful day!"
        assert _classify_emotional_tone(text) == "happy"

    def test_anxious_text(self) -> None:
        """Text with anxiety markers → anxious."""
        text = "I'm worried and nervous. What if something terrible happens?"
        assert _classify_emotional_tone(text) == "anxious"

    def test_empty_text_neutral(self) -> None:
        """Boundary: empty text → neutral."""
        assert _classify_emotional_tone("") == "neutral"


# ---------------------------------------------------------------------------
# CharacterVoice dataclass
# ---------------------------------------------------------------------------

class TestCharacterVoiceModel:
    """Coverage: happy-path, boundary."""

    def test_default_values(self) -> None:
        """CharacterVoice can be created with minimal args."""
        cv = CharacterVoice(name="JOHN", total_lines=0, avg_line_length=0.0, vocabulary_richness=0.0, common_words=[], speaking_style="neutral", emotional_tone="neutral")
        assert cv.name == "JOHN"
        assert cv.total_lines == 0

    def test_full_constructor(self) -> None:
        """CharacterVoice with all fields set."""
        cv = CharacterVoice(
            name="SARAH",
            total_lines=10,
            avg_line_length=15.5,
            vocabulary_richness=0.75,
            common_words=["the", "and", "you", "I", "to"],
            speaking_style="casual",
            emotional_tone="happy",
        )
        assert cv.avg_line_length == 15.5
        assert cv.vocabulary_richness == 0.75
        assert len(cv.common_words) == 5


# ---------------------------------------------------------------------------
# Integration tests for analyze_voices
# ---------------------------------------------------------------------------

class TestAnalyzeVoices:
    """Coverage: happy-path, boundary, input-variation, invariant."""

    def _make_screenplay(self, scenes: list[tuple[str, str]]) -> Screenplay:
        """Helper: create Screenplay from (heading, content) pairs."""
        return Screenplay(
            scenes=[Scene(heading=h, content=c) for h, c in scenes],
        )

    def test_single_character_single_line(self) -> None:
        """Happy-path: one character with one dialogue line."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "SARAH\nHello there."),
        ])
        result = analyze_voices(sp)
        assert len(result) == 1
        assert result[0].name == "SARAH"
        assert result[0].total_lines == 1
        assert result[0].avg_line_length > 0
        assert result[0].vocabulary_richness > 0

    def test_multiple_characters(self) -> None:
        """Happy-path: multiple characters are returned sorted by talkativeness."""
        sp = self._make_screenplay([
            ("INT. CAFE - DAY", "SARAH\nHi, how are you?\nJOHN\nGood, thanks."),
        ])
        result = analyze_voices(sp)
        assert len(result) == 2
        names = [v.name for v in result]
        assert "SARAH" in names
        assert "JOHN" in names

    def test_sorted_by_total_lines_descending(self) -> None:
        """Invariant: results sorted by total_lines (most talkative first)."""
        sp = self._make_screenplay([
            ("INT. OFFICE - DAY", "JOHN\nShort.\nJOHN\nAnother.\nJOHN\nThird.\nSARAH\nOne."),
        ])
        result = analyze_voices(sp)
        assert result[0].total_lines >= result[1].total_lines

    def test_character_with_zero_lines(self) -> None:
        """Boundary: character mentioned but with no dialogue is not included."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "Some action with no dialogue."),
        ])
        result = analyze_voices(sp)
        assert len(result) == 0

    def test_vocabulary_richness_calculation(self) -> None:
        """Happy-path: vocabulary richness is between 0 and 1."""
        sp = self._make_screenplay([
            ("INT. HALL - DAY", "SARAH\nThe same word the same word the same word."),
        ])
        result = analyze_voices(sp)
        # Many repeated words → low richness
        assert result[0].vocabulary_richness < 0.5

    def test_common_words_exclude_stop_words(self) -> None:
        """Invariant: common_words should not contain basic stop words."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "SARAH\nHello mystery world adventure quest."),
        ])
        result = analyze_voices(sp)
        assert len(result) == 1
        for word in result[0].common_words:
            assert word.lower() not in {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}

    def test_parentheticals_excluded_from_dialogue_count(self) -> None:
        """Invariant: parentheticals like (whispering) are not counted as dialogue."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "SARAH\n(whispering)\nHello."),
        ])
        result = analyze_voices(sp)
        assert result[0].total_lines == 1  # only "Hello." is dialogue

    def test_empty_screenplay(self) -> None:
        """Boundary: empty screenplay returns empty list."""
        sp = Screenplay()
        result = analyze_voices(sp)
        assert result == []

    def test_single_word_dialogue(self) -> None:
        """Boundary: single-word dialogue line."""
        sp = self._make_screenplay([
            ("INT. DOOR - DAY", "BOB\nHi."),
        ])
        result = analyze_voices(sp)
        assert result[0].total_lines == 1
        assert result[0].avg_line_length == 1.0

    def test_dialogue_with_punctuation(self) -> None:
        """Input-variation: dialogue with punctuation is handled."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "JOHN\nWhat? No! I can't believe it..."),
        ])
        result = analyze_voices(sp)
        assert result[0].total_lines == 1
        assert result[0].avg_line_length > 0

    def test_character_cue_variations(self) -> None:
        """Input-variation: character cues with extensions like (V.O.) are parsed."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "SARAH (V.O.)\nI remember it well.\nJOHN (O.S.)\nCome in."),
        ])
        result = analyze_voices(sp)
        assert len(result) == 2

    def test_results_have_all_fields(self) -> None:
        """Invariant: every CharacterVoice has all fields populated."""
        sp = self._make_screenplay([
            ("INT. ROOM - DAY", "JOHN\nHello world."),
        ])
        result = analyze_voices(sp)
        cv = result[0]
        assert cv.name is not None
        assert cv.total_lines >= 0
        assert cv.avg_line_length >= 0
        assert 0 <= cv.vocabulary_richness <= 1
        assert isinstance(cv.common_words, list)
        assert cv.speaking_style in ("formal", "casual", "terse", "verbose")
        assert cv.emotional_tone in ("neutral", "angry", "sad", "happy", "anxious")


# ---------------------------------------------------------------------------
# Edge cases & invariants for analyze_voices
# ---------------------------------------------------------------------------

class TestAnalyzeVoicesEdgeCases:

    def test_no_scenes_no_elements(self) -> None:
        """Screenplay with no scenes and no elements returns empty."""
        sp = Screenplay(title="Empty")
        assert analyze_voices(sp) == []

    def test_no_dialogue_in_scene(self) -> None:
        """Scene with only action returns empty."""
        sp = Screenplay(
            scenes=[Scene(heading="INT. ROOM - DAY", content="Just some action.")],
        )
        assert analyze_voices(sp) == []

    def test_multiple_scenes_same_character(self) -> None:
        """Character across multiple scenes has cumulative counts."""
        sp = Screenplay(
            scenes=[
                Scene(heading="INT. A - DAY", content="JOHN\nHello."),
                Scene(heading="INT. B - DAY", content="JOHN\nGoodbye."),
            ],
        )
        result = analyze_voices(sp)
        assert len(result) == 1
        assert result[0].total_lines == 2
