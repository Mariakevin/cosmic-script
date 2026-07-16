"""Tests for prompts module."""

from cosmic_script.conversion.prompts import SYSTEM_PROMPT, USER_PROMPT


class TestSystemPrompt:
    """Coverage: happy-path, invariant, boundary, error-path, input-variation."""

    def test_system_prompt_contains_required_sections(self) -> None:
        """Invariant: prompt must contain all expected formatting rules."""
        assert "Scene Heading" in SYSTEM_PROMPT
        assert "Character" in SYSTEM_PROMPT
        assert "Dialogue" in SYSTEM_PROMPT
        assert "Action" in SYSTEM_PROMPT
        assert "Parenthetical" in SYSTEM_PROMPT
        assert "Transition" in SYSTEM_PROMPT

    def test_system_prompt_has_character_registry_placeholder(self) -> None:
        """Invariant: placeholder must be present for injection."""
        assert "{character_registry}" in SYSTEM_PROMPT

    def test_system_prompt_mentions_fountain_format(self) -> None:
        """Invariant: must reference Fountain output format."""
        assert "Fountain" in SYSTEM_PROMPT

    def test_system_prompt_requires_no_explanations(self) -> None:
        """Invariant: must instruct LLM to output only Fountain text."""
        assert "no explanations" in SYSTEM_PROMPT

    def test_system_prompt_accepts_character_registry_injection(self) -> None:
        """Happy-path: inject registry and verify output is well-formed."""
        registry_text = "  - SARAH [first appears: Chapter 1]\n  - JOHN [first appears: Chapter 1]"
        prompt = SYSTEM_PROMPT.format(character_registry=registry_text)
        assert registry_text in prompt
        assert "{character_registry}" not in prompt


class TestUserPrompt:
    """Coverage: happy-path, invariant, boundary, input-variation."""

    def test_user_prompt_contains_placeholders(self) -> None:
        """Invariant: must have both chapter_number and chapter_text."""
        assert "{chapter_number}" in USER_PROMPT
        assert "{chapter_text}" in USER_PROMPT

    def test_user_prompt_formatting(self) -> None:
        """Happy-path: render with sample values."""
        result = USER_PROMPT.format(chapter_number=5, chapter_text="It was a dark night.")
        assert "Chapter 5" in result
        assert "It was a dark night." in result

    def test_user_prompt_with_empty_text(self) -> None:
        """Boundary: empty chapter text should not crash."""
        result = USER_PROMPT.format(chapter_number=1, chapter_text="")
        assert "Chapter 1" in result
        assert result.strip().endswith(":")

    def test_user_prompt_chapter_number_zero(self) -> None:
        """Boundary: chapter number 0 (edge of valid range)."""
        result = USER_PROMPT.format(chapter_number=0, chapter_text="Prologue.")
        assert "Chapter 0" in result

    def test_user_prompt_with_multiline_text(self) -> None:
        """Input-variation: multiline chapter text."""
        text = "Line one.\nLine two.\nLine three."
        result = USER_PROMPT.format(chapter_number=3, chapter_text=text)
        assert text in result
