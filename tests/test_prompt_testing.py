"""Tests for prompt A/B testing framework."""

from __future__ import annotations

import pytest

from cosmic_script.conversion.prompt_testing import (
    PromptVariant,
    VariantResult,
    ABTestResult,
    get_default_variants,
    run_variant,
    run_ab_test,
)


class TestPromptVariant:
    """Test PromptVariant dataclass."""

    def test_prompt_variant_creation(self) -> None:
        """Happy-path: create a valid PromptVariant."""
        variant = PromptVariant(
            id="v1",
            name="Default",
            system_prompt="You are a screenplay adapter.",
            user_template="Chapter {chapter_number}: {chapter_text}",
        )
        assert variant.id == "v1"
        assert variant.name == "Default"
        assert "screenplay" in variant.system_prompt

    def test_prompt_variant_is_dataclass(self) -> None:
        """Invariant: PromptVariant must be a dataclass."""
        from dataclasses import asdict

        variant = PromptVariant(
            id="v1",
            name="Test",
            system_prompt="sys",
            user_template="user",
        )
        data = asdict(variant)
        assert "id" in data
        assert "name" in data
        assert "system_prompt" in data
        assert "user_template" in data

    def test_prompt_variant_equality(self) -> None:
        """Invariant: two identical variants are equal."""
        v1 = PromptVariant(id="a", name="A", system_prompt="s", user_template="u")
        v2 = PromptVariant(id="a", name="A", system_prompt="s", user_template="u")
        assert v1 == v2

    def test_prompt_variant_inequality(self) -> None:
        """Invariant: different variants are not equal."""
        v1 = PromptVariant(id="a", name="A", system_prompt="s", user_template="u")
        v2 = PromptVariant(id="b", name="B", system_prompt="s", user_template="u")
        assert v1 != v2

    def test_prompt_variant_empty_fields(self) -> None:
        """Boundary: variant with empty string fields."""
        variant = PromptVariant(id="", name="", system_prompt="", user_template="")
        assert variant.id == ""
        assert variant.system_prompt == ""

    def test_prompt_variant_long_text(self) -> None:
        """Boundary: variant with very long prompt text."""
        long_prompt = "x" * 10000
        variant = PromptVariant(id="v1", name="Long", system_prompt=long_prompt, user_template="u")
        assert len(variant.system_prompt) == 10000


class TestGetDefaultVariants:
    """Test get_default_variants function."""

    def test_get_default_variants_returns_list(self) -> None:
        """Happy-path: default variants are returned."""
        variants = get_default_variants()
        assert isinstance(variants, list)

    def test_get_default_variants_has_at_least_three(self) -> None:
        """Invariant: must return 3+ variants."""
        variants = get_default_variants()
        assert len(variants) >= 3

    def test_default_variants_are_prompt_variants(self) -> None:
        """Invariant: all default variants must be PromptVariant instances."""
        variants = get_default_variants()
        for v in variants:
            assert isinstance(v, PromptVariant)

    def test_default_variants_have_unique_ids(self) -> None:
        """Invariant: each variant must have a unique id."""
        variants = get_default_variants()
        ids = [v.id for v in variants]
        assert len(ids) == len(set(ids))

    def test_default_variants_have_nonempty_prompts(self) -> None:
        """Invariant: system_prompt and user_template must not be empty."""
        variants = get_default_variants()
        for v in variants:
            assert v.system_prompt, f"Variant {v.id} has empty system_prompt"
            assert v.user_template, f"Variant {v.id} has empty user_template"


