"""Main LLM conversion logic for screenplay generation.

Implements a two-pass approach inspired by the R² framework:
1. Pass 1: Chain-of-Thought outline generation (scene analysis)
2. Pass 2: Screenplay conversion guided by the outline

Also includes quality scoring and hallucination detection.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import litellm
from screenplay_tools.fountain.parser import Parser as FountainParser
from screenplay_tools.fountain.parser import (
    ElementType as StElementType,
    SceneHeading as StSceneHeading,
)

from cosmic_script.conversion.cache import ConversionCache, _build_cache_key
from cosmic_script.conversion.prompts import (
    SYSTEM_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
    QUALITY_EVAL_PROMPT,
    build_user_prompt,
)
from cosmic_script.conversion.postprocess import postprocess_fountain, postprocess_scenes
from cosmic_script.conversion.quality import analyze_quality, QualityReport
from cosmic_script.conversion.registry import CharacterRegistry
from cosmic_script.export.validator import FountainValidator
from cosmic_script.models import Chapter, Scene, Screenplay

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
) -> str:
    """Call *fn* with exponential-backoff retry logic.

    Args:
        fn: A zero-argument callable that returns the LLM response text.
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Initial delay in seconds (default 2.0).
        backoff_factor: Multiplier for each subsequent delay (default 2.0).

    Returns:
        The response text from the successful call.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except (
            litellm.APIError,
            litellm.RateLimitError,
            litellm.ServiceUnavailableError,
            litellm.Timeout,
        ) as exc:
            last_exc = exc
            logger.warning("LLM call failed (attempt %d/%d): %s", attempt, max_retries, exc)
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** (attempt - 1))
                time.sleep(delay)
    raise RuntimeError(f"LLM call failed after {max_retries} retries") from last_exc


# ---------------------------------------------------------------------------
# Fountain parser (uses screenplay-tools for spec-compliant parsing)
# ---------------------------------------------------------------------------


def _parse_fountain(text: str) -> list[Scene]:
    """Split LLM Fountain output into individual :class:`Scene` objects.

    Uses ``screenplay-tools`` for spec-compliant Fountain parsing, then
    groups elements into scenes by scene-heading boundaries.

    Args:
        text: Raw Fountain-formatted text returned by the LLM.

    Returns:
        A list of :class:`Scene` instances.
    """
    try:
        parser = FountainParser()
        parser.add_text(text)
        script = parser.script
    except Exception:
        logger.warning("screenplay-tools parser failed — treating entire output as single scene")
        return [Scene(heading="FADE IN:", content=text.strip())]

    if not script or not script.elements:
        logger.warning(
            "No elements parsed from LLM output — treating entire output as single scene"
        )
        return [Scene(heading="FADE IN:", content=text.strip())]

    # Group elements into scenes by scene-heading boundaries
    scenes: list[Scene] = []
    current_heading = "FADE IN:"
    current_lines: list[str] = []

    for element in script.elements:
        if isinstance(element, StSceneHeading):
            # Save previous scene (if it has content)
            if current_lines:
                scenes.append(
                    Scene(
                        heading=current_heading,
                        content="\n".join(current_lines).strip(),
                    )
                )
            current_heading = element._text
            current_lines = [element._text]
        else:
            # Extract text — Character uses .name, others use ._text
            if hasattr(element, "name") and not isinstance(element, StSceneHeading):
                el_text = element.name
                if hasattr(element, "extension") and element.extension:
                    el_text += f" ({element.extension})"
            else:
                el_text = getattr(element, "_text", "")
            if el_text:
                current_lines.append(el_text)

    # Don't forget the last scene
    if current_lines:
        scenes.append(
            Scene(
                heading=current_heading,
                content="\n".join(current_lines).strip(),
            )
        )

    if not scenes:
        logger.warning(
            "No scene headings found in parsed output — treating entire output as single scene"
        )
        return [Scene(heading="FADE IN:", content=text.strip())]

    return scenes


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


