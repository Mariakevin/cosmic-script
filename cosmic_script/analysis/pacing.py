"""Scene pacing analysis for screenplays.

Analyzes scene-by-scene pacing metrics to identify structural issues and
generate actionable recommendations for improving script rhythm.

Pure calculation — no LLM calls required.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from cosmic_script.models import Screenplay, Scene, ScreenplayElement

# ---------------------------------------------------------------------------
# Pacing thresholds
# ---------------------------------------------------------------------------

FAST_LINE_LIMIT = 10  # <= 10 lines → fast
SLOW_LINE_LIMIT = 25  # >= 26 lines → slow
FAST_DIALOGUE_RATIO = 0.6  # > 60% dialogue → fast
SLOW_DIALOGUE_RATIO = 0.3  # < 30% dialogue (+ long) → slow

TOO_LONG_LIMIT = 30  # > 30 lines → "too long" issue
TOO_SHORT_LIMIT = 3  # < 3 lines → "too short" issue
ALL_DIALOGUE_RATIO = 0.9  # > 90% dialogue → "all dialogue"

# Character cue pattern: standalone ALL-CAPS lines (typically 2-20 chars)
_CHARACTER_CUE_RE = __import__("re").compile(r"^[A-Z][A-Z\s]{0,19}$")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScenePacing:
    """Pacing metrics for a single scene.

    Attributes:
        scene_number: 1-indexed scene number.
        heading: Scene heading text (e.g. ``"INT. HOUSE - DAY"``).
        line_count: Total estimated line count for the scene.
        dialogue_lines: Number of dialogue lines in the scene.
        action_lines: Number of action/description lines.
        dialogue_ratio: Proportion of lines that are dialogue (0.0 to 1.0).
        pacing: ``"fast"``, ``"medium"``, or ``"slow"``.
        issues: List of detected pacing issues (e.g. ``["too long"]``).
    """

    scene_number: int
    heading: str
    line_count: int
    dialogue_lines: int
    action_lines: int
    dialogue_ratio: float
    pacing: str
    issues: list[str] = field(default_factory=list)


@dataclass
class PacingReport:
    """Complete pacing analysis for a screenplay.

    Attributes:
        scenes: Per-scene pacing metrics.
        overall_pacing: Aggregate pacing classification.
        avg_scene_length: Mean line count across all scenes.
        total_issues: Cumulative issue count across all scenes.
        recommendations: Actionable suggestions for improving pacing.
    """

    scenes: list[ScenePacing] = field(default_factory=list)
    overall_pacing: str = "medium"
    avg_scene_length: float = 0.0
    total_issues: int = 0
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _classify_pacing(line_count: int, dialogue_ratio: float) -> str:
    """Classify scene pacing as ``"fast"``, ``"medium"``, or ``"slow"``.

    Args:
        line_count: Total lines in the scene.
        dialogue_ratio: Proportion of lines that are dialogue (0.0 to 1.0).

    Returns:
        Pacing classification string.
    """
    if line_count <= FAST_LINE_LIMIT and dialogue_ratio >= FAST_DIALOGUE_RATIO:
        return "fast"
    if line_count >= SLOW_LINE_LIMIT and dialogue_ratio <= SLOW_DIALOGUE_RATIO:
        return "slow"
    if line_count <= FAST_LINE_LIMIT:
        return "fast"
    if line_count >= SLOW_LINE_LIMIT:
        return "slow"
    return "medium"


def _detect_issues(
    line_count: int,
    dialogue_lines: int,
    dialogue_ratio: float,
) -> list[str]:
    """Detect pacing issues for a single scene.

    Args:
        line_count: Total lines in the scene.
        dialogue_lines: Number of dialogue lines.
        dialogue_ratio: Proportion of lines that are dialogue.

    Returns:
        List of issue strings (empty if no issues).
    """
    issues: list[str] = []

    if line_count > TOO_LONG_LIMIT:
        issues.append("too long")
    if line_count < TOO_SHORT_LIMIT:
        issues.append("too short")
    if dialogue_lines == 0 and line_count >= 5:
        issues.append("no dialogue")
    if dialogue_ratio >= ALL_DIALOGUE_RATIO and line_count >= 5:
        issues.append("all dialogue")

    return issues


def _generate_recommendations(issues: list[str]) -> list[str]:
    """Generate actionable recommendations from a list of issues.

    Args:
        issues: List of issue strings from one or more scenes.

    Returns:
        Deduplicated list of recommendation strings.
    """
    recs: list[str] = []

    if "too long" in issues:
        recs.append("Consider splitting long scenes")
    if "no dialogue" in issues:
        recs.append("Add dialogue to break up action")
    if "all dialogue" in issues:
        recs.append("Add action to break up dialogue")
    if "too short" in issues:
        recs.append("Expand very short scenes")

    return recs


def _classify_overall_pacing(scene_pacings: list[ScenePacing]) -> str:
    """Derive the overall pacing from scene-level classifications.

    Uses majority voting. Ties are broken: fast > slow > medium.

    Args:
        scene_pacings: Per-scene pacing metrics.

    Returns:
        Overall pacing string.
    """
    if not scene_pacings:
        return "medium"

    counts: Counter = Counter(s.pacing for s in scene_pacings)

    # Majority rule with tiebreaker
    fast = counts.get("fast", 0)
    medium = counts.get("medium", 0)
    slow = counts.get("slow", 0)

    if fast >= medium and fast >= slow:
        return "fast"
    if slow >= medium and slow >= fast:
        return "slow"
    return "medium"


# ---------------------------------------------------------------------------
# Scene parsing
# ---------------------------------------------------------------------------


def _parse_scene_lines(content: str) -> tuple[int, int, int]:
    """Parse a scene's Fountain content and count line types.

    Args:
        content: Fountain-formatted scene content.

    Returns:
        Tuple of (total_lines, dialogue_lines, action_lines).
        Parentheticals, character cues, and blank lines are excluded from
        dialogue and action counts but contribute to total_lines.
    """
    lines = content.split("\n")
    total = 0
    dialogue = 0
    action = 0
    in_dialogue = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            in_dialogue = False
            continue

        total += 1

        # Check for character cue (ALL-CAPS, short)
        if stripped.isupper() and len(stripped.split()[0]) <= 20:
            in_dialogue = True
            # Don't count character cues as dialogue or action
            continue

        # Check for parenthetical
        if stripped.startswith("(") and stripped.endswith(")"):
            in_dialogue = False  # parentheticals reset the context
            continue

        if in_dialogue:
            dialogue += 1
        else:
            action += 1

    return total, dialogue, action


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_pacing(screenplay: Screenplay) -> PacingReport:
    """Analyze scene pacing and generate a structured report.

    Processes both element-based and scene-based screenplays.  Scenes are
    reconstructed from elements when necessary.

    Args:
        screenplay: The screenplay data model to analyse.

    Returns:
        A :class:`PacingReport` with per-scene metrics, overall pacing,
        and recommendations.

    Example:
        >>> from cosmic_script.models import Screenplay, Scene
        >>> sp = Screenplay(scenes=[
        ...     Scene(heading="INT. ROOM - DAY",
        ...           content="JOHN\\nHello.\\n\\nSARAH\\nHi."),
        ... ])
        >>> report = analyze_pacing(sp)
        >>> len(report.scenes)
        1
        >>> report.scenes[0].pacing
        'fast'
    """
    has_content = bool(screenplay.elements or screenplay.scenes)
    if not has_content:
        return PacingReport()

    # Build scene list from elements or scenes
    scenes_to_analyze: list[tuple[str, str]] = []

    if screenplay.elements:
        # Group elements by scene_heading
        current_heading: str | None = None
        current_lines: list[str] = []
        for elem in screenplay.elements:
            if elem.element_type == "scene_heading":
                if current_heading is not None:
                    scenes_to_analyze.append(
                        (current_heading, "\n".join(current_lines))
                    )
                current_heading = elem.text
                current_lines = []
            elif current_heading is not None:
                if elem.element_type == "character":
                    current_lines.append(elem.text)
                elif elem.element_type == "dialogue":
                    current_lines.append(elem.text)
                elif elem.element_type == "parenthetical":
                    current_lines.append(f"({elem.text})")
                elif elem.element_type == "action":
                    current_lines.append(elem.text)
                elif elem.element_type == "transition":
                    current_lines.append(elem.text.upper())

        if current_heading is not None:
            scenes_to_analyze.append(
                (current_heading, "\n".join(current_lines))
            )

    elif screenplay.scenes:
        scenes_to_analyze = [
            (scene.heading, scene.content) for scene in screenplay.scenes
        ]

    if not scenes_to_analyze:
        return PacingReport()

    # Analyze each scene
    scene_pacings: list[ScenePacing] = []
    all_issues: list[str] = []

    for i, (heading, content) in enumerate(scenes_to_analyze, start=1):
        total, dialogue, action = _parse_scene_lines(content)
        dialogue_ratio = round(dialogue / total, 2) if total > 0 else 0.0

        pacing = _classify_pacing(total, dialogue_ratio)
        issues = _detect_issues(total, dialogue, dialogue_ratio)
        all_issues.extend(issues)

        scene_pacings.append(ScenePacing(
            scene_number=i,
            heading=heading,
            line_count=total,
            dialogue_lines=dialogue,
            action_lines=action,
            dialogue_ratio=dialogue_ratio,
            pacing=pacing,
            issues=issues,
        ))

    # Derive aggregate metrics
    overall_pacing = _classify_overall_pacing(scene_pacings)
    avg_scene_length = (
        sum(s.line_count for s in scene_pacings) / len(scene_pacings)
        if scene_pacings
        else 0.0
    )

    # Deduplicate recommendations
    unique_issues = list(set(all_issues))
    recommendations = _generate_recommendations(unique_issues)

    return PacingReport(
        scenes=scene_pacings,
        overall_pacing=overall_pacing,
        avg_scene_length=round(avg_scene_length, 1),
        total_issues=len(all_issues),
        recommendations=recommendations,
    )
