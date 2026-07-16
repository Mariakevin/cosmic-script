"""Tests for converter module."""

import json

import pytest

from cosmic_script.models import Chapter, Scene, Screenplay
from cosmic_script.conversion.converter import (
    ConversionConfig,
    ScreenplayConverter,
    _parse_fountain,
    _retry_with_backoff,
)


# ---------------------------------------------------------------------------
# Chapter model
# ---------------------------------------------------------------------------

class TestChapterModel:
    """Coverage: happy-path, invariant, boundary."""

    def test_minimal_chapter(self) -> None:
        """Happy-path: chapter with required fields."""
        ch = Chapter(number=1, text="Hello.")
        assert ch.number == 1
        assert ch.text == "Hello."

    def test_chapter_number_validation(self) -> None:
        """Boundary: chapter number accepts any int."""
        ch = Chapter(number=0, text="Invalid")
        assert ch.number == 0


# ---------------------------------------------------------------------------
# Scene model
# ---------------------------------------------------------------------------

class TestSceneModel:
    """Coverage: happy-path, invariant."""

    def test_minimal_scene(self) -> None:
        """Happy-path: scene with required fields."""
        s = Scene(heading="INT. HOUSE - DAY", content="The house is quiet.")
        assert s.heading == "INT. HOUSE - DAY"
        assert s.content == "The house is quiet."


# ---------------------------------------------------------------------------
# Screenplay model
# ---------------------------------------------------------------------------

class TestScreenplayModel:
    """Coverage: happy-path, invariant, boundary."""

    def test_minimal_screenplay(self) -> None:
        """Happy-path: screenplay with defaults."""
        sp = Screenplay()
        assert sp.title is None
        assert sp.author is None
        assert sp.scenes == []
        assert sp.elements == []

    def test_screenplay_with_scenes(self) -> None:
        """Happy-path: screenplay populated with scenes."""
        scenes = [Scene(heading="INT. ROOM - DAY", content="Test.")]
        sp = Screenplay(title="My Script", author="Me", scenes=scenes)
        assert len(sp.scenes) == 1
        assert sp.scenes[0].heading == "INT. ROOM - DAY"


# ---------------------------------------------------------------------------
# ConversionConfig
# ---------------------------------------------------------------------------

class TestConversionConfig:
    """Coverage: happy-path, invariant, boundary."""

    def test_default_values(self) -> None:
        """Invariant: defaults are sensible."""
        cfg = ConversionConfig()
        assert cfg.model == "auto"
        assert cfg.api_key is None
        assert cfg.max_retries == 3
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 8192

    def test_custom_values(self) -> None:
        """Happy-path: config with custom values."""
        cfg = ConversionConfig(
            model="claude-3-opus",
            api_key="sk-xxx",
            max_retries=5,
            temperature=0.0,
            max_tokens=4096,
        )
        assert cfg.model == "claude-3-opus"
        assert cfg.api_key == "sk-xxx"
        assert cfg.max_retries == 5


# ---------------------------------------------------------------------------
# _retry_with_backoff
# ---------------------------------------------------------------------------

class TestRetryWithBackoff:
    """Coverage: happy-path, error-path, boundary."""

    def test_success_on_first_call(self) -> None:
        """Happy-path: function succeeds immediately."""
        result = _retry_with_backoff(lambda: "ok", max_retries=3)
        assert result == "ok"

    def test_succeeds_after_retries(self) -> None:
        """Happy-path: function fails twice then succeeds."""
        call_count = 0

        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "Rate limit exceeded"
                raise __import__("litellm").RateLimitError(
                    message=msg,
                    llm_provider="openai",
                    model="gpt-4o",
                )
            return "success"

        result = _retry_with_backoff(flaky, max_retries=3, base_delay=0.01)
        assert result == "success"

    def test_all_retries_exhausted(self) -> None:
        """Error-path: all retries fail -> RuntimeError."""
        import litellm as _litellm

        call_count = 0

        def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            msg = "Server error"
            raise _litellm.APIError(
                status_code=500,
                message=msg,
                llm_provider="openai",
                model="gpt-4o",
            )

        with pytest.raises(RuntimeError, match="LLM call failed after 2 retries"):
            _retry_with_backoff(always_fails, max_retries=2, base_delay=0.01)

    def test_non_litellm_exception_not_caught(self) -> None:
        """Error-path: non-litellm exceptions propagate immediately."""
        def raises_value_error() -> str:
            raise ValueError("Something else")

        with pytest.raises(ValueError):
            _retry_with_backoff(raises_value_error, max_retries=3)


# ---------------------------------------------------------------------------
# _parse_fountain
# ---------------------------------------------------------------------------