@dataclass
class ConversionConfig:
    """Configuration for the LLM conversion process."""

    model: str = "auto"
    """LLM model identifier. ``"auto"`` uses ModelRouter's fallback chain.
    ``"demo"`` returns mock output. Any other value is passed directly
    to litellm."""

    api_key: Optional[str] = None
    """API key for the LLM provider.  Falls back to environment variable."""

    max_retries: int = 3
    """Number of retry attempts for transient API failures."""

    temperature: float = 0.3
    """LLM sampling temperature (lower = more deterministic)."""

    max_tokens: int = 8192
    """Maximum tokens in the LLM response."""

    no_cache: bool = False
    """If True, bypass the content-hash cache."""

    cache_ttl: int = 86400
    """Cache entry TTL in seconds (default 86400 = 24 h)."""

    genre: Optional[str] = None
    """Genre preset key (e.g. ``"action"``, ``"noir"``). Passed to the
    prompt builder for genre-specific formatting guidance. ``None``
    defaults to the ``"classic"`` preset."""


class ScreenplayConverter:
    """Orchestrates the conversion of novel chapters into a screenplay.

    Usage::

        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters)
    """

    def __init__(self, config: ConversionConfig) -> None:
        self.config = config
        self._cache = ConversionCache(
            enabled=not config.no_cache,
            ttl_seconds=config.cache_ttl,
        )

    # ------------------------------------------------------------------
    # Single-chapter conversion
    # ------------------------------------------------------------------

    def convert_chapter(
        self,
        chapter: Chapter,
        registry: CharacterRegistry,
    ) -> list[Scene]:
        """Convert one chapter into a list of :class:`Scene` objects.

        Implements a two-pass approach inspired by the R² framework:
        1. Pass 1: Generate scene outline (Chain-of-Thought analysis)
        2. Pass 2: Convert outline to Fountain markup
        3. Pass 3: Quality evaluation and hallucination detection

        Args:
            chapter: The chapter to convert.
            registry: The current character registry.

        Returns:
            A list of parsed :class:`Scene` objects.

        Raises:
            RuntimeError: If the LLM call fails after all retries.

        Side effects:
            MUTATES ``registry`` — updates it with characters found in the
            chapter text. This is intentional: the registry accumulates
            characters across the entire novel.
        """
        # ── Pass 1: Generate outline ──────────────────────────────────
        outline = None
        if self.config.model != "demo":
            outline = self._generate_outline(chapter, registry)

        # ── Pass 2: Convert to screenplay ─────────────────────────────
        registry_context = registry.to_prompt_context()
        system_msg = SYSTEM_PROMPT.format(character_registry=registry_context)

        # Enhance user prompt with outline context if available
        user_msg = build_user_prompt(
            chapter_number=chapter.number,
            chapter_text=chapter.text,
            genre=self.config.genre,
        )

        if outline:
            # Add outline to user prompt for better guidance
            outline_text = self._format_outline_for_prompt(outline)
            user_msg = f"{user_msg}\n\n## Scene Outline (use as guide):\n{outline_text}"

        # Guard: demo mode returns mock output without LLM call
        if self.config.model == "demo":
            raw_output = self._demo_output(chapter)
        else:
            raw_output = self._get_cached_or_llm_output(chapter, system_msg, user_msg)

        # Guard: self-healing retries with error context
        raw_output = self._self_heal_if_needed(chapter, raw_output, system_msg, user_msg)

        # ── Post-processing (deterministic fixes) ──────────────────────
        raw_output = postprocess_fountain(raw_output)

        # ── Hallucination detection ───────────────────────────────────
        hallucination_warnings = self._check_character_consistency(raw_output, registry)
        if hallucination_warnings:
            for warning in hallucination_warnings:
                logger.warning("Chapter %d: %s", chapter.number, warning)

        # ── Parse into scenes ─────────────────────────────────────────
        scenes = _parse_fountain(raw_output)

        # ── Scene-level post-processing ───────────────────────────────
        scene_dicts = [{"heading": s.heading, "content": s.content} for s in scenes]
        scene_dicts = postprocess_scenes(scene_dicts)
        scenes = [Scene(heading=s["heading"], content=s["content"]) for s in scene_dicts]

        # ── Algorithmic quality analysis (no LLM) ─────────────────────
        quality_report = analyze_quality(
            text=raw_output,
            scenes=scene_dicts,
            registry_characters=registry.characters,
        )

        if quality_report.warnings:
            for warning in quality_report.warnings[:3]:  # Limit to top 3
                logger.warning("Chapter %d quality: %s", chapter.number, warning)

        logger.info(
            "Chapter %d: %d scenes, %d chars, quality=%.1f/10",
            chapter.number,
            len(scenes),
            len(registry.characters),
            quality_report.overall_score,
        )

        # ── LLM quality evaluation (optional, skip if rate-limited) ───
        # Only run LLM evaluation if we have a working model and
        # the algorithmic score is borderline (6-8 range)
        if self.config.model != "demo" and 6.0 <= quality_report.overall_score <= 8.0:
            try:
                evaluation = self._evaluate_quality(chapter, raw_output, registry)
                if evaluation.get("overall", 0) < 6.0:
                    logger.warning(
                        "Chapter %d LLM quality score %.1f/10 — consider re-converting",
                        chapter.number,
                        evaluation["overall"],
                    )
            except Exception as e:
                # Don't fail conversion if LLM evaluation fails
                logger.warning(
                    "Chapter %d: LLM evaluation skipped (%s)",
                    chapter.number,
                    type(e).__name__,
                )

        # MUTATES: registry is updated with characters found in this chapter
        registry.update_from_text(
            chapter_text=chapter.text,
            chapter_number=chapter.number,
        )

        return scenes

    def _format_outline_for_prompt(self, outline: dict) -> str:
        """Format an outline dictionary for inclusion in the user prompt.

        Args:
            outline: The outline dictionary from _generate_outline().

        Returns:
            A formatted string describing the scene breakdown.
        """
        parts = []
        parts.append(f"Genre: {outline.get('genre', 'unknown')}")
        parts.append(f"Tone: {outline.get('tone', 'neutral')}")

        scenes = outline.get("scenes", [])
        if scenes:
            parts.append(f"\nScenes ({len(scenes)} total):")
            for i, scene in enumerate(scenes, 1):
                location = scene.get("location", "UNKNOWN LOCATION")
                characters = ", ".join(scene.get("characters", []))
                purpose = scene.get("purpose", "")
                beats = "; ".join(scene.get("beats", []))

                parts.append(f"  {i}. {location}")
                if characters:
                    parts.append(f"     Characters: {characters}")
                parts.append(f"     Purpose: {purpose}")
                if beats:
                    parts.append(f"     Beats: {beats}")

        notes = outline.get("character_notes", "")
        if notes:
            parts.append(f"\nCharacter notes: {notes}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Pass 1: Outline generation (Chain-of-Thought)
    # ------------------------------------------------------------------

    def _generate_outline(
        self,
        chapter: Chapter,
        registry: CharacterRegistry,
    ) -> dict:
        """Generate a structured scene outline for the chapter.

        This is Pass 1 of the two-pass approach. The outline guides
        the screenplay conversion by analyzing genre, tone, and scene
        structure before writing any Fountain markup.

        Args:
            chapter: The chapter to analyze.
            registry: The current character registry.

        Returns:
            A dictionary with genre, tone, scenes, and character_notes.
        """
        registry_context = registry.to_prompt_context()
        system_msg = OUTLINE_SYSTEM_PROMPT.format(character_registry=registry_context)
        user_msg = build_user_prompt(
            chapter_number=chapter.number,
            chapter_text=chapter.text,
            genre=self.config.genre,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        try:
            raw_output = _retry_with_backoff(
                lambda: self._llm_completion(messages),
                max_retries=self.config.max_retries,
            )

            # Parse JSON response
            # Try to extract JSON from response (may have markdown code blocks)
            json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
            if json_match:
                outline = json.loads(json_match.group(1))
            else:
                outline = json.loads(raw_output)

            logger.info(
                "Chapter %d outline: %d scenes, genre=%s",
                chapter.number,
                len(outline.get("scenes", [])),
                outline.get("genre", "unknown"),
            )
            return outline

        except (json.JSONDecodeError, RuntimeError) as e:
            logger.warning(
                "Outline generation failed for chapter %d: %s — falling back to simple outline",
                chapter.number,
                e,
            )
            return self._simple_outline(chapter)

    def _simple_outline(self, chapter: Chapter) -> dict:
        """Create a simple outline when LLM outline generation fails.

        Args:
            chapter: The chapter to create a basic outline for.

        Returns:
            A minimal outline dictionary.
        """
        # Simple heuristic: split by paragraphs and assume each is a scene
        paragraphs = [p.strip() for p in chapter.text.split("\n\n") if p.strip()]
        scenes = []
        for i, para in enumerate(paragraphs[:5]):  # Max 5 scenes
            scenes.append(
                {
                    "location": f"INT. LOCATION - {'DAY' if i % 2 == 0 else 'NIGHT'}",
                    "characters": [],
                    "purpose": "advances plot",
                    "beats": [para[:100] + "..." if len(para) > 100 else para],
                }
            )

        return {
            "genre": "drama",
            "tone": "neutral",
            "scenes": scenes,
            "character_notes": "",
        }

    # ------------------------------------------------------------------
    # Quality scoring (Pass 3: Evaluation)
    # ------------------------------------------------------------------

    def _evaluate_quality(
        self,
        chapter: Chapter,
        screenplay_text: str,
        registry: CharacterRegistry,
    ) -> dict:
        """Evaluate the quality of the converted screenplay.

        Scores on 6 dimensions: format, characters, structure, visual,
        dialogue, and coherence.

        Args:
            chapter: The original chapter.
            screenplay_text: The generated Fountain text.
            registry: The current character registry.

        Returns:
            A dictionary with scores, strengths, weaknesses, suggestions.
        """
        if self.config.model == "demo":
            return {
                "scores": {
                    "format": 8,
                    "characters": 8,
                    "structure": 8,
                    "visual": 8,
                    "dialogue": 8,
                    "coherence": 8,
                },
                "overall": 8.0,
                "strengths": ["Demo mode — no evaluation"],
                "weaknesses": [],
                "suggestions": [],
            }

        registry_context = registry.to_prompt_context()
        system_msg = "You are a professional screenplay evaluator."
        user_msg = QUALITY_EVAL_PROMPT.format(
            novel_text=chapter.text[:2000],  # Limit to avoid token overflow
            screenplay_text=screenplay_text[:2000],
            character_registry=registry_context,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        try:
            raw_output = _retry_with_backoff(
                lambda: self._llm_completion(messages),
                max_retries=1,  # Don't retry evaluation too many times
            )

            # Parse JSON
            json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
            if json_match:
                evaluation = json.loads(json_match.group(1))
            else:
                evaluation = json.loads(raw_output)

            logger.info(
                "Chapter %d quality: %.1f/10",
                chapter.number,
                evaluation.get("overall", 0),
            )
            return evaluation

        except (json.JSONDecodeError, RuntimeError) as e:
            logger.warning(
                "Quality evaluation failed for chapter %d: %s",
                chapter.number,
                e,
            )
            return {
                "scores": {
                    "format": 7,
                    "characters": 7,
                    "structure": 7,
                    "visual": 7,
                    "dialogue": 7,
                    "coherence": 7,
                },
                "overall": 7.0,
                "strengths": ["Evaluation unavailable"],
                "weaknesses": [],
                "suggestions": [],
            }

    # ------------------------------------------------------------------
    # Hallucination detection
    # ------------------------------------------------------------------

    def _check_character_consistency(
        self,
        screenplay_text: str,
        registry: CharacterRegistry,
    ) -> list[str]:
        """Check for character consistency issues in the screenplay.

        Detects:
        - Characters in screenplay not in registry (hallucinated)
        - Characters in registry missing from screenplay (omitted)
        - Inconsistent character names

        Args:
            screenplay_text: The generated Fountain text.
            registry: The current character registry.

        Returns:
            A list of warning messages.
        """
        warnings = []
        registry_names = {name.upper() for name in registry.characters}

        # Extract character cues from screenplay (ALL CAPS lines before dialogue)
        character_pattern = re.compile(r"^([A-Z][A-Z\s]+?)(?:\s*\(|$)", re.MULTILINE)
        screenplay_chars = set()
        for match in character_pattern.finditer(screenplay_text):
            name = match.group(1).strip()
            if len(name) >= 2 and name not in {"INT", "EXT", "FADE", "CUT", "DISSOLVE"}:
                screenplay_chars.add(name)

        # Check for hallucinated characters
        hallucinated = screenplay_chars - registry_names
        if hallucinated:
            warnings.append(
                f"Characters in screenplay not in registry (possible hallucination): "
                f"{', '.join(sorted(hallucinated))}"
            )

        # Check for omitted characters (only if they should be present)
        # This is a heuristic — we only warn if the registry has characters
        # but none appear in the screenplay
        if registry_names and not screenplay_chars.intersection(registry_names):
            warnings.append(
                f"No registry characters found in screenplay. "
                f"Registry has: {', '.join(sorted(registry_names)[:5])}"
            )

        return warnings

    # ------------------------------------------------------------------
    # LLM call helpers (extracted from convert_chapter for clarity)
    # ------------------------------------------------------------------

    def _get_cached_or_llm_output(
        self,
        chapter: Chapter,
        system_msg: str,
        user_msg: str,
    ) -> str:
        """Return cached LLM output or make a fresh LLM call.

        Checks the content-hash cache first. On miss, calls the LLM
        (via ModelRouter when model="auto", or directly otherwise),
        then stores the result in cache.
        """
        cache_key = _build_cache_key(
            chapter_text=chapter.text,
            model=self.config.model,
            temperature=self.config.temperature,
            system_prompt=system_msg,
        )

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(
                "Chapter %d: cache hit, skipping LLM call",
                chapter.number,
            )
            return cached

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        raw_output = _retry_with_backoff(
            lambda: self._llm_completion(messages),
            max_retries=self.config.max_retries,
        )

        self._cache.set(cache_key, raw_output, self.config.model)
        return raw_output

    def _llm_completion(self, messages: list[dict]) -> str:
        """Make a single LLM completion call.

        Routes through ModelRouter when ``self.config.model == "auto"``,
        otherwise calls litellm directly with the specified model.
        """
        if self.config.model == "auto":
            from cosmic_script.conversion.model_router import get_router

            router = get_router()
            content, _model_used = router.call_with_fallback(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            return content

        response = litellm.completion(
            model=self.config.model,
            api_key=self.config.api_key,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def _self_heal_if_needed(
        self,
        chapter: Chapter,
        raw_output: str,
        system_msg: str,
        user_msg: str,
    ) -> str:
        """Validate output and retry with error context if errors found.

        If the initial LLM output contains validation errors, appends
        the error details to the system prompt and re-runs the LLM call.
        Keeps whichever output (original or healed) has fewer errors.
        Skipped in demo mode or when max_retries == 0.
        """
        if self.config.max_retries <= 0 or self.config.model == "demo":
            return raw_output

        validator = FountainValidator()
        validation = validator.validate(raw_output)
        if validation["valid"]:
            return raw_output

        error_summary = "\n".join(
            f"- {e['code']}: {e['message']}" for e in validation["errors"][:5]
        )
        logger.warning(
            "Self-healing: %d errors found in chapter %d, retrying with error context",
            len(validation["errors"]),
            chapter.number,
        )

        heal_system_msg = system_msg + (
            "\n\n## Previous Attempt Had Errors\n\n"
            "The following errors were found in your previous Fountain output:\n"
            f"{error_summary}\n\n"
            "Fix these errors and output ONLY valid Fountain 1.1 text."
        )
        heal_messages = [
            {"role": "system", "content": heal_system_msg},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": raw_output},
            {
                "role": "user",
                "content": (
                    "Fix the following errors in your Fountain output:\n"
                    f"{error_summary}\n\n"
                    "Output ONLY valid Fountain 1.1 text."
                ),
            },
        ]

        try:
            healed_output = _retry_with_backoff(
                lambda: self._llm_completion(heal_messages),
                max_retries=self.config.max_retries,
            )
            healed_validation = validator.validate(healed_output)
            if healed_validation["valid"] or (
                len(healed_validation["errors"]) < len(validation["errors"])
            ):
                logger.info(
                    "Self-heal succeeded for chapter %d: %d -> %d errors",
                    chapter.number,
                    len(validation["errors"]),
                    len(healed_validation["errors"]),
                )
                return healed_output
            logger.warning(
                "Self-heal did not improve output for chapter %d, "
                "keeping original (%d vs %d errors)",
                chapter.number,
                len(validation["errors"]),
                len(healed_validation["errors"]),
            )
        except RuntimeError:
            logger.warning(
                "Self-heal LLM call failed for chapter %d, keeping original output",
                chapter.number,
            )

        return raw_output

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    def _demo_output(self, chapter: Chapter) -> str:
        """Generate mock Fountain output for demo/testing.

        Produces a simple, valid Fountain screenplay from the chapter text
        without making any LLM API calls.

        Args:
            chapter: The chapter to create mock output for.

        Returns:
            A valid Fountain-formatted string.
        """
        # Take first ~500 chars of chapter text as action
        preview = chapter.text[:500].strip()
        if len(chapter.text) > 500:
            preview += "..."

        return f"""FADE IN:

INT. SCENE - DAY

{preview}

FADE OUT."""

    # ------------------------------------------------------------------
    # Multi-chapter (full novel) conversion
    # ------------------------------------------------------------------

    def convert_novel(
        self,
        chapters: list[Chapter],
        title: str = "Untitled",
        author: str = "Unknown",
        progress_callback: callable = None,
    ) -> Screenplay:
        """Convert a list of chapters into a complete :class:`Screenplay`.

        Processes chapters sequentially, maintaining character state
        across the entire novel.  The first chapter initializes the
        character registry; subsequent chapters build on it.

        Args:
            chapters: Ordered list of chapters to convert.
            title: Screenplay title (default ``"Untitled"``).
            author: Screenplay author (default ``"Unknown"``).
            progress_callback: Optional callback invoked with
                (event_type, chapter_num, total_chapters, message)
                for progress reporting.

        Returns:
            A :class:`Screenplay` containing all converted scenes.
        """
        if not chapters:
            return Screenplay(title=title, author=author)

        registry = CharacterRegistry()
        all_scenes: list[Scene] = []
        total = len(chapters)

        for i, chapter in enumerate(chapters):
            if progress_callback:
                progress_callback(
                    "chapter_start", i + 1, total, f"Converting chapter {i + 1}/{total}"
                )
            scenes = self.convert_chapter(chapter, registry)
            if progress_callback:
                progress_callback("chapter_complete", i + 1, total, f"Chapter {i + 1} complete")
            all_scenes.extend(scenes)

        if progress_callback:
            progress_callback("conversion_complete", total, total, "All chapters converted")

        return Screenplay(
            title=title,
            author=author,
            scenes=all_scenes,
        )

    def clear_cache(self) -> None:
        """Clear the LLM response cache."""
        self._cache.clear()
