"""Main LLM conversion logic for screenplay generation."""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import litellm

from cosmic_script.conversion.cache import ConversionCache, _build_cache_key
from cosmic_script.conversion.prompts import SYSTEM_PROMPT, build_user_prompt
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
        except (litellm.APIError, litellm.RateLimitError,
                litellm.ServiceUnavailableError, litellm.Timeout) as exc:
            last_exc = exc
            logger.warning(
                "LLM call failed (attempt %d/%d): %s", attempt, max_retries, exc
            )
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** (attempt - 1))
                time.sleep(delay)
    raise RuntimeError(
        f"LLM call failed after {max_retries} retries"
    ) from last_exc


# ---------------------------------------------------------------------------
# Fountain parser
# ---------------------------------------------------------------------------

# Regex to identify a scene heading line in Fountain format.
_SCENE_HEADING_RE = re.compile(
    r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_fountain(text: str) -> list[Scene]:
    """Split LLM Fountain output into individual :class:`Scene` objects.

    Scenes are delimited by lines that match a valid scene heading
    (``INT.``, ``EXT.``, ``INT/EXT.``, ``I/E.``).

    Args:
        text: Raw Fountain-formatted text returned by the LLM.

    Returns:
        A list of :class:`Scene` instances.
    """
    matches = list(_SCENE_HEADING_RE.finditer(text))
    if not matches:
        # No scene headings found - treat the entire output as a single scene.
        return [Scene(heading="FADE IN:", content=text.strip())]

    scenes: list[Scene] = []
    for i, match in enumerate(matches):
        start = match.start()
        # The heading is the line containing the match.
        heading_line = text[match.start(): text.index("\n", match.start())].strip()
        # Content runs from the start of this heading (or after previous heading)
        # to the start of the next heading.
        if i + 1 < len(matches):
            content = text[match.start(): matches[i + 1].start()].strip()
        else:
            content = text[match.start():].strip()
        scenes.append(Scene(heading=heading_line, content=content))

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

        Builds a prompt from the chapter text and current character
        registry, calls the LLM (with retry), and parses the Fountain
        output into scenes.

        After a successful conversion, the registry is updated with any
        new character names found in the chapter text.

        Args:
            chapter: The chapter to convert.
            registry: The current character registry (may be mutated).

        Returns:
            A list of parsed :class:`Scene` objects.

        Raises:
            RuntimeError: If the LLM call fails after all retries.
        """
        registry_context = registry.to_prompt_context()
        system_msg = SYSTEM_PROMPT.format(character_registry=registry_context)
        user_msg = build_user_prompt(
            chapter_number=chapter.number,
            chapter_text=chapter.text,
            genre=self.config.genre,
        )

        # Demo mode: return mock output without LLM call
        if self.config.model == "demo":
            raw_output = self._demo_output(chapter)
        else:
            # Build cache key and check cache
            cache_key = _build_cache_key(
                chapter_text=chapter.text,
                model=self.config.model,
                temperature=self.config.temperature,
                system_prompt=system_msg,
            )

            cached = self._cache.get(cache_key)
            if cached is not None:
                raw_output = cached
                logger.info(
                    "Chapter %d: cache hit, skipping LLM call",
                    chapter.number,
                )
            else:
                def _call() -> str:
                    if self.config.model == "auto":
                        from cosmic_script.conversion.model_router import get_router
                        router = get_router()
                        content, _model_used = router.call_with_fallback(
                            messages=[
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_msg},
                            ],
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                        )
                        return content
                    else:
                        response = litellm.completion(
                            model=self.config.model,
                            api_key=self.config.api_key,
                            messages=[
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_msg},
                            ],
                            temperature=self.config.temperature,
                            max_tokens=self.config.max_tokens,
                        )
                        content: str = response.choices[0].message.content or ""
                        return content

                raw_output = _retry_with_backoff(
                    _call,
                    max_retries=self.config.max_retries,
                )

                # Cache the response
                self._cache.set(cache_key, raw_output, self.config.model)

        # Self-healing: validate and retry if errors found (skip in demo mode)
        validator = FountainValidator()
        validation = validator.validate(raw_output)
        if not validation["valid"] and self.config.max_retries > 0 and self.config.model != "demo":
            error_summary = "\n".join(
                f"- {e['code']}: {e['message']}" for e in validation["errors"][:5]
            )
            logger.warning(
                "Self-healing: %d errors found in chapter %d, retrying with error context",
                len(validation["errors"]),
                chapter.number,
            )

            # Build enhanced prompt with error context
            heal_system_msg = system_msg + (
                "\n\n## Previous Attempt Had Errors\n\n"
                "The following errors were found in your previous Fountain output:\n"
                f"{error_summary}\n\n"
                "Fix these errors and output ONLY valid Fountain 1.1 text."
            )

            def _heal_call() -> str:
                response = litellm.completion(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    messages=[
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
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                content: str = response.choices[0].message.content or ""
                return content

            try:
                healed_output = _retry_with_backoff(
                    _heal_call,
                    max_retries=self.config.max_retries,
                )
                # Validate the healed output
                healed_validation = validator.validate(healed_output)
                if healed_validation["valid"] or (
                    len(healed_validation["errors"])
                    < len(validation["errors"])
                ):
                    logger.info(
                        "Self-heal succeeded for chapter %d: %d -> %d errors",
                        chapter.number,
                        len(validation["errors"]),
                        len(healed_validation["errors"]),
                    )
                    raw_output = healed_output
                else:
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

        scenes = _parse_fountain(raw_output)

        # Update character registry from the original chapter text.
        registry.update_from_text(
            chapter_text=chapter.text,
            chapter_number=chapter.number,
        )

        logger.info(
            "Chapter %d: %d scenes, %d characters in registry",
            chapter.number,
            len(scenes),
            len(registry.characters),
        )

        return scenes

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
    ) -> Screenplay:
        """Convert a list of chapters into a complete :class:`Screenplay`.

        Processes chapters sequentially, maintaining character state
        across the entire novel.  The first chapter initializes the
        character registry; subsequent chapters build on it.

        Args:
            chapters: Ordered list of chapters to convert.
            title: Screenplay title (default ``"Untitled"``).
            author: Screenplay author (default ``"Unknown"``).

        Returns:
            A :class:`Screenplay` containing all converted scenes.
        """
        if not chapters:
            return Screenplay(title=title, author=author)

        registry = CharacterRegistry()
        all_scenes: list[Scene] = []

        for chapter in chapters:
            scenes = self.convert_chapter(chapter, registry)
            all_scenes.extend(scenes)

        return Screenplay(
            title=title,
            author=author,
            scenes=all_scenes,
        )

    def clear_cache(self) -> None:
        """Clear the LLM response cache."""
        self._cache.clear()