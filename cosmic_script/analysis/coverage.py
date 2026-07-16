"""Script coverage report generation using LLM.

Generates professional script coverage (logline, synopsis, strengths,
weaknesses, rating, recommendation) by submitting the screenplay Fountain
text to an LLM and parsing the structured JSON response.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from cosmic_script.export.fountain import generate_fountain
from cosmic_script.models import Screenplay

# Lazy import to avoid circular dependency at module level
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ScriptCoverage:
    """Professional script coverage report.

    Attributes:
        logline: One-sentence story summary.
        synopsis: 1-2 paragraph narrative summary.
        strengths: 3-5 bullet points describing what works.
        weaknesses: 3-5 bullet points describing what needs improvement.
        rating: Numeric rating 1-10.
        recommendation: "Pass", "Consider", or "Strong Consider".
        genre: Detected or provided genre.
        target_audience: Suggested target audience.
        model_used: The LLM model that generated this coverage (if known).
    """

    logline: str = ""
    synopsis: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    rating: int = 5
    recommendation: str = "Consider"
    genre: str = ""
    target_audience: str = ""
    model_used: str = ""


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_COVERAGE_SYSTEM_PROMPT = """You are a professional script reader at a major studio. Your job is to provide honest, constructive, and insightful coverage for screenplays. Read the following Fountain-formatted screenplay and produce a structured coverage report.

Your response must be valid JSON only (no markdown fences, no extra text) with these exact keys:
- "logline": One sentence summarizing who the protagonist is, what they want, the obstacle, and the stakes.
- "synopsis": 1-2 paragraphs summarizing the story (character, setup, conflict, resolution).
- "strengths": Array of 3-5 specific strengths.
- "weaknesses": Array of 3-5 specific weaknesses (be constructive, not harsh).
- "rating": Integer 1-10 (10 = exceptional, 1 = unsalvageable). Be honest — most scripts land between 4 and 7.
- "recommendation": One of "Pass", "Consider", or "Strong Consider".
- "genre": The primary genre of this screenplay.
- "target_audience": Who this screenplay would appeal to.

CRITERIA:
- Story: originality, structure, pacing, plot coherence.
- Characters: depth, arc, dialogue authenticity, motivation.
- Format: proper scene headings, character cues, dialogue formatting.
- Marketability: genre appeal, target audience, production feasibility.

Be specific in your feedback. Reference particular scenes, characters, or lines when possible."""


def _build_messages(fountain_text: str) -> list[dict]:
    """Build the system+user message list for the LLM call."""
    return [
        {"role": "system", "content": _COVERAGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Please provide coverage for the following screenplay:\n\n"
                f"{fountain_text}"
            ),
        },
    ]


def _parse_coverage_response(raw: str, model_used: str) -> ScriptCoverage:
    """Parse the LLM JSON response into a ScriptCoverage dataclass.

    Handles minor formatting deviations (markdown fences, trailing commas)
    gracefully.  Returns a partially-populated ScriptCoverage on parse
    failure rather than raising.
    """
    text = raw.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        # Find the first and last ```
        start = text.index("\n", text.index("```")) + 1
        end = text.rindex("```")
        text = text[start:end].strip()
        # Also strip language tag line if present
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse coverage JSON: %s", exc)
        logger.debug("Raw response: %s", raw[:500])
        return ScriptCoverage(
            logline="(coverage generation failed)",
            weaknesses=[f"JSON parse error: {exc}"],
            model_used=model_used,
        )

    # Map fields with fallbacks
    return ScriptCoverage(
        logline=data.get("logline", ""),
        synopsis=data.get("synopsis", ""),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        rating=_clamp_rating(data.get("rating", 5)),
        recommendation=_normalize_recommendation(data.get("recommendation", "Consider")),
        genre=data.get("genre", ""),
        target_audience=data.get("target_audience", ""),
        model_used=model_used,
    )


def _clamp_rating(rating: int) -> int:
    """Clamp rating to 1-10 range."""
    try:
        r = int(rating)
    except (ValueError, TypeError):
        return 5
    return max(1, min(10, r))


def _normalize_recommendation(rec: str) -> str:
    """Normalize recommendation to one of the three valid values."""
    r = rec.strip().lower()
    if r in ("pass", "consider", "strong consider"):
        if r == "strong consider":
            return "Strong Consider"
        return r.capitalize()
    return "Consider"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_coverage(
    screenplay: Screenplay,
    model: str = "gemini/gemini-2.5-flash",
    api_key: Optional[str] = None,
) -> ScriptCoverage:
    """Generate professional script coverage using an LLM.

    Args:
        screenplay: The screenplay data model to analyse.
        model: LLM model identifier. Pass ``"demo"`` to bypass the LLM
            and return a placeholder coverage report (useful for frontend
            development).
        api_key: Optional API key override. Falls back to environment
            variables.

    Returns:
        A :class:`ScriptCoverage` dataclass with the LLM-generated coverage.

    Example:
        >>> from cosmic_script.models import Screenplay, ScreenplayElement
        >>> sp = Screenplay(title="Test", elements=[
        ...     ScreenplayElement(element_type="scene_heading", text="INT. HOUSE - DAY"),
        ... ])
        >>> cov = generate_coverage(sp, model="demo")
        >>> cov.logline
        'A logline for the screenplay.'
    """
    fountain_text = generate_fountain(screenplay)
    if not fountain_text.strip():
        return ScriptCoverage(
            logline="(empty screenplay)",
            synopsis="The screenplay contains no content.",
            rating=1,
            recommendation="Pass",
            model_used=model,
        )

    # Demo mode — return placeholder coverage
    if model == "demo":
        return ScriptCoverage(
            logline="A logline for the screenplay.",
            synopsis="This is a placeholder synopsis for demo mode.",
            strengths=[
                "Strong visual storytelling.",
                "Well-structured scenes.",
                "Authentic dialogue.",
            ],
            weaknesses=[
                "Pacing could be tighter in act two.",
                "Some character motivations need clarification.",
                "The ending feels slightly rushed.",
            ],
            rating=6,
            recommendation="Consider",
            genre="Drama",
            target_audience="Adult viewers who enjoy character-driven stories.",
            model_used="demo",
        )

    messages = _build_messages(fountain_text)

    # Use the existing ModelRouter
    from cosmic_script.conversion.model_router import get_router

    router = get_router()
    # If the caller passed an explicit API key, attach it to the router for
    # this call by setting preferred_model and relying on the router's key
    # resolution — but the router uses env vars primarily.
    # We handle API key override by passing it via the router.
    if api_key:
        router.api_key = api_key

    try:
        raw_response, model_used = router.call_with_fallback(
            messages=messages,
            temperature=0.5,
            max_tokens=4096,
            preferred_model=model,
        )
    except Exception as exc:
        logger.error("Coverage LLM call failed: %s", exc)
        return ScriptCoverage(
            logline="(coverage generation failed)",
            weaknesses=[f"LLM call error: {exc}"],
            model_used=model,
        )

    return _parse_coverage_response(raw_response, model_used)
