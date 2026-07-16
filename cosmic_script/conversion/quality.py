"""Algorithmic quality checks for screenplay output.

Provides deterministic quality scoring without LLM calls.
Checks pacing, dialogue ratios, scene structure, and more.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Quality assessment report for a screenplay."""

    dialogue_ratio: float = 0.0
    """Percentage of lines that are dialogue (0.0 - 1.0)."""

    action_ratio: float = 0.0
    """Percentage of lines that are action (0.0 - 1.0)."""

    scene_count: int = 0
    """Total number of scenes."""

    avg_scene_length: float = 0.0
    """Average lines per scene."""

    character_count: int = 0
    """Number of unique characters speaking."""

    pacing_score: float = 0.0
    """Pacing quality score (0.0 - 10.0)."""

    formatting_score: float = 0.0
    """Formatting quality score (0.0 - 10.0)."""

    warnings: list[str] = field(default_factory=list)
    """Quality warnings."""

    suggestions: list[str] = field(default_factory=list)
    """Improvement suggestions."""

    @property
    def overall_score(self) -> float:
        """Overall quality score (0.0 - 10.0)."""
        return (self.pacing_score + self.formatting_score) / 2


# ---------------------------------------------------------------------------
# Dialogue ratio analysis
# ---------------------------------------------------------------------------