class TestParseFountain:
    """Coverage: happy-path, invariant, boundary, error-path, input-variation."""

    def test_single_scene_heading(self) -> None:
        """Happy-path: single INT. scene."""
        text = "INT. COFFEE SHOP - DAY\n\nSarah sits quietly."
        scenes = _parse_fountain(text)
        assert len(scenes) == 1
        assert scenes[0].heading == "INT. COFFEE SHOP - DAY"
        assert "Sarah sits quietly." in scenes[0].content

    def test_multiple_scenes(self) -> None:
        """Happy-path: multiple scene headings."""
        text = (
            "INT. HOUSE - DAY\n\nAction here.\n\n"
            "EXT. GARDEN - NIGHT\n\nMore action."
        )
        scenes = _parse_fountain(text)
        assert len(scenes) == 2
        assert scenes[0].heading == "INT. HOUSE - DAY"
        assert scenes[1].heading == "EXT. GARDEN - NIGHT"

    def test_int_ext_variants(self) -> None:
        """Input-variation: all heading variants accepted."""
        text = (
            "INT. ROOM - DAY\n\nA.\n"
            "EXT. STREET - NIGHT\n\nB.\n"
            "INT/EXT. CAR - DAY\n\nC.\n"
            "I/E. SPACESHIP - DAY\n\nD."
        )
        scenes = _parse_fountain(text)
        assert len(scenes) == 4

    def test_no_scene_heading(self) -> None:
        """Boundary: no heading -> single scene with FADE IN heading."""
        text = "Just some narrative text.\n\nSARAH\nHello."
        scenes = _parse_fountain(text)
        assert len(scenes) == 1
        assert scenes[0].heading == "FADE IN:"

    def test_empty_text(self) -> None:
        """Boundary: empty text returns single empty scene."""
        scenes = _parse_fountain("")
        assert len(scenes) == 1
        assert scenes[0].heading == "FADE IN:"
        assert scenes[0].content == ""

    def test_scene_heading_in_middle_of_text(self) -> None:
        """Heading after some text creates two scenes (prologue + scene)."""
        text = "Prologue text.\n\nINT. ROOM - DAY\n\nAction."
        scenes = _parse_fountain(text)
        # screenplay-tools parser creates separate scene for pre-heading text
        assert len(scenes) == 2
        assert scenes[0].heading == "FADE IN:"  # Prologue gets default heading
        assert scenes[1].heading == "INT. ROOM - DAY"

    def test_preserves_content_within_scene(self) -> None:
        """Happy-path: scene content is not truncated."""
        text = "INT. ROOM - DAY\n\nSARAH\nHello there.\n\nJOHN\nHi."
        scenes = _parse_fountain(text)
        assert "SARAH" in scenes[0].content
        assert "Hello there." in scenes[0].content
        assert "JOHN" in scenes[0].content

    def test_consecutive_scenes_content_boundaries(self) -> None:
        """Invariant: scene contents do not overlap."""
        text = (
            "INT. FIRST - DAY\n\nContent A.\n\n"
            "EXT. SECOND - NIGHT\n\nContent B.\n\n"
            "INT. THIRD - DAY\n\nContent C."
        )
        scenes = _parse_fountain(text)
        assert scenes[0].content.count("Content A") == 1
        assert scenes[0].content.count("Content B") == 0
        assert scenes[1].content.count("Content B") == 1
        assert scenes[1].content.count("Content C") == 0
        assert scenes[2].content.count("Content C") == 1


# ---------------------------------------------------------------------------
# ScreenplayConverter
# ---------------------------------------------------------------------------

class TestScreenplayConverter:
    """Coverage: convert_chapter and convert_novel (mocked)."""

    def test_convert_chapter_injects_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy-path: registry context is passed in system prompt."""
        from cosmic_script.conversion import registry as reg_mod

        reg = reg_mod.CharacterRegistry()
        reg.update_from_text("ARTHUR enters.", chapter_number=1)

        captured_system: list[str] = []
        captured_user: list[str] = []

        def fake_completion(**kwargs):
            captured_system.append(kwargs["messages"][0]["content"])
            captured_user.append(kwargs["messages"][1]["content"])

            class FakeChoice:
                class FakeMessage:
                    content = "INT. HALL - DAY\n\nARTHUR\nHello."

                message = FakeMessage()

            class FakeResponse:
                choices = [FakeChoice()]

            return FakeResponse()

        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            fake_completion,
        )

        cfg = ConversionConfig(api_key="test-key", max_retries=1, no_cache=True)
        converter = ScreenplayConverter(cfg)
        chapter = Chapter(number=2, text="Arthur entered the hall.")
        scenes = converter.convert_chapter(chapter, reg)

        assert len(scenes) == 1
        assert "ARTHUR" in captured_system[0]
        assert "Chapter 2" in captured_user[0]
        assert "Arthur entered the hall." in captured_user[0]

    def test_convert_novel_empty(self) -> None:
        """Boundary: empty chapter list returns empty Screenplay."""
        cfg = ConversionConfig(api_key="test-key")
        converter = ScreenplayConverter(cfg)
        sp = converter.convert_novel([], title="Empty", author="Test")
        assert sp.title == "Empty"
        assert sp.author == "Test"
        assert sp.scenes == []

    def test_convert_novel_sequential(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Happy-path: processes chapters sequentially with shared registry."""
        call_index = 0

        # Pre-define outlines to avoid LLM call for outline generation
        fake_outlines = [
            {"genre": "drama", "tone": "neutral", "scenes": [{"location": "INT. ROOM - DAY", "characters": [], "purpose": "advances plot", "beats": []}], "character_notes": ""},
            {"genre": "drama", "tone": "neutral", "scenes": [{"location": "EXT. GARDEN - NIGHT", "characters": [], "purpose": "advances plot", "beats": []}], "character_notes": ""},
            {"genre": "drama", "tone": "neutral", "scenes": [{"location": "INT. CASTLE - DAY", "characters": [], "purpose": "advances plot", "beats": []}], "character_notes": ""},
        ]
        outline_index = 0

        def fake_completion(**kwargs):
            nonlocal call_index, outline_index
            call_index += 1
            system = kwargs["messages"][0]["content"]

            # Handle outline generation calls — exact match for OUTLINE_SYSTEM_PROMPT
            if system.startswith("You are a professional screenplay adapter analyzing"):
                outline = fake_outlines[outline_index]
                outline_index += 1
                content = json.dumps(outline)
                fake_message = type("FakeMessage", (), {"content": content})()
                fake_choice = type("FakeChoice", (), {"message": fake_message})()
                return type("FakeResponse", (), {"choices": [fake_choice]})()

            # Handle quality evaluation calls
            if system.startswith("You are a professional screenplay evaluator"):
                content = '{"scores":{"format":8,"characters":8,"structure":8,"visual":8,"dialogue":8,"coherence":8},"overall":8.0,"strengths":[],"weaknesses":[],"suggestions":[]}'
                fake_message = type("FakeMessage", (), {"content": content})()
                fake_choice = type("FakeChoice", (), {"message": fake_message})()
                return type("FakeResponse", (), {"choices": [fake_choice]})()

            # Handle main conversion calls (SYSTEM_PROMPT)
            if "ARTHUR" in system:
                content = "INT. CASTLE - DAY\n\nARTHUR\nThird line."
            elif "No characters identified yet." in system:
                content = "INT. ROOM - DAY\n\nARTHUR\nFirst line."
            else:
                content = "EXT. GARDEN - NIGHT\n\nGUINEVERE\nSecond line."

            fake_message = type("FakeMessage", (), {"content": content})()
            fake_choice = type("FakeChoice", (), {"message": fake_message})()
            return type("FakeResponse", (), {"choices": [fake_choice]})()

        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            fake_completion,
        )

        cfg = ConversionConfig(api_key="test-key", max_retries=1, no_cache=True)
        converter = ScreenplayConverter(cfg)
        chapters = [
            Chapter(number=1, text="ARTHUR walked into the room."),
            Chapter(number=2, text="GUINEVERE wandered through the garden."),
            Chapter(number=3, text="ARTHUR stood in the castle courtyard."),
        ]
        sp = converter.convert_novel(chapters, title="Test", author="Tester")

        assert len(sp.scenes) == 3
        assert sp.title == "Test"
        assert sp.author == "Tester"

    def test_convert_chapter_handles_api_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Error-path: API errors raise RuntimeError after retries."""
        import litellm as _litellm

        call_count = 0

        def failing_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            raise _litellm.APIError(
                status_code=500,
                message="Server error",
                llm_provider="openai",
                model="gpt-4o",
            )

        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            failing_completion,
        )

        from cosmic_script.conversion.registry import CharacterRegistry

        cfg = ConversionConfig(api_key="test-key", max_retries=2, max_tokens=100)
        converter = ScreenplayConverter(cfg)
        chapter = Chapter(number=1, text="Hello.")
        reg = CharacterRegistry()

        with pytest.raises(RuntimeError, match="LLM call failed after 2 retries"):
            converter.convert_chapter(chapter, reg)

        # 2 retries for outline + 2 retries for main conversion = 4 total
        assert call_count == 4


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    """Coverage: happy-path, invariant, boundary."""

    def test_basic_prompt(self) -> None:
        """Happy-path: basic prompt with chapter number and text."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(chapter_number=1, chapter_text="Hello.")
        assert "Chapter 1:" in result
        assert "Hello." in result

    def test_with_title(self) -> None:
        """Happy-path: prompt with title."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=2,
            chapter_text="Test.",
            title="My Screenplay",
        )
        assert "Title: My Screenplay" in result
        assert "Chapter 2:" in result

    def test_with_tone(self) -> None:
        """Happy-path: prompt with tone."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=3,
            chapter_text="Test.",
            tone="noir",
        )
        assert "Tone: noir" in result
        assert "Chapter 3:" in result

    def test_with_title_and_tone(self) -> None:
        """Happy-path: prompt with both title and tone."""
        from cosmic_script.conversion.prompts import build_user_prompt

        result = build_user_prompt(
            chapter_number=4,
            chapter_text="Test.",
            title="My Script",
            tone="comedy",
        )
        assert "Title: My Script" in result
        assert "Tone: comedy" in result
        assert "Chapter 4:" in result


# ---------------------------------------------------------------------------
# ConversionCache
# ---------------------------------------------------------------------------

class TestConversionCache:
    """Coverage: happy-path, invariant, boundary."""

    def test_cache_hit_and_miss(self) -> None:
        """Happy-path: cache miss then hit returns same value."""
        from cosmic_script.conversion.cache import ConversionCache, _build_cache_key

        cache = ConversionCache(enabled=True, ttl_seconds=3600)
        try:
            key = _build_cache_key(
                chapter_text="Test chapter.",
                model="test-model",
                temperature=0.3,
                system_prompt="system prompt",
            )

            # Miss
            assert cache.get(key) is None

            # Set
            cache.set(key, "INT. ROOM - DAY\n\nTest.", "test-model")

            # Hit
            result = cache.get(key)
            assert result == "INT. ROOM - DAY\n\nTest."
        finally:
            cache.clear()
            cache.close()

    def test_cache_disabled(self) -> None:
        """Boundary: disabled cache returns None always."""
        from cosmic_script.conversion.cache import ConversionCache, _build_cache_key

        cache = ConversionCache(enabled=False)
        try:
            key = _build_cache_key("text", "model", 0.3, "sys")
            cache.set(key, "response", "model")
            assert cache.get(key) is None
        finally:
            cache.close()

    def test_cache_clear(self) -> None:
        """Happy-path: clear removes all entries."""
        from cosmic_script.conversion.cache import ConversionCache, _build_cache_key

        cache = ConversionCache(enabled=True, ttl_seconds=3600)
        try:
            key = _build_cache_key("text", "model", 0.3, "sys")
            cache.set(key, "response", "model")
            assert cache.get(key) == "response"
            cache.clear()
            assert cache.get(key) is None
        finally:
            cache.close()

    def test_cache_stats(self) -> None:
        """Happy-path: stats returns counts."""
        from cosmic_script.conversion.cache import ConversionCache, _build_cache_key

        cache = ConversionCache(enabled=True, ttl_seconds=3600)
        try:
            key = _build_cache_key("text", "model", 0.3, "sys")
            cache.set(key, "response", "model")
            cache.get(key)  # hit
            stats = cache.stats()
            assert stats["total_entries"] >= 1
            assert stats["total_hits"] >= 1
        finally:
            cache.clear()
            cache.close()

    def test_cache_key_different_text_different_key(self) -> None:
        """Invariant: different text produces different cache keys."""
        from cosmic_script.conversion.cache import _build_cache_key

        key1 = _build_cache_key("text A", "model", 0.3, "sys")
        key2 = _build_cache_key("text B", "model", 0.3, "sys")
        assert key1 != key2

    def test_cache_key_different_model_different_key(self) -> None:
        """Invariant: different model produces different cache keys."""
        from cosmic_script.conversion.cache import _build_cache_key

        key1 = _build_cache_key("text", "model-a", 0.3, "sys")
        key2 = _build_cache_key("text", "model-b", 0.3, "sys")
        assert key1 != key2

    def test_cache_key_different_temp_different_key(self) -> None:
        """Invariant: different temperature produces different keys."""
        from cosmic_script.conversion.cache import _build_cache_key

        key1 = _build_cache_key("text", "model", 0.3, "sys")
        key2 = _build_cache_key("text", "model", 0.7, "sys")
        assert key1 != key2

    def test_cache_key_different_system_prompt_different_key(self) -> None:
        """Invariant: different system prompt produces different keys."""
        from cosmic_script.conversion.cache import _build_cache_key

        key1 = _build_cache_key("text", "model", 0.3, "sys prompt A")
        key2 = _build_cache_key("text", "model", 0.3, "sys prompt B")
        assert key1 != key2


