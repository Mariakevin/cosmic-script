"""Deterministic post-processing for LLM screenplay output.

Applies rule-based fixes to improve Fountain formatting quality
without additional LLM calls. These are cheap, fast, and catch
common LLM mistakes.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scene heading fixes
# ---------------------------------------------------------------------------

_VALID_TIME_OF_DAY = {
    "DAY", "NIGHT", "DAWN", "DUSK", "MORNING", "AFTERNOON",
    "EVENING", "MIDNIGHT", "LATER", "CONTINUOUS", "SAME",
}

_LOCATION_PATTERN = re.compile(
    r"^(?:INT\.|EXT\.|INT/EXT\.|I/E\.)\s+",
    re.IGNORECASE,
)


def fix_scene_headings(text: str) -> str:
    """Fix common scene heading formatting issues.

    - Ensures INT./EXT. prefix
    - Converts location to ALL CAPS
    - Ensures time-of-day is valid
    """
    lines = text.split("\n")
    fixed = []

    for line in lines:
        stripped = line.strip()

        # Check if this looks like a scene heading but is missing INT./EXT.
        if _looks_like_location(stripped) and not _LOCATION_PATTERN.match(stripped):
            # Try to infer INT./EXT. from context
            if any(word in stripped.upper() for word in ["ROOM", "HOUSE", "APARTMENT", "OFFICE", "HALL", "CORRIDOR"]):
                stripped = f"INT. {stripped}"
            else:
                stripped = f"EXT. {stripped}"

        # Fix ALL CAPS for location part
        if _LOCATION_PATTERN.match(stripped):
            parts = stripped.split(" - ", 1)
            if len(parts) == 2:
                location = parts[0].strip()
                time_of_day = parts[1].strip().upper()
                # Ensure time-of-day is valid
                if time_of_day not in _VALID_TIME_OF_DAY:
                    time_of_day = "DAY"  # Default to DAY
                stripped = f"{location} - {time_of_day}"

        fixed.append(stripped if stripped != line.rstrip() else line)

    return "\n".join(fixed)


def _looks_like_location(text: str) -> bool:
    """Heuristic: does this text look like a scene location?"""
    text_upper = text.upper()
    # Short, all-caps, contains location-like words
    if len(text) < 50 and text_upper == text and " - " in text_upper:
        return True
    return False


# ---------------------------------------------------------------------------
# Character cue fixes
# ---------------------------------------------------------------------------

def fix_character_cues(text: str) -> str:
    """Fix character cue formatting.

    - Ensures ALL CAPS
    - Removes extensions from detection (V.O., O.S. stay)
    - Flags very long character names
    """
    lines = text.split("\n")
    fixed = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this is a character cue (short line before dialogue)
        if _is_character_cue(stripped):
            # Ensure ALL CAPS
            name_part = stripped.split("(")[0].strip()
            ext_part = stripped[len(name_part):]
            name_upper = name_part.upper()
            stripped = f"{name_upper}{ext_part}"

            # Warn if too long
            if len(stripped) > 25:
                logger.warning(
                    "Character cue very long (%d chars): %s",
                    len(stripped),
                    stripped,
                )

        fixed.append(stripped if stripped != line.rstrip() else line)

    return "\n".join(fixed)


def _is_character_cue(text: str) -> bool:
    """Heuristic: is this line a character cue?

    Detects:
    - ALL CAPS lines (standard Fountain)
    - Capitalized single-word lines (common LLM mistake)
    """
    if not text:
        return False
    # ALL CAPS, reasonable length, not a scene heading
    if text.upper() == text and len(text) <= 30 and len(text) >= 2:
        if not _LOCATION_PATTERN.match(text) and not text.endswith("TO:"):
            return True
    # Capitalized single word (e.g., "Sarah") - possible LLM mistake
    if (
        len(text) <= 25
        and text[0].isupper()
        and " " not in text.strip()
        and not text.endswith(".")
        and not _LOCATION_PATTERN.match(text)
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Camera direction removal
# ---------------------------------------------------------------------------

_CAMERA_DIRECTIONS = re.compile(
    r"\b(CLOSE UP|CLOSE-UP|CLOSEUP|WIDE SHOT|WIDE ANGLE|"
    r"EXTREME CLOSE UP|EXTREME WIDE SHOT|"
    r"PAN (LEFT|RIGHT|UP|DOWN)|PANNING|"
    r"DOLLY (IN|OUT)|DOLLYING|"
    r"TRACKING SHOT|TRUCK (LEFT|RIGHT)|"
    r"CRANE SHOT|JIB SHOT|"
    r"TILT (UP|DOWN)|TILTING|"
    r"ZOOM (IN|OUT)|ZOOMING|"
    r"STEADICAM|HANDHELD|"
    r"PULL FOCUS|RACK FOCUS|"
    r"POV SHOT|POINT OF VIEW|"
    r"OVER THE SHOULDER|OTS|"
    r"HIGH ANGLE|LOW ANGLE|"
    r"BIRDS EYE|WORMS EYE|"
    r"INSERT SHOT|CUTAWAY|"
    r"反应镜头|reaction shot)\b",
    re.IGNORECASE,
)


def remove_camera_directions(text: str) -> str:
    """Remove camera directions from action lines.

    These belong in a shooting script, not a spec screenplay.
    """
    lines = text.split("\n")
    fixed = []

    for line in lines:
        stripped = line.strip()
        # Only process action lines (not scene headings, character cues, etc.)
        if not _LOCATION_PATTERN.match(stripped) and not _is_character_cue(stripped):
            # Remove camera directions
            cleaned = _CAMERA_DIRECTIONS.sub("", stripped)
            # Clean up extra spaces
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
            if cleaned != stripped:
                logger.debug("Removed camera direction: '%s' -> '%s'", stripped, cleaned)
                stripped = cleaned

        fixed.append(stripped if stripped != line.rstrip() else line)

    return "\n".join(fixed)


# ---------------------------------------------------------------------------
# Inner thought removal
# ---------------------------------------------------------------------------

_INNER_THOUGHT_PATTERNS = [
    re.compile(r"\b(she|he|they|I)\s+(thought|wondered|pondered|reflected|considered|realized|knew|felt|believed|imagined|recalled|remembered)\b", re.IGNORECASE),
    re.compile(r"\b(in his|in her|in their)\s+(mind|thoughts|head)\b", re.IGNORECASE),
    re.compile(r"\b(the thought (that|of)|the realization that)\b", re.IGNORECASE),
]


def fix_inner_thoughts(text: str) -> str:
    """Convert novelistic inner thoughts to screenplay-appropriate format.

    Inner thoughts in action lines should be converted to:
    - V.O. dialogue (if important)
    - Removed (if redundant with visible action)
    """
    lines = text.split("\n")
    fixed = []

    for line in lines:
        stripped = line.strip()
        # Only process action lines
        if not _LOCATION_PATTERN.match(stripped) and not _is_character_cue(stripped):
            for pattern in _INNER_THOUGHT_PATTERNS:
                if pattern.search(stripped):
                    # Log but don't auto-fix (too risky)
                    logger.warning(
                        "Inner thought detected (consider V.O.): %s",
                        stripped[:80],
                    )
                    break

        fixed.append(line)

    return "\n".join(fixed)


# ---------------------------------------------------------------------------
# Transition fixes
# ---------------------------------------------------------------------------

def fix_transitions(text: str) -> str:
    """Fix transition formatting.

    - Ensures ALL CAPS
    - Ensures proper TO: suffix
    """
    lines = text.split("\n")
    fixed = []

    for line in lines:
        stripped = line.strip()

        # Check if this looks like a transition
        if _looks_like_transition(stripped):
            # Ensure ALL CAPS
            if stripped != stripped.upper():
                stripped = stripped.upper()
            # Ensure proper TO: suffix
            if stripped.endswith("TO") and not stripped.endswith("TO:"):
                stripped = stripped + ":"

        fixed.append(stripped if stripped != line.rstrip() else line)

    return "\n".join(fixed)


def _looks_like_transition(text: str) -> bool:
    """Heuristic: is this line a transition?"""
    text_upper = text.upper()
    transition_words = ["CUT", "FADE", "DISSOLVE", "SMASH", "MATCH", "JUMP"]
    return (
        any(text_upper.startswith(w) for w in transition_words)
        and ("TO" in text_upper or "OUT" in text_upper or "IN" in text_upper)
        and len(text) < 40
    )


# ---------------------------------------------------------------------------
# Scene merging and splitting
# ---------------------------------------------------------------------------

def merge_short_scenes(
    scenes: list[dict],
    min_lines: int = 3,
) -> list[dict]:
    """Merge very short scenes with adjacent scenes.

    Scenes with fewer than min_lines of content are merged with
    the previous scene (if same location) or next scene.

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.
        min_lines: Minimum lines to keep a scene separate.

    Returns:
        Merged list of scenes.
    """
    if not scenes:
        return scenes

    merged = [scenes[0]]

    for scene in scenes[1:]:
        current_content = scene.get("content", "").strip()
        current_lines = [l for l in current_content.split("\n") if l.strip()]

        if len(current_lines) < min_lines:
            # Merge with previous scene
            prev = merged[-1]
            prev_heading = prev.get("heading", "")
            curr_heading = scene.get("heading", "")

            # Only merge if same location type (both INT. or both EXT.)
            prev_type = "INT" if "INT" in prev_heading.upper() else "EXT"
            curr_type = "INT" if "INT" in curr_heading.upper() else "EXT"

            if prev_type == curr_type:
                # Merge content
                prev_content = prev.get("content", "")
                prev["content"] = f"{prev_content}\n\n{current_content}".strip()
                logger.debug(
                    "Merged short scene '%s' into '%s'",
                    curr_heading[:30],
                    prev_heading[:30],
                )
                continue

        merged.append(scene)

    return merged


def split_long_scenes(
    scenes: list[dict],
    max_lines: int = 30,
) -> list[dict]:
    """Split very long scenes at natural break points.

    Scenes with more than max_lines are split at:
    - Character cue changes (dialogue turns)
    - Empty lines
    - Action beats (period followed by newline)

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.
        max_lines: Maximum lines before splitting.

    Returns:
        Split list of scenes.
    """
    result = []

    for scene in scenes:
        content = scene.get("content", "").strip()
        lines = content.split("\n")

        if len(lines) <= max_lines:
            result.append(scene)
            continue

        # Find split points
        split_points = [0]
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Split at dialogue turns (character cues)
            if _is_character_cue(stripped) and i > split_points[-1] + 5:
                split_points.append(i)
            # Split at double newlines (scene breaks)
            elif not stripped and i > 0 and lines[i-1].strip() and i > split_points[-1] + 5:
                split_points.append(i)
        # If no natural split points found, split at regular intervals
        if len(split_points) == 1:
            step = max_lines
            for i in range(step, len(lines), step):
                if i > split_points[-1] + 3:  # Don't split too close to previous
                    split_points.append(i)
        split_points.append(len(lines))

        # Create split scenes
        heading = scene.get("heading", "INT. LOCATION - DAY")
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]
            split_content = "\n".join(lines[start:end]).strip()

            if split_content:
                # Add scene heading to splits (except first)
                if i > 0:
                    split_content = f"{heading}\n\n{split_content}"

                result.append({
                    "heading": heading,
                    "content": split_content,
                })

        logger.debug(
            "Split long scene '%s' into %d parts",
            heading[:30],
            len(split_points) - 1,
        )

    return result


# ---------------------------------------------------------------------------
# Main post-processing pipeline
# ---------------------------------------------------------------------------

def postprocess_fountain(text: str) -> str:
    """Apply all deterministic fixes to Fountain text.

    This is a cheap, fast post-processing step that catches common
    LLM mistakes without additional LLM calls.

    Args:
        text: Raw Fountain text from LLM.

    Returns:
        Cleaned and corrected Fountain text.
    """
    if not text or not text.strip():
        return text

    # Apply fixes in order
    text = fix_scene_headings(text)
    text = fix_character_cues(text)
    text = remove_camera_directions(text)
    text = fix_inner_thoughts(text)
    text = fix_transitions(text)

    return text


def postprocess_scenes(scenes: list[dict]) -> list[dict]:
    """Apply scene-level post-processing.

    - Merge short scenes
    - Split long scenes

    Args:
        scenes: List of scene dicts with 'heading' and 'content' keys.

    Returns:
        Optimized list of scenes.
    """
    if not scenes:
        return scenes

    scenes = merge_short_scenes(scenes)
    scenes = split_long_scenes(scenes)

    return scenes
