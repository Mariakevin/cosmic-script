"""Prompt A/B Testing Framework for screenplay conversion quality optimization."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from cosmic_script.analysis.quality_metrics import QualityMetrics, compute_metrics
from cosmic_script.conversion.converter import ConversionConfig, ScreenplayConverter
from cosmic_script.conversion.prompts import SYSTEM_PROMPT, build_user_prompt
from cosmic_script.models import Screenplay


@dataclass
class PromptVariant:
    """A prompt configuration for A/B testing."""

    id: str
    name: str
    system_prompt: str
    user_template: str  # Must contain {chapter_number} and {chapter_text}


@dataclass
class VariantResult:
    """Result of testing a single variant on a single input."""

    variant_id: str
    input_name: str
    screenplay: Screenplay
    metrics: QualityMetrics
    elapsed_seconds: float


@dataclass
class ABTestResult:
    """Aggregate results of an A/B test."""

    results: list[VariantResult] = field(default_factory=list)

    def rankings(self) -> list[tuple[str, float]]:
        """Rank variants by average overall quality score."""
        from collections import defaultdict

        scores: dict[str, list[float]] = defaultdict(list)
        for r in self.results:
            scores[r.variant_id].append(r.metrics.overall)
        avg = [(vid, sum(s) / len(s)) for vid, s in scores.items()]
        return sorted(avg, key=lambda x: x[1], reverse=True)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = ["A/B Test Results:", ""]
        for rank, (vid, score) in enumerate(self.rankings(), 1):
            lines.append(f"  #{rank} {vid}: {score:.1f}/100")
        return "\n".join(lines)


def get_default_variants() -> list[PromptVariant]:
    """Return the default set of prompt variants for testing."""
    return [
        PromptVariant(
            id="v1_current",
            name="Current (Full Rules)",
            system_prompt=SYSTEM_PROMPT,
            user_template=build_user_prompt(0, "{chapter_text}").replace(
                "Chapter 0:", "Chapter {chapter_number}:"
            ),
        ),
        PromptVariant(
            id="v2_concise",
            name="Concise Rules",
            system_prompt=(
                "You are a professional screenplay adapter. Convert the chapter below into "
                "valid Fountain 1.1 format.\n\n"
                "RULES:\n"
                "- Scene headings: INT./EXT. LOCATION - TIME\n"
                "- Character names: ALL CAPS before dialogue\n"
                "- Dialogue goes under character names\n"
                "- Action lines describe what we see\n"
                "- Use transitions (CUT TO:, FADE OUT.) sparingly\n"
                "- Output ONLY Fountain text, no commentary."
            ),
            user_template="Convert Chapter {chapter_number} to Fountain:\n\n{chapter_text}",
        ),
        PromptVariant(
            id="v3_structured",
            name="Structured Output",
            system_prompt=(
                "You are a professional screenplay adapter. Convert novel chapters to "
                "Fountain 1.1 format.\n\n"
                "STEP 1: Identify the setting (INT/EXT, location, time of day)\n"
                "STEP 2: Break into scenes with clear headings\n"
                "STEP 3: Convert dialogue to character cues + dialogue blocks\n"
                "STEP 4: Convert description to action lines (present tense, concise)\n"
                "STEP 5: Add transitions where natural (CUT TO:, SMASH CUT:)\n\n"
                "OUTPUT FORMAT: Valid Fountain 1.1 only. No explanations."
            ),
            user_template="Chapter {chapter_number}:\n\n{chapter_text}",
        ),
    ]


def run_variant(
    variant: PromptVariant,
    chapter_text: str,
    chapter_number: int = 1,
    model: str = "demo",
    title: str = "",
) -> VariantResult:
    """Run a single variant on a single chapter input."""
    from cosmic_script.conversion.registry import CharacterRegistry
    from cosmic_script.models import Chapter

    system_msg = variant.system_prompt
    user_msg = variant.user_template.format(
        chapter_number=chapter_number, chapter_text=chapter_text
    )

    config = ConversionConfig(model=model)
    converter = ScreenplayConverter(config)

    chapter = Chapter(number=chapter_number, text=chapter_text)
    registry = CharacterRegistry()

    start = time.time()
    scenes = converter.convert_chapter(chapter, registry)
    screenplay = Screenplay(title=title, scenes=scenes)
    elapsed = time.time() - start

    metrics = compute_metrics(screenplay)

    return VariantResult(
        variant_id=variant.id,
        input_name=f"chapter_{chapter_number}",
        screenplay=screenplay,
        metrics=metrics,
        elapsed_seconds=elapsed,
    )


def run_ab_test(
    variants: list[PromptVariant],
    inputs: dict[str, str],
    model: str = "demo",
) -> ABTestResult:
    """Run an A/B test comparing variants on multiple inputs.

    Args:
        variants: List of PromptVariant to compare
        inputs: Dict of input_name -> chapter_text
        model: Model to use (default "demo" for testing)

    Returns:
        ABTestResult with all results and rankings
    """
    result = ABTestResult()

    for input_name, chapter_text in inputs.items():
        for variant in variants:
            vr = run_variant(
                variant=variant,
                chapter_text=chapter_text,
                chapter_number=1,
                model=model,
                title=input_name,
            )
            vr.input_name = input_name
            result.results.append(vr)

    return result
