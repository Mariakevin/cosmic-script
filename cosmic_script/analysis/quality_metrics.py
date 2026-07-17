"""Quality metrics for screenplay regression testing.

Provides deterministic scoring functions that evaluate Fountain format
compliance, structural quality, and dialogue balance. All functions
accept a Screenplay object and return float scores suitable for
threshold-based regression tests.

No LLM calls — pure calculation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cosmic_script.models import Screenplay, ScreenplayElement
from cosmic_script.export.fountain import generate_fountain

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_SCENE_HEADING_RE = re.compile(r"^(?:INT\.|EXT\.|INT/EXT\.|I/E\.)\s+.+")
_CHARACTER_CUE_RE = re.compile(r"^[A-Z][A-Z\s]{1,25}$")
_TRANSITION_RE = re.compile(r"^[A-Z\s]+TO:$|FADE\s+(?:IN|OUT)")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class QualityMetrics:
    """Aggregate quality scores for a screenplay.

    Attributes:
        format_score: Fountain format compliance (0.0 - 100.0).
        structure_score: Scene structure and pacing (0.0 - 100.0).
        dialogue_score: Dialogue-to-action balance (0.0 - 100.0).
        overall: Weighted combination of above (0.0 - 100.0).
        element_counts: Breakdown of element types found.
        warnings: Quality warnings.
    """

    format_score: float = 0.0
    structure_score: float = 0.0
    dialogue_score: float = 0.0
    overall: float = 0.0
    element_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: count elements by type
# ---------------------------------------------------------------------------


def _count_elements(screenplay: Screenplay) -> dict[str, int]:
    """Count occurrences of each element type.

    Works with both element-based and scene-based screenplays.
    """
    counts: dict[str, int] = {}
    if screenplay.elements:
        for el in screenplay.elements:
            counts[el.element_type] = counts.get(el.element_type, 0) + 1
    elif screenplay.scenes:
        # Parse scene content to derive element types
        for scene in screenplay.scenes:
            _count_from_text(scene.heading, scene.content, counts)
    return counts


def _count_from_text(heading: str, content: str, counts: dict[str, int]) -> None:
    """Derive element counts from raw scene heading + content."""
    counts["scene_heading"] = counts.get("scene_heading", 0) + 1

    in_dialogue = False
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            in_dialogue = False
            continue

        if stripped.isupper() and len(stripped) <= 30:
            counts["character"] = counts.get("character", 0) + 1
            in_dialogue = True
            continue

        if stripped.startswith("(") and stripped.endswith(")"):
            counts["parenthetical"] = counts.get("parenthetical", 0) + 1
            continue

        if in_dialogue:
            counts["dialogue"] = counts.get("dialogue", 0) + 1
            in_dialogue = False
        else:
            counts["action"] = counts.get("action", 0) + 1


# ---------------------------------------------------------------------------
# format_score
# ---------------------------------------------------------------------------


def format_score(screenplay: Screenplay) -> float:
    """Check Fountain format compliance.

    Validates:
    - Scene headings follow INT./EXT. convention
    - Character cues are uppercase and short
    - Dialogue appears after character cues
    - Transitions end with TO:

    Args:
        screenplay: The screenplay to evaluate.

    Returns:
        Score from 0.0 to 100.0 (100 = perfect compliance).
    """
    if not screenplay.elements and not screenplay.scenes:
        return 100.0  # Empty is trivially valid

    fountain_text = generate_fountain(screenplay)
    if not fountain_text.strip():
        return 100.0

    lines = [l for l in fountain_text.split("\n") if l.strip()]
    if not lines:
        return 100.0

    score = 100.0
    issues = 0

    prev_type: str | None = None
    in_dialogue = False

    for line in lines:
        stripped = line.strip()

        # Scene heading
        if _SCENE_HEADING_RE.match(stripped):
            in_dialogue = False
            prev_type = "scene_heading"
            continue

        # Character cue
        if _CHARACTER_CUE_RE.match(stripped):
            in_dialogue = True
            prev_type = "character"
            continue

        # Dialogue (indented or after character)
        if in_dialogue and (line.startswith("\t") or line.startswith("    ")):
            prev_type = "dialogue"
            continue
        if in_dialogue and not line.startswith("\t") and not line.startswith("    "):
            # Dialogue not indented
            issues += 1
            in_dialogue = False
            prev_type = "dialogue"
            continue

        # Transition
        if stripped.upper().endswith("TO:") or stripped == "FADE IN:":
            in_dialogue = False
            prev_type = "transition"
            continue

        # Parenthetical
        if stripped.startswith("(") and stripped.endswith(")"):
            prev_type = "parenthetical"
            continue

        # Centered
        if stripped.startswith(">") and stripped.endswith("<"):
            prev_type = "centered"
            continue

        # Section
        if stripped.startswith("# "):
            prev_type = "section"
            continue

        # Synopsis
        if stripped.startswith("= "):
            prev_type = "synopsis"
            continue

        # Lyric
        if stripped.startswith("~"):
            prev_type = "lyric"
            continue

        # Page break
        if stripped == "===":
            prev_type = "page_break"
            continue

        in_dialogue = False

    # Penalize based on issues found
    if issues > 0:
        score -= min(30.0, issues * 5.0)

    # Check element counts for format compliance
    counts = _count_elements(screenplay)

    # Must have at least one scene heading
    if counts.get("scene_heading", 0) == 0:
        score -= 20.0

    # If there are dialogue lines, there should be character cues
    dialogue_count = counts.get("dialogue", 0)
    character_count = counts.get("character", 0)
    if dialogue_count > 0 and character_count == 0:
        score -= 15.0

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# structure_score
# ---------------------------------------------------------------------------


def structure_score(screenplay: Screenplay) -> float:
    """Check scene structure and pacing.

    Validates:
    - Scene count is reasonable (2-20 scenes)
    - Scene lengths are balanced (no extremely short/long scenes)
    - Scene headings use INT./EXT. convention

    Args:
        screenplay: The screenplay to evaluate.

    Returns:
        Score from 0.0 to 100.0 (100 = perfect structure).
    """
    if not screenplay.elements and not screenplay.scenes:
        return 100.0

    counts = _count_elements(screenplay)
    scene_count = counts.get("scene_heading", 0)

    if scene_count == 0:
        return 30.0  # No scenes is poor structure

    score = 100.0

    # Scene count scoring
    if scene_count < 2:
        score -= 15.0  # Too few scenes
    elif scene_count > 20:
        score -= 10.0  # Too many scenes

    # Check scene heading quality
    if screenplay.scenes:
        for scene in screenplay.scenes:
            if not _SCENE_HEADING_RE.match(scene.heading):
                score -= 5.0

    # Check scene length balance using elements
    if screenplay.elements:
        scene_lengths = _get_scene_lengths(screenplay.elements)
        if scene_lengths:
            avg_len = sum(scene_lengths) / len(scene_lengths)
            for length in scene_lengths:
                if length < 3:
                    score -= 3.0  # Very short scene
                elif length > 30:
                    score -= 5.0  # Very long scene

            # Bonus for balanced lengths
            if 3 <= avg_len <= 20:
                score += 5.0

    return max(0.0, min(100.0, score))


def _get_scene_lengths(elements: list[ScreenplayElement]) -> list[int]:
    """Get the number of elements per scene."""
    lengths: list[int] = []
    current_count = 0
    for el in elements:
        if el.element_type == "scene_heading":
            if current_count > 0:
                lengths.append(current_count)
            current_count = 1
        else:
            current_count += 1
    if current_count > 0:
        lengths.append(current_count)
    return lengths


# ---------------------------------------------------------------------------
# dialogue_score
# ---------------------------------------------------------------------------


def dialogue_score(screenplay: Screenplay) -> float:
    """Check dialogue-to-action balance.

    Validates:
    - Dialogue-to-action ratio is in healthy range (30-60%)
    - Multiple characters speak (not monologue)
    - Dialogue is distributed across characters

    Args:
        screenplay: The screenplay to evaluate.

    Returns:
        Score from 0.0 to 100.0 (100 = perfect balance).
    """
    if not screenplay.elements and not screenplay.scenes:
        return 100.0

    counts = _count_elements(screenplay)

    dialogue = counts.get("dialogue", 0) + counts.get("character", 0)
    action = counts.get("action", 0)
    total = dialogue + action

    if total == 0:
        return 50.0  # No dialogue or action

    score = 100.0

    # Dialogue ratio scoring
    ratio = dialogue / total
    if ratio < 0.2:
        score -= 25.0  # Too little dialogue
    elif ratio > 0.7:
        score -= 20.0  # Too much dialogue
    elif 0.3 <= ratio <= 0.6:
        score += 5.0  # Ideal range

    # Character count scoring
    character_count = counts.get("character", 0)
    if character_count == 0:
        score -= 20.0  # No speaking characters
    elif character_count == 1:
        score -= 10.0  # Monologue

    # Dialogue distribution
    if screenplay.elements:
        char_dialogue = _get_dialogue_per_character(screenplay.elements)
        if char_dialogue:
            values = list(char_dialogue.values())
            if len(values) > 1:
                avg = sum(values) / len(values)
                # Check if dialogue is reasonably distributed
                max_deviation = max(abs(v - avg) for v in values) / avg if avg > 0 else 0
                if max_deviation > 2.0:
                    score -= 10.0  # Very uneven distribution

    return max(0.0, min(100.0, score))


def _get_dialogue_per_character(
    elements: list[ScreenplayElement],
) -> dict[str, int]:
    """Count dialogue lines per character."""
    char_dialogue: dict[str, int] = {}
    current_char: str | None = None
    for el in elements:
        if el.element_type == "character":
            current_char = el.text
        elif el.element_type == "dialogue" and current_char:
            char_dialogue[current_char] = char_dialogue.get(current_char, 0) + 1
        elif el.element_type in ("action", "scene_heading"):
            current_char = None
    return char_dialogue


# ---------------------------------------------------------------------------
# overall_quality
# ---------------------------------------------------------------------------


def overall_quality(screenplay: Screenplay) -> float:
    """Compute weighted overall quality score.

    Weights:
    - format_score: 40%
    - structure_score: 30%
    - dialogue_score: 30%

    Args:
        screenplay: The screenplay to evaluate.

    Returns:
        Score from 0.0 to 100.0.
    """
    fmt = format_score(screenplay)
    struct = structure_score(screenplay)
    dial = dialogue_score(screenplay)

    return round(fmt * 0.4 + struct * 0.3 + dial * 0.3, 2)


# ---------------------------------------------------------------------------
# Full metrics report
# ---------------------------------------------------------------------------


def compute_metrics(screenplay: Screenplay) -> QualityMetrics:
    """Compute all quality metrics for a screenplay.

    Args:
        screenplay: The screenplay to evaluate.

    Returns:
        QualityMetrics with all scores, element counts, and warnings.
    """
    fmt = format_score(screenplay)
    struct = structure_score(screenplay)
    dial = dialogue_score(screenplay)
    overall = round(fmt * 0.4 + struct * 0.3 + dial * 0.3, 2)
    counts = _count_elements(screenplay)
    warnings: list[str] = []

    if counts.get("scene_heading", 0) == 0:
        warnings.append("No scene headings found")
    if counts.get("character", 0) == 0 and counts.get("dialogue", 0) > 0:
        warnings.append("Dialogue without character cues")
    if counts.get("dialogue", 0) == 0 and counts.get("character", 0) > 0:
        warnings.append("Character cues without dialogue")

    return QualityMetrics(
        format_score=fmt,
        structure_score=struct,
        dialogue_score=dial,
        overall=overall,
        element_counts=counts,
        warnings=warnings,
    )
