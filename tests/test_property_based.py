"""Property-based tests using Hypothesis for deterministic screenplay systems.

Tests invariants that must hold for ANY valid input across:
- Fountain validator roundtrip
- Auto-fix idempotency
- Fountain generation
- Rules engine conversion
- Character name casing
"""

import re

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from cosmic_script.export.validator import FountainValidator
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.conversion.rules_engine import convert_with_rules
from cosmic_script.models import Screenplay, ScreenplayElement, Scene


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid scene heading prefixes
_SCENE_PREFIXES = ["INT.", "EXT.", "INT/EXT.", "I/E."]
_TIMES = [
    "DAY",
    "NIGHT",
    "DAWN",
    "MORNING",
    "AFTERNOON",
    "DUSK",
    "EVENING",
    "MIDNIGHT",
    "LATER",
    "CONTINUOUS",
]


def _valid_scene_heading() -> st.SearchStrategy[str]:
    """Generate a valid Fountain scene heading."""
    prefix = st.sampled_from(_SCENE_PREFIXES)
    location = st.from_regex(r"[A-Z][A-Z\s]{1,20}", fullmatch=True)
    time = st.sampled_from(_TIMES)
    return st.tuples(prefix, location, time).map(lambda t: f"{t[0]} {t[1].strip()} - {t[2]}")


def _valid_character_name() -> st.SearchStrategy[str]:
    """Generate a valid uppercase character name (1-3 words, min 2 chars)."""
    word = st.from_regex(r"[A-Z]{2,10}", fullmatch=True)
    return st.tuples(
        word,
        st.one_of(st.just(""), st.just(" ")).filter(lambda s: True),
    ).map(lambda t: t[0] + t[1] + t[0][:3] if t[1] else t[0])


def _valid_dialogue() -> st.SearchStrategy[str]:
    """Generate simple dialogue text."""
    return st.from_regex(r"[A-Za-z\s,.\!?]{5,60}", fullmatch=False)


def _fountain_element() -> st.SearchStrategy[str]:
    """Generate a single valid Fountain element."""
    return st.one_of(
        _valid_scene_heading(),
        _valid_character_name(),
        _valid_dialogue(),
        st.just("Some action line describing what happens."),
        st.just("FADE IN:"),
        st.just("FADE OUT."),
    )


def _fountain_text() -> st.SearchStrategy[str]:
    """Generate a multi-line Fountain document with at least one scene heading."""
    heading = _valid_scene_heading()
    char_name = _valid_character_name()
    dialogue = _valid_dialogue()
    action = st.just("John sits at his desk, typing furiously.")

    # Build a minimal valid Fountain: heading + action + character + dialogue
    def build_fountain(h, c, d, a):
        return f"{h}\n\n{a}\n\n{c}\n{d}\n\nFADE OUT."

    return st.tuples(heading, char_name, dialogue, action).map(lambda t: build_fountain(*t))


def _novel_text() -> st.SearchStrategy[str]:
    """Generate simple novel-style text suitable for rules engine."""
    location_words = st.sampled_from(
        [
            "in the kitchen",
            "at the park",
            "in the office",
            "at the beach",
            "in the car",
            "at the restaurant",
        ]
    )
    action_words = st.sampled_from(
        [
            "She walked forward.",
            "He sat down.",
            "They looked at each other.",
            "The sun was setting.",
            "Rain fell from the sky.",
            "The phone rang.",
            "A door opened.",
        ]
    )
    time_words = st.sampled_from(["morning", "night", "afternoon", "evening"])

    def build_paragraph(loc, act, time):
        return f"{loc.capitalize()}, {act} It was {time}."

    return st.tuples(location_words, action_words, time_words).map(lambda t: build_paragraph(*t))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidatorRoundtrip:
    """Any valid Fountain text -> validate() -> valid=True."""

    @given(
        heading=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ ", min_size=3, max_size=60),
        action=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=5, max_size=200)
        .filter(
            lambda t: (
                not re.match(
                    r"^(well|oh|hey|hi|hello|yeah|no|yes|okay|sure|sorry|"
                    r"please|thanks|wait|listen|look|so|but|and|then|"
                    r"actually|really|right|Hmm|Um|Ah)",
                    t.strip(),
                    re.IGNORECASE,
                )
            )
        )
        .filter(lambda t: not t.strip().endswith(("?", "!")))
        .filter(lambda t: not t.strip().startswith(('"', "'", "`"))),
        dialogue=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=3, max_size=200),
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_valid_fountain_always_validates(
        self, heading: str, action: str, dialogue: str
    ) -> None:
        """A well-formed Fountain document should always pass validation."""
        fountain = f"INT. {heading} - DAY\n\n{action}\n\nBOB\n{dialogue}"
        validator = FountainValidator()
        result = validator.validate(fountain)
        critical = {e["code"] for e in result["errors"]} & {"E1", "E2", "E3", "E4", "E5"}
        assert len(critical) == 0, f"Critical errors: {result['errors']}"