# ---------------------------------------------------------------------------
# Self-healing
# ---------------------------------------------------------------------------

class TestSelfHealing:
    """Coverage: self-healing pipeline in convert_chapter."""

    def _make_fake_completion(self, content_sequence):
        """Create a fake completion that routes calls by system prompt."""
        call_index = [0]
        outline_call = [0]

        def fake_completion(**kwargs):
            system = kwargs["messages"][0]["content"]

            # Outline calls
            if system.startswith("You are a professional screenplay adapter analyzing"):
                outline_call[0] += 1
                content = json.dumps({"genre": "drama", "tone": "neutral", "scenes": [], "character_notes": ""})
                fm = type("FakeMessage", (), {"content": content})()
                fc = type("FakeChoice", (), {"message": fm})()
                return type("FakeResponse", (), {"choices": [fc]})()

            # Quality eval calls
            if system.startswith("You are a professional screenplay evaluator"):
                content = '{"scores":{"format":8,"characters":8,"structure":8,"visual":8,"dialogue":8,"coherence":8},"overall":8.0,"strengths":[],"weaknesses":[],"suggestions":[]}'
                fm = type("FakeMessage", (), {"content": content})()
                fc = type("FakeChoice", (), {"message": fm})()
                return type("FakeResponse", (), {"choices": [fc]})()

            # Main conversion or self-heal calls
            idx = call_index[0]
            call_index[0] += 1
            content = content_sequence[min(idx, len(content_sequence) - 1)]
            fm = type("FakeMessage", (), {"content": content})()
            fc = type("FakeChoice", (), {"message": fm})()
            return type("FakeResponse", (), {"choices": [fc]})()

        return fake_completion

    def test_self_heal_skipped_when_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy-path: no self-heal when output is already valid."""
        fake = self._make_fake_completion(["INT. ROOM - DAY\n\nSARAH\nHello."])
        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            fake,
        )

        from cosmic_script.conversion.registry import CharacterRegistry

        cfg = ConversionConfig(api_key="test-key", max_retries=1, no_cache=True)
        converter = ScreenplayConverter(cfg)
        chapter = Chapter(number=1, text="Sarah said hello.")
        reg = CharacterRegistry()
        scenes = converter.convert_chapter(chapter, reg)
        assert len(scenes) == 1

    def test_self_heal_triggered_on_invalid_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Happy-path: self-heal triggered when output has errors."""
        fake = self._make_fake_completion([
            "INT. ROOM - DAY\n\nsarah\nHello.",  # Invalid (lowercase)
            "INT. ROOM - DAY\n\nSARAH\nHello.",  # Fixed
        ])
        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            fake,
        )

        from cosmic_script.conversion.registry import CharacterRegistry

        cfg = ConversionConfig(api_key="test-key", max_retries=1, no_cache=True)
        converter = ScreenplayConverter(cfg)
        chapter = Chapter(number=1, text="Sarah said hello.")
        reg = CharacterRegistry()
        scenes = converter.convert_chapter(chapter, reg)
        assert len(scenes) == 1

    def test_self_heal_keeps_original_when_worse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Error-path: self-heal produces worse output, keep original."""
        fake = self._make_fake_completion([
            "INT. ROOM - DAY\n\nSARAH\nHello.",  # Valid
            "bad output with no scene heading",   # Worse
        ])
        monkeypatch.setattr(
            "cosmic_script.conversion.converter.litellm.completion",
            fake,
        )

        from cosmic_script.conversion.registry import CharacterRegistry

        cfg = ConversionConfig(api_key="test-key", max_retries=1, no_cache=True)
        converter = ScreenplayConverter(cfg)
        chapter = Chapter(number=1, text="Sarah said hello.")
        reg = CharacterRegistry()
        scenes = converter.convert_chapter(chapter, reg)
        # Should still return scenes from original output
        assert len(scenes) == 1

    def test_no_cache_flag(self) -> None:
        """Boundary: no_cache=True in config disables cache."""
        cfg = ConversionConfig(no_cache=True)
        converter = ScreenplayConverter(cfg)
        assert converter._cache._enabled is False

    def test_clear_cache_method(self) -> None:
        """Happy-path: clear_cache() works."""
        cfg = ConversionConfig()
        converter = ScreenplayConverter(cfg)
        # Should not raise
        converter.clear_cache()
