"""Logline generator for screenplays.

Generates a one-sentence logline in the standard format:
[PROTAGONIST] [WANTS] [OBSTACLE] [STAKES]
"""

from __future__ import annotations

import logging
from typing import Optional

from cosmic_script.export.fountain import generate_fountain
from cosmic_script.models import Screenplay

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_LOGLINE_SYSTEM_PROMPT = """You are a professional script analyst. Write a single-sentence logline for the provided screenplay.

A logline must follow this format:
[PROTAGONIST] [WANTS SOMETHING SPECIFIC] [BUT FACES A MAJOR OBSTACLE] [OR ELSE STAKES].

Rules:
- One sentence only (25-50 words maximum).
- No character names — use archetypes or descriptors ("A detective", "A grieving mother").
- No setup or backstory — start with the protagonist's want.
- Make it compelling — the logline should make someone want to read the script.

Output ONLY the logline sentence. No labels, no quotes, no extra text."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_logline(
    screenplay: Screenplay,
    model: str = "gemini/gemini-2.5-flash",
    api_key: Optional[str] = None,
) -> str:
    """Generate a one-sentence logline for the screenplay.

    The logline follows the standard format:
    ``[PROTAGONIST] [WANTS] [OBSTACLE] [STAKES]``

    Args:
        screenplay: The screenplay data model.
        model: LLM model identifier. Pass ``"demo"`` to return a
            placeholder logline without calling the LLM.
        api_key: Optional API key override.

    Returns:
        A single sentence (25-50 words) summarising the screenplay's
        dramatic core.

    Example:
        >>> from cosmic_script.models import Screenplay, ScreenplayElement
        >>> sp = Screenplay(title="Test", elements=[
        ...     ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - DAY"),
        ... ])
        >>> logline = generate_logline(sp, model="demo")
        >>> len(logline) > 10
        True
    """
    fountain_text = generate_fountain(screenplay)
    if not fountain_text.strip():
        return "(empty screenplay)"

    # Demo mode — return placeholder
    if model == "demo":
        return (
            "A small-town detective must unravel a series of cryptic clues "
            "left by a shadowy figure before the next full moon claims another victim."
        )

    messages = [
        {"role": "system", "content": _LOGLINE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Generate a logline for this screenplay:\n\n{fountain_text}",
        },
    ]

    from cosmic_script.conversion.model_router import get_router

    router = get_router()
    if api_key:
        router.api_key = api_key

    try:
        raw_response, model_used = router.call_with_fallback(
            messages=messages,
            temperature=0.5,
            max_tokens=256,
            preferred_model=model,
        )
    except Exception as exc:
        logger.error("Logline LLM call failed: %s", exc)
        return f"(logline generation failed: {exc})"

    text = raw_response.strip()
    # Strip surrounding quotes if present
    if text.startswith(('"', "'")) and text.endswith(('"', "'")):
        text = text[1:-1]

    # Limit to ~50 words
    words = text.split()
    if len(words) > 50:
        text = " ".join(words[:50]) + "."

    return text