class TestRunVariant:
    """Test run_variant function with demo mode."""

    def test_run_variant_returns_variant_result(self) -> None:
        """Happy-path: run_variant with model='demo' returns valid result."""
        variant = PromptVariant(
            id="test_v1",
            name="Test Variant",
            system_prompt="You are a screenplay adapter.",
            user_template="Chapter {chapter_number}:\n\n{chapter_text}",
        )
        result = run_variant(
            variant=variant,
            chapter_text="Sarah walked into the room. She looked around.",
            chapter_number=1,
            model="demo",
        )
        assert isinstance(result, VariantResult)
        assert result.variant_id == "test_v1"
        assert result.input_name == "chapter_1"
        assert result.screenplay is not None
        assert result.metrics is not None
        assert result.elapsed_seconds >= 0

    def test_run_variant_screenplay_has_scenes(self) -> None:
        """Invariant: demo mode produces a screenplay with scenes."""
        variant = PromptVariant(
            id="test_v1",
            name="Test",
            system_prompt="sys",
            user_template="Chapter {chapter_number}:\n\n{chapter_text}",
        )
        result = run_variant(
            variant=variant,
            chapter_text="Test content.",
            chapter_number=1,
            model="demo",
        )
        assert len(result.screenplay.scenes) > 0

    def test_run_variant_metrics_are_numeric(self) -> None:
        """Invariant: metrics scores must be numeric."""
        variant = PromptVariant(
            id="test_v1",
            name="Test",
            system_prompt="sys",
            user_template="Chapter {chapter_number}:\n\n{chapter_text}",
        )
        result = run_variant(
            variant=variant,
            chapter_text="Test.",
            chapter_number=1,
            model="demo",
        )
        assert isinstance(result.metrics.overall, (int, float))
        assert 0 <= result.metrics.overall <= 100

    def test_run_variant_with_title(self) -> None:
        """Happy-path: run_variant with title parameter."""
        variant = PromptVariant(
            id="test_v1",
            name="Test",
            system_prompt="sys",
            user_template="Chapter {chapter_number}:\n\n{chapter_text}",
        )
        result = run_variant(
            variant=variant,
            chapter_text="Content.",
            chapter_number=1,
            model="demo",
            title="My Screenplay",
        )
        assert result is not None


class TestRunABTest:
    """Test run_ab_test function with demo mode."""

    def test_run_ab_test_returns_result(self) -> None:
        """Happy-path: run_ab_test with model='demo' returns valid result."""
        variants = get_default_variants()[:2]
        inputs = {"scene_a": "Sarah entered the room.", "scene_b": "John opened the door."}
        result = run_ab_test(variants=variants, inputs=inputs, model="demo")
        assert isinstance(result, ABTestResult)
        assert len(result.results) > 0

    def test_run_ab_test_rankings_are_valid(self) -> None:
        """Invariant: rankings must return sorted list of (variant_id, score)."""
        variants = get_default_variants()[:2]
        inputs = {"test_input": "Some text."}
        result = run_ab_test(variants=variants, inputs=inputs, model="demo")
        rankings = result.rankings()
        assert isinstance(rankings, list)
        assert len(rankings) > 0
        for vid, score in rankings:
            assert isinstance(vid, str)
            assert isinstance(score, (int, float))
        # Verify sorted descending
        scores = [s for _, s in rankings]
        assert scores == sorted(scores, reverse=True)

    def test_run_ab_test_summary_is_string(self) -> None:
        """Invariant: summary must return a string."""
        variants = get_default_variants()[:2]
        inputs = {"test": "Text."}
        result = run_ab_test(variants=variants, inputs=inputs, model="demo")
        summary = result.summary()
        assert isinstance(summary, str)
        assert "A/B Test Results" in summary

    def test_run_ab_test_multiple_inputs(self) -> None:
        """Input-variation: multiple inputs produce multiple results."""
        variants = get_default_variants()[:1]
        inputs = {
            "input_1": "First chapter text.",
            "input_2": "Second chapter text.",
            "input_3": "Third chapter text.",
        }
        result = run_ab_test(variants=variants, inputs=inputs, model="demo")
        assert len(result.results) == 3

    def test_run_ab_test_empty_inputs(self) -> None:
        """Boundary: empty inputs produces empty results."""
        variants = get_default_variants()[:1]
        result = run_ab_test(variants=variants, inputs={}, model="demo")
        assert len(result.results) == 0
