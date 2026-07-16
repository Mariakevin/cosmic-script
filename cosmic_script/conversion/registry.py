"""Character state management for screenplay conversion."""

import re
from typing import Optional

from pydantic import BaseModel, Field
from rapidfuzz import fuzz


class Character(BaseModel):
    """Represents a character extracted from novel text."""

    canonical_name: str
    """The primary/standardized name used in all prompts."""

    aliases: set[str] = Field(default_factory=set)
    """Alternative names or spellings for this character."""

    first_appearance: int = 0
    """Chapter number where this character first appeared."""


class CharacterRegistry:
    """Maintains character state across chapters during conversion.

    Tracks character names, aliases, and first-appearance chapters.
    Uses RapidFuzz to normalize similar names (e.g. "Jon" vs "John").
    Uses multiple strategies to detect character names:
      - ALL-CAPS words (existing)
      - Dialogue tag patterns ('said Sarah', 'Sarah replied')
      - Capitalised name + action verb at line start ('Sarah walked')
    """

    # Words that appear all-caps in text but are not character names.
    _SKIP_WORDS: frozenset[str] = frozenset({
        "I", "A", "AN", "THE", "AND", "OR", "BUT", "NOT", "IN", "ON",
        "AT", "TO", "FOR", "OF", "WITH", "BY", "FROM", "AS", "IS", "IT",
        "BE", "HE", "SHE", "WE", "THEY", "ME", "HIM", "HER", "US", "THEM",
        "YES", "NO", "OK", "OH", "AH", "WELL", "SO", "IF", "THEN", "ELSE",
        "WHEN", "WHERE", "WHAT", "WHY", "HOW", "ALSO", "JUST", "VERY",
        "ALL", "ANY", "MORE", "MOST", "SOME", "THAT", "THIS", "THESE",
        "THOSE", "HAS", "HAD", "HAVE", "DO", "DOES", "DID", "WAS", "WERE",
        "ARE", "CAN", "COULD", "WILL", "WOULD", "SHALL", "SHOULD", "MAY",
        "MIGHT", "MUST", "CHAPTER", "INT", "EXT", "DAY", "NIGHT",
    })
    """Common uppercase words that should not be treated as character names."""

    # Words that appear at the start of a sentence but are never character names.
    # Used by the NAME_ACTION pattern to filter false positives.
    # Stored uppercase for case-insensitive matching with name.upper().
    _NAME_SKIP_WORDS: frozenset[str] = frozenset({
        "WHEN", "WHAT", "WHY", "WHERE", "WHO", "WHOM", "WHICH",
        "THIS", "THAT", "THESE", "THOSE", "THERE", "HERE",
        "CHAPTER", "PART", "SCENE", "SECTION", "ACT",
        "HOWEVER", "THEREFORE", "MEANWHILE", "SUDDENLY", "EVENTUALLY",
        "FINALLY", "AFTERWARD", "AFTER", "BEFORE", "ALTHOUGH",
        "BECAUSE", "SINCE", "THOUGH", "WHILE", "UNLESS", "UNTIL",
        "DESPITE", "BESIDES", "FURTHERMORE", "MOREOVER", "NEVERTHELESS",
        "INDEED", "PERHAPS", "PROBABLY", "CERTAINLY", "TODAY",
        "TOMORROW", "YESTERDAY", "INSIDE", "OUTSIDE", "BEHIND",
        "BETWEEN", "ACROSS", "AROUND", "DOWN", "UP", "OVER", "UNDER",
        "THROUGH", "ONE", "TWO", "SOME", "MANY", "SEVERAL", "EACH",
        "EVERY", "BOTH", "SUCH", "ONLY", "JUST", "EVEN", "STILL",
        "ALREADY", "ALMOST", "PLEASE", "HELLO", "WELCOME",
    })
    """Capitalised words at line start that should not be treated as names."""

    # ── Detection patterns (Strategy 1) ────────────────────────────────
    # Dialogue tag: "dialogue" said Name   or   Name said, "dialogue"
    # NOTE: No re.IGNORECASE — character classes would become case-insensitive.
    # Dialogue verbs are listed in lowercase (typical novel prose).
    # ALL-CAPS dialogue tags are caught by Strategy 3.
    _DIALOGUE_TAG_AFTER = re.compile(
        r'(?:said|asked|replied|answered|called|shouted|whispered|'
        r'yelled|exclaimed|muttered|cried|laughed|smiled|nodded|shook|'
        r'added|continued|began|started|finished|ended|finished|'
        r'whisper|scream|yell|shout|answer|reply|call|mutter|cry|'
        r'laugh|smile|nod)\s+'
        r'([A-Z][a-z]+)',
    )

    _DIALOGUE_TAG_BEFORE = re.compile(
        r'([A-Z][a-z]+)\s+'
        r'(?:said|asked|replied|answered|called|shouted|whispered|'
        r'yelled|exclaimed|muttered|cried|laughed|smiled|nodded|shook|'
        r'added|continued|began|started|finished|ended|finished|'
        r'whisper|scream|yell|shout|answer|reply|call|mutter|cry|'
        r'laugh|smile|nod)',
    )

    # ── Detection patterns (Strategy 2) ────────────────────────────────
    # Capitalised name + action verb at line start: "Sarah walked ..."
    _NAME_ACTION = re.compile(
        r'^([A-Z][a-z]+)\s+'
        r'(?:walked|ran|stood|sat|looked|turned|smiled|frowned|'
        r'nodded|shook|laughed|cried|whispered|shouted|said|asked|'
        r'replied|answered|called|entered|left|stepped|jumped|'
        r'grabbed|pushed|pulled|opened|closed|placed|set|put|'
        r'glanced|stared|watched|observed|noticed|saw|heard|'
        r'felt|touched|reached|moved|walk|run|stand|sit|look|turn)',
        re.MULTILINE,
    )

    # ── Detection patterns (Strategy 3: existing ALL-CAPS) ────────────
    _ALL_CAPS = re.compile(r"\b([A-Z][A-Z]{2,})\b")

    def __init__(self) -> None:
        self._characters: dict[str, Character] = {}

    @property
    def characters(self) -> dict[str, Character]:
        """Read-only view of the character registry."""
        return dict(self._characters)

    def normalize_name(self, name: str) -> Optional[str]:
        """Match *name* to an existing character using fuzzy matching.

        Args:
            name: A candidate character name to resolve.

        Returns:
            The canonical name of the closest match, or *name* itself if
            no existing character is similar enough (score >= 80).
            Returns None if *name* is empty or only whitespace.
        """
        cleaned = name.strip().upper()
        if not cleaned or len(cleaned) < 2:
            return None

        best_match: Optional[str] = None
        best_score = 0

        for canonical in self._characters:
            # Check against canonical name
            score = fuzz.ratio(cleaned, canonical.upper())
            if score > best_score:
                best_score = score
                best_match = canonical

            # Check against each alias
            for alias in self._characters[canonical].aliases:
                alias_score = fuzz.ratio(cleaned, alias.upper())
                if alias_score > best_score:
                    best_score = alias_score
                    best_match = canonical

        if best_score >= 80 and best_match is not None:
            return best_match
        return cleaned

    # ── Internal helpers ──────────────────────────────────────────────

    def _add_name(self, word: str, seen: set[str], chapter_number: int) -> None:
        """Register a detected name (uppercased) into the registry.

        Args:
            word: The raw word detected (may be title case or upper case).
            seen: Set of already-processed words in this chapter.
            chapter_number: Current chapter number for first-appearance tracking.
        """
        word_upper = word.strip().upper()
        if not word_upper or len(word_upper) < 2:
            return
        if word_upper in self._SKIP_WORDS:
            return
        if word_upper in self._NAME_SKIP_WORDS:
            return
        if word_upper in seen:
            return
        seen.add(word_upper)

        resolved = self.normalize_name(word_upper)

        if resolved == word_upper:
            # New character — add with all-caps canonical name.
            if word_upper not in self._characters:
                self._characters[word_upper] = Character(
                    canonical_name=word_upper,
                    first_appearance=chapter_number,
                )
        elif resolved is not None:
            # Alias for an existing character.
            existing = self._characters[resolved]
            existing.aliases.add(word_upper)

    def update_from_text(self, chapter_text: str, chapter_number: int) -> None:
        """Scan *chapter_text* for character names and update the registry.

        Uses three strategies:
          1. Dialogue tag patterns (``"Hello," said Sarah``, ``John replied, ...``)
          2. Capitalised name + action verb at line start (``Sarah walked ...``)
          3. ALL-CAPS words (``SARAH`` in dialogue tags or emphasis)

        Skips common non-name words via ``_SKIP_WORDS`` and ``_NAME_SKIP_WORDS``.

        Args:
            chapter_text: Raw novel chapter text.
            chapter_number: The chapter number (1-based) for tracking
                first appearance.
        """
        seen_in_chapter: set[str] = set()

        # ── Strategy 1: Dialogue tags ─────────────────────────────────
        for match in self._DIALOGUE_TAG_AFTER.finditer(chapter_text):
            name = match.group(1)
            if name.upper() in self._NAME_SKIP_WORDS:
                continue
            self._add_name(name, seen_in_chapter, chapter_number)

        for match in self._DIALOGUE_TAG_BEFORE.finditer(chapter_text):
            name = match.group(1)
            if name.upper() in self._NAME_SKIP_WORDS:
                continue
            self._add_name(name, seen_in_chapter, chapter_number)

        # ── Strategy 2: Name + action verb at line start ──────────────
        for match in self._NAME_ACTION.finditer(chapter_text):
            name = match.group(1)
            if name.upper() in self._NAME_SKIP_WORDS:
                continue
            self._add_name(name, seen_in_chapter, chapter_number)

        # ── Strategy 3: ALL-CAPS words ─────────────────────────────────
        for match in self._ALL_CAPS.finditer(chapter_text):
            word = match.group(1)
            self._add_name(word, seen_in_chapter, chapter_number)

    def to_prompt_context(self) -> str:
        """Format the registry for injection into the LLM system prompt.

        Returns:
            A human-readable string listing each character, their aliases,
            and the chapter they first appeared in.
        """
        if not self._characters:
            return "No characters identified yet."

        parts: list[str] = []
        for name in sorted(self._characters.keys()):
            char = self._characters[name]
            line = f"  - {name}"
            if char.aliases:
                alias_list = ", ".join(sorted(char.aliases))
                line += f" (also: {alias_list})"
            line += f" [first appears: Chapter {char.first_appearance}]"
            parts.append(line)

        return "\n".join(parts)