def analyze_dialogue_ratio(scenes: list[dict]) -> dict:
    """Analyze dialogue-to-action ratio.

    Industry standards:
    - Drama: 40-60% dialogue
    - Comedy: 50-70% dialogue
    - Action: 20-40% dialogue
    - Thriller: 30-50% dialogue

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.

    Returns:
        Dict with 'dialogue_ratio', 'action_ratio', 'warnings'.
    """
    total_lines = 0
    dialogue_lines = 0
    action_lines = 0
    warnings = []

    for scene in scenes:
        content = scene.get("content", "")
        raw_lines = content.split("\n")

        for raw_line in raw_lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            total_lines += 1
            # Dialogue: indented under character cue (check raw line before stripping)
            if raw_line.startswith("    ") or raw_line.startswith("\t"):
                dialogue_lines += 1
            # Character cue
            elif stripped.isupper() and len(stripped) <= 30:
                dialogue_lines += 1  # Count as dialogue block
            # Parenthetical
            elif stripped.startswith("(") and stripped.endswith(")"):
                dialogue_lines += 1
            else:
                action_lines += 1

    if total_lines == 0:
        return {"dialogue_ratio": 0.0, "action_ratio": 0.0, "warnings": ["Empty screenplay"]}

    dialogue_ratio = dialogue_lines / total_lines
    action_ratio = action_lines / total_lines

    # Check against industry norms
    if dialogue_ratio > 0.7:
        warnings.append(f"High dialogue ratio ({dialogue_ratio:.0%}) — consider adding more action beats")
    elif dialogue_ratio < 0.2:
        warnings.append(f"Low dialogue ratio ({dialogue_ratio:.0%}) — consider adding more character interaction")

    return {
        "dialogue_ratio": dialogue_ratio,
        "action_ratio": action_ratio,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Scene pacing analysis
# ---------------------------------------------------------------------------

def analyze_scene_pacing(scenes: list[dict]) -> dict:
    """Analyze scene pacing and structure.

    Checks:
    - Scene count vs chapter length
    - Average scene length
    - Very short scenes (< 3 lines)
    - Very long scenes (> 30 lines)
    - Scene heading variety (INT./EXT. mix)

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.

    Returns:
        Dict with pacing metrics and warnings.
    """
    if not scenes:
        return {
            "scene_count": 0,
            "avg_scene_length": 0,
            "location_count": 0,
            "pacing_score": 0,
            "warnings": ["No scenes found"],
            "suggestions": ["Add scene headings"],
        }

    scene_count = len(scenes)
    scene_lengths = []
    warnings = []
    suggestions = []
    locations = set()

    for scene in scenes:
        content = scene.get("content", "")
        heading = scene.get("heading", "")

        # Count lines
        lines = [l for l in content.split("\n") if l.strip()]
        scene_lengths.append(len(lines))

        # Track locations
        locations.add(heading.split(" - ")[0] if " - " in heading else heading)

        # Check for very short scenes
        if len(lines) < 3:
            warnings.append(f"Very short scene ({len(lines)} lines): {heading[:40]}")

        # Check for very long scenes
        if len(lines) > 30:
            warnings.append(f"Very long scene ({len(lines)} lines): {heading[:40]}")
            suggestions.append(f"Consider splitting '{heading[:30]}' into multiple scenes")

    avg_length = sum(scene_lengths) / len(scene_lengths) if scene_lengths else 0

    # Check scene count
    if scene_count < 3:
        warnings.append(f"Only {scene_count} scenes — screenplay may feel rushed")
    elif scene_count > 15:
        warnings.append(f"Many scenes ({scene_count}) — screenplay may feel fragmented")

    # Check location variety
    if len(locations) < 2 and scene_count > 3:
        suggestions.append("Consider adding more location variety")

    # Calculate pacing score (0-10)
    pacing_score = 7.0  # Base score
    if 5 <= scene_count <= 12:
        pacing_score += 1.0  # Good scene count
    if 5 <= avg_length <= 20:
        pacing_score += 1.0  # Good average length
    if len([s for s in scene_lengths if s < 3]) == 0:
        pacing_score += 0.5  # No very short scenes
    if len([s for s in scene_lengths if s > 30]) == 0:
        pacing_score += 0.5  # No very long scenes

    pacing_score = min(10.0, pacing_score)

    return {
        "scene_count": scene_count,
        "avg_scene_length": avg_length,
        "location_count": len(locations),
        "pacing_score": pacing_score,
        "warnings": warnings,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Character appearance analysis
# ---------------------------------------------------------------------------

def analyze_character_appearance(
    scenes: list[dict],
    registry_characters,
) -> dict:
    """Analyze character appearance across scenes.

    Checks:
    - Characters in registry but never speaking
    - Characters appearing only in one scene
    - Main characters disappearing for long stretches

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.
        registry_characters: Set of character names, or dict (keys are names).

    Returns:
        Dict with character appearance analysis.
    """
    # Handle both set and dict inputs
    if isinstance(registry_characters, dict):
        char_names = set(registry_characters.keys())
    else:
        char_names = set(registry_characters)

    if not char_names:
        return {"warnings": [], "suggestions": []}

    character_scenes: dict[str, list[int]] = {name: [] for name in char_names}
    warnings = []
    suggestions = []

    for i, scene in enumerate(scenes):
        content = scene.get("content", "")
        # Find character cues (ALL CAPS lines)
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.isupper() and 2 <= len(stripped) <= 30:
                # Check if this matches any registry character
                for name in registry_characters:
                    if name.upper() in stripped:
                        character_scenes[name].append(i)
                        break

    # Check for characters that never appear
    never_appear = [name for name, appearances in character_scenes.items() if not appearances]
    if never_appear:
        suggestions.append(
            f"Characters in registry but never speaking: {', '.join(never_appear[:3])}"
        )

    # Check for characters appearing only once
    single_appear = [name for name, appearances in character_scenes.items() if len(appearances) == 1]
    if single_appear:
        suggestions.append(
            f"Characters with only 1 scene: {', '.join(single_appear[:3])}"
        )

    # Check for long gaps in character appearances
    for name, appearances in character_scenes.items():
        if len(appearances) >= 2:
            for i in range(1, len(appearances)):
                gap = appearances[i] - appearances[i-1]
                if gap > 5:
                    warnings.append(
                        f"{name} disappears for {gap} scenes between scenes {appearances[i-1]+1} and {appearances[i]+1}"
                    )
                    break

    return {
        "character_appearances": {k: len(v) for k, v in character_scenes.items()},
        "warnings": warnings,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# Formatting quality analysis
# ---------------------------------------------------------------------------

def analyze_formatting(text: str) -> dict:
    """Analyze Fountain formatting quality.

    Checks:
    - Scene heading format
    - Character cue format
    - Dialogue indentation
    - Transition format
    - Common formatting mistakes

    Args:
        text: Raw Fountain text.

    Returns:
        Dict with formatting score and issues.
    """
    lines = text.split("\n")
    issues = []
    score = 10.0

    scene_heading_pattern = re.compile(r"^(?:INT\.|EXT\.|INT/EXT\.|I/E\.)\s+")
    character_pattern = re.compile(r"^[A-Z][A-Z\s]{1,25}$")

    prev_was_character = False
    in_dialogue = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check scene headings
        if scene_heading_pattern.match(stripped):
            in_dialogue = False
            prev_was_character = False
            # Check for time-of-day
            if " - " not in stripped:
                issues.append(f"Line {i+1}: Scene heading missing time-of-day: {stripped[:40]}")
                score -= 0.5
            continue

        # Check character cues
        if character_pattern.match(stripped):
            prev_was_character = True
            in_dialogue = True
            continue

        # Check dialogue (should be indented)
        if in_dialogue and stripped and not stripped.startswith("("):
            if not line.startswith("    ") and not line.startswith("\t"):
                issues.append(f"Line {i+1}: Dialogue not indented: {stripped[:40]}")
                score -= 0.3
            prev_was_character = False
            continue

        # Check for camera directions
        camera_words = ["CLOSE UP", "WIDE SHOT", "PAN ", "DOLLY", "TRACKING"]
        if any(word in stripped.upper() for word in camera_words):
            issues.append(f"Line {i+1}: Camera direction in action: {stripped[:40]}")
            score -= 0.2

        # Check for "WE SEE" / "WE HEAR"
        if stripped.upper().startswith("WE SEE") or stripped.upper().startswith("WE HEAR"):
            issues.append(f"Line {i+1}: 'We see/we hear' in action: {stripped[:40]}")
            score -= 0.3

        in_dialogue = False
        prev_was_character = False

    score = max(0.0, score)

    return {
        "formatting_score": score,
        "issues": issues,
        "line_count": len(lines),
    }


# ---------------------------------------------------------------------------
# Main quality analysis pipeline
# ---------------------------------------------------------------------------

def analyze_quality(
    text: str,
    scenes: list[dict],
    registry_characters=None,
) -> QualityReport:
    """Run all quality checks and produce a report.

    Args:
        text: Raw Fountain text.
        scenes: Parsed scene dicts.
        registry_characters: Set of known character names.

    Returns:
        QualityReport with all metrics and warnings.
    """
    report = QualityReport()

    # Dialogue ratio
    dialogue_result = analyze_dialogue_ratio(scenes)
    report.dialogue_ratio = dialogue_result["dialogue_ratio"]
    report.action_ratio = dialogue_result["action_ratio"]
    report.warnings.extend(dialogue_result["warnings"])

    # Scene pacing
    pacing_result = analyze_scene_pacing(scenes)
    report.scene_count = pacing_result["scene_count"]
    report.avg_scene_length = pacing_result["avg_scene_length"]
    report.pacing_score = pacing_result["pacing_score"]
    report.warnings.extend(pacing_result["warnings"])
    report.suggestions.extend(pacing_result["suggestions"])

    # Character appearance
    if registry_characters:
        char_result = analyze_character_appearance(scenes, registry_characters)
        report.character_count = len([
            name for name, count in char_result["character_appearances"].items()
            if count > 0
        ])
        report.warnings.extend(char_result["warnings"])
        report.suggestions.extend(char_result["suggestions"])

    # Formatting
    format_result = analyze_formatting(text)
    report.formatting_score = format_result["formatting_score"]
    # Only add formatting issues as warnings if score is low
    if format_result["formatting_score"] < 7.0:
        report.warnings.append(
            f"Formatting issues found ({len(format_result['issues'])} issues)"
        )

    return report