class TestAutoFixIdempotency:
    """auto_fix(auto_fix(text)) == auto_fix(text)."""

    @given(text=_fountain_text())
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_auto_fix_is_idempotent(self, text: str) -> None:
        """Applying auto_fix twice must produce the same result."""
        validator = FountainValidator()
        once = validator.auto_fix(text)
        twice = validator.auto_fix(once)
        assert once == twice


class TestFountainGeneration:
    """generate_fountain(screenplay) produces text with scene headings."""

    def test_generates_text_with_scene_headings(self) -> None:
        """Output must contain at least one INT./EXT. scene heading."""
        screenplay = Screenplay(
            title="Test",
            author="Tester",
            elements=[
                ScreenplayElement(element_type="scene_heading", text="INT. OFFICE - DAY"),
                ScreenplayElement(element_type="action", text="John enters."),
                ScreenplayElement(element_type="character", text="JOHN"),
                ScreenplayElement(element_type="dialogue", text="Hello world."),
            ],
        )
        text = generate_fountain(screenplay)
        assert "INT. OFFICE - DAY" in text
        assert re.search(r"(INT\.|EXT\.)", text)

    def test_empty_screenplay_returns_empty(self) -> None:
        """Empty screenplay produces empty or minimal text."""
        screenplay = Screenplay()
        text = generate_fountain(screenplay)
        assert text == "" or text.strip() == ""

    @given(
        title=st.text(min_size=1, max_size=30).filter(lambda s: s.isascii()),
        scene_text=_valid_scene_heading(),
    )
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_title_appears_in_output(self, title: str, scene_text: str) -> None:
        """Title should appear in the generated Fountain output."""
        assume("\n" not in title and "\r" not in title)
        screenplay = Screenplay(
            title=title,
            elements=[
                ScreenplayElement(element_type="scene_heading", text=scene_text),
            ],
        )
        text = generate_fountain(screenplay)
        assert title in text


class TestRulesEngineConversion:
    """convert_with_rules(text) produces valid Screenplay object."""

    @given(text=_novel_text())
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_returns_screenplay_object(self, text: str) -> None:
        """Rules engine must return a Screenplay instance."""
        result = convert_with_rules(text)
        assert isinstance(result, Screenplay)

    @given(text=_novel_text())
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_has_at_least_one_scene(self, text: str) -> None:
        """Conversion should produce at least one scene."""
        result = convert_with_rules(text)
        assert len(result.scenes) >= 1

    @given(text=_novel_text())
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_scene_headings_are_valid_format(self, text: str) -> None:
        """Scene headings should start with INT. or EXT."""
        result = convert_with_rules(text)
        for scene in result.scenes:
            assert scene.heading.startswith(("INT.", "EXT.")), f"Invalid heading: {scene.heading}"


class TestCharacterNamesUppercase:
    """All character names in output are uppercase."""

    @given(text=_novel_text())
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_character_elements_are_uppercase(self, text: str) -> None:
        """All CHARACTER elements in the screenplay must be uppercase."""
        result = convert_with_rules(text)
        for el in result.elements:
            if el.element_type.value == "character":
                name = el.text.strip()
                # Remove parenthetical extension before checking case
                clean = re.sub(r"\s*\(.*?\)\s*$", "", name)
                if clean:
                    assert clean == clean.upper(), f"Character name not uppercase: {clean!r}"


class TestInvariantFountainValidator:
    """Multi-input invariant tests for the validator."""

    def test_empty_string_always_valid(self) -> None:
        """Empty string always validates as valid."""
        v = FountainValidator()
        assert v.validate("")["valid"] is True
        assert v.validate("\n")["valid"] is True
        assert v.validate("  ")["valid"] is True

    def test_auto_fix_empty_returns_empty(self) -> None:
        """auto_fix on empty/whitespace string returns cleaned string."""
        v = FountainValidator()
        assert v.auto_fix("") == ""
        assert v.auto_fix(" ") == ""


class TestBoundaryConditions:
    """Boundary and edge-case tests."""

    def test_very_long_scene_heading(self) -> None:
        """Extremely long scene heading should still validate."""
        long_location = "A" * 200
        text = f"INT. {long_location} - DAY\n\nAction."
        v = FountainValidator()
        result = v.validate(text)
        # Should be valid (no character issues)
        errors = [e for e in result["errors"] if e["code"] == "E1"]
        assert len(errors) == 0

    def test_single_character_name(self) -> None:
        """Two-character name should be detected by parser."""
        text = "INT. ROOM - DAY\n\nAL\nHello."
        v = FountainValidator()
        result = v.validate(text)
        assert "AL" in result["characters"]

    def test_multiple_scene_headings(self) -> None:
        """Multiple scene headings in sequence should all validate."""
        text = (
            "INT. OFFICE - DAY\n\nAction.\n\n"
            "EXT. PARK - NIGHT\n\nMore action.\n\n"
            "INT. HOUSE - MORNING\n\nFinal action."
        )
        v = FountainValidator()
        result = v.validate(text)
        # No E1 errors for properly prefixed headings
        errors = [e for e in result["errors"] if e["code"] == "E1"]
        assert len(errors) == 0
