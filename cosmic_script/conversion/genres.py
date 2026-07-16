"""Genre-specific formatting styles for screenplay conversion.

Provides presets that influence scene length, dialogue ratio, transition
style, action density, and prompt guidance for each supported genre.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class GenreStyle:
    """Definition of a genre's structural and tonal characteristics.

    Attributes:
        name: Short identifier (e.g. ``"classic"``, ``"noir"``).
        description: Human-readable explanation of the genre style.
        scene_length: Target scene length — ``"short"`` (2-5 lines),
            ``"medium"`` (5-15), ``"long"`` (10-30).
        dialogue_ratio: Target dialogue-to-action ratio — ``"low"`` (~30%),
            ``"balanced"`` (~50%), ``"high"`` (~70%).
        transition_style: How often transitions are used — ``"minimal"``,
            ``"moderate"``, ``"heavy"``.
        parenthetical_guidance: Frequency of parentheticals — ``"rare"``,
            ``"moderate"``, ``"frequent"``.
        action_style: Verbosity of action lines — ``"concise"``,
            ``"descriptive"``, ``"cinematic"``.
        prompt_addition: Extra text appended to the user prompt (~200 tokens
            max) to guide LLM output toward the genre's conventions.
    """

    name: str
    description: str
    scene_length: str = "medium"
    dialogue_ratio: str = "balanced"
    transition_style: str = "moderate"
    parenthetical_guidance: str = "moderate"
    action_style: str = "descriptive"
    prompt_addition: str = ""


# ---------------------------------------------------------------------------
# Preset genres
# ---------------------------------------------------------------------------

_GENRES: dict[str, GenreStyle] = {
    "classic": GenreStyle(
        name="classic",
        description="Balanced, traditional Hollywood structure",
        prompt_addition=(
            "Use balanced scene lengths with moderate transitions. "
            "Maintain a 50/50 dialogue-to-action ratio. "
            "Scene headings follow standard INT./EXT. format. "
            "Character entrances and exits should be clearly indicated."
        ),
    ),
    "modern": GenreStyle(
        name="modern",
        description="Quick cuts, minimal action, dialogue-driven",
        scene_length="short",
        dialogue_ratio="high",
        transition_style="heavy",
        parenthetical_guidance="rare",
        action_style="concise",
        prompt_addition=(
            "Keep scenes short (2-5 lines). Use frequent transitions "
            "like CUT TO: and SMASH CUT TO:. Prioritise dialogue over "
            "action — aim for 70% dialogue. Action lines must be brief "
            "and punchy. Avoid parentheticals. Fast pacing is essential."
        ),
    ),
    "tarantino": GenreStyle(
        name="tarantino",
        description="Long dialogue scenes, pop culture references, non-linear hints",
        scene_length="long",
        dialogue_ratio="high",
        transition_style="minimal",
        parenthetical_guidance="frequent",
        action_style="descriptive",
        prompt_addition=(
            "Write extended dialogue scenes where characters 'talk around' "
            "the subject. Include pop culture references in dialogue where "
            "appropriate. Action descriptions can be verbose and stylised. "
            "Use parentheticals freely to capture tone. Hint at non-linear "
            "storytelling through scene structure."
        ),
    ),
    "noir": GenreStyle(
        name="noir",
        description="Heavy atmosphere, voice-over, shadow descriptions",
        scene_length="medium",
        dialogue_ratio="balanced",
        transition_style="moderate",
        parenthetical_guidance="moderate",
        action_style="cinematic",
        prompt_addition=(
            "Emphasise atmosphere in action lines — shadows, rain, smoke, "
            "and low-key lighting. Use (V.O.) for voice-over narration. "
            "Dialogue should be terse with subtext. Action descriptions "
            "should feel cinematic and moody. Noir tropes like detectives, "
            "femmes fatales, and moral ambiguity are welcome."
        ),
    ),
    "comedy": GenreStyle(
        name="comedy",
        description="Fast pacing, visual gags, short scenes",
        scene_length="short",
        dialogue_ratio="balanced",
        transition_style="heavy",
        parenthetical_guidance="rare",
        action_style="concise",
        prompt_addition=(
            "Keep scenes short and punchy. Use visual gags in action "
            "lines. Dialogue should have quick wit and comedic timing. "
            "Use transitions freely to maintain brisk pacing. Avoid "
            "parentheticals — let the dialogue land on its own. Aim "
            "for 3-5 lines per scene maximum."
        ),
    ),
    "horror": GenreStyle(
        name="horror",
        description="Slow build, atmospheric action, sudden transitions",
        scene_length="medium",
        dialogue_ratio="low",
        transition_style="heavy",
        parenthetical_guidance="rare",
        action_style="cinematic",
        prompt_addition=(
            "Build tension through slow, atmospheric action descriptions. "
            "Use sudden transitions (SMASH CUT TO:) for scares. Keep "
            "dialogue minimal — let the visuals carry the horror. "
            "Describe sounds, shadows, and the uncanny in action lines. "
            "Short, punchy sentences increase dread."
        ),
    ),
    "action": GenreStyle(
        name="action",
        description="Short scenes, heavy transitions, minimal dialogue",
        scene_length="short",
        dialogue_ratio="low",
        transition_style="heavy",
        parenthetical_guidance="rare",
        action_style="concise",
        prompt_addition=(
            "Prioritise action over dialogue (70/30 split). Use very "
            "short scenes and heavy transitions (CUT TO:, SMASH CUT TO:). "
            "Action lines should be concise and physically descriptive. "
            "Dialogue should be minimal and functional. No parentheticals. "
            "Keep the momentum high throughout."
        ),
    ),
    "drama": GenreStyle(
        name="drama",
        description="Character-focused, balanced dialogue/action",
        scene_length="medium",
        dialogue_ratio="balanced",
        transition_style="moderate",
        parenthetical_guidance="moderate",
        action_style="descriptive",
        prompt_addition=(
            "Focus on character development and emotional depth. "
            "Balance dialogue and action evenly. Allow scenes to breathe "
            "with moderate length. Use parentheticals when delivery is "
            "important to character. Action should reveal character "
            "interiority through external behaviour."
        ),
    ),
}


def get_genre_style(genre: Optional[str]) -> GenreStyle:
    """Return the :class:`GenreStyle` for *genre*, defaulting to classic.

    Args:
        genre: Genre name (case-insensitive). ``None`` or unknown genres
            return the ``"classic"`` preset.

    Returns:
        The matching :class:`GenreStyle` instance.
    """
    if not genre:
        return _GENRES["classic"]
    key = genre.strip().lower()
    return _GENRES.get(key, _GENRES["classic"])


def list_genres() -> list[dict[str, str]]:
    """Return a list of available genre names and descriptions."""
    return [
        {"name": g.name, "description": g.description}
        for g in _GENRES.values()
    ]
