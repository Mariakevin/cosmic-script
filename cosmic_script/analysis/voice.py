"""Character voice analysis for screenplays.

Analyzes character dialogue patterns to produce per-character metrics:
  - Total dialogue lines
  - Average line length (words per line)
  - Vocabulary richness (type-token ratio)
  - Most common words (excluding stop words)
  - Speaking style classification
  - Emotional tone classification (lexicon + textblob sentiment)

Pure text analysis — no LLM calls required.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from cosmic_script.models import Screenplay, Scene, ScreenplayElement

# ---------------------------------------------------------------------------
# Stop words (common English words excluded from vocabulary analysis)
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    "i", "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "is", "it", "be", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "this", "that", "these", "those",
    "am", "are", "was", "were", "been", "being", "have", "has", "had",
    "do", "does", "did", "doing", "will", "would", "can", "could",
    "shall", "should", "may", "might", "must", "need", "dare", "ought",
    "used", "to", "not", "no", "nor", "so", "if", "then", "than",
    "too", "very", "just", "also", "up", "down", "out", "off", "over",
    "under", "again", "further", "once", "here", "there", "when",
    "where", "why", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "what", "which", "who",
    "whom", "whose", "any", "many",
})

# ---------------------------------------------------------------------------
# Emotional tone lexicons
# ---------------------------------------------------------------------------

_ANGER_WORDS: frozenset[str] = frozenset({
    "angry", "furious", "hate", "rage", "frustrated", "annoyed", "irritated",
    "mad", "livid", "outraged", "fuming", "seething", "infuriate", "infuriating",
    "anger", "hostile", "bitter", "resentful", "wrath", "fury",
})

_SADNESS_WORDS: frozenset[str] = frozenset({
    "sad", "cry", "crying", "tears", "weep", "weeping", "grief", "mourn",
    "mourning", "heartbroken", "depressed", "miserable", "lonely", "alone",
    "hurt", "pain", "sorrow", "sorry", "miss", "missing", "lost", "loss",
    "heartbreaking", "heartache", "despair",
})

_JOY_WORDS: frozenset[str] = frozenset({
    "happy", "glad", "joy", "delight", "wonderful", "beautiful", "love",
    "lovely", "amazing", "great", "fantastic", "excellent", "wonder",
    "thrilled", "ecstatic", "elated", "cheerful", "smile", "laugh",
    "laughter", "celebrate", "celebration", "bliss", "radiant",
})

_ANXIETY_WORDS: frozenset[str] = frozenset({
    "anxious", "nervous", "worried", "afraid", "scared", "fear", "terrified",
    "panic", "panicking", "dread", "dreading", "uneasy", "restless",
    "tense", "stressed", "overwhelmed", "helpless", "vulnerable",
    "frightened", "fearful", "terrifying", "terrible", "horrible",
})

# Raw dialogue line pattern: character cue (possibly with extension) followed
# by one or more dialogue lines. Also matches lines that are solely a character
# cue (like after a scene heading).
_CHARACTER_CUE_RE = re.compile(r'^([A-Z][A-Z\s]+?)(?:\s*\([^)]*\))?\s*$')

# Line that starts with a parenthetical — skip these
_PARENTHETICAL_RE = re.compile(r'^\s*\(')

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CharacterVoice:
    """Voice profile for a single character in a screenplay.

    Attributes:
        name: Character name (uppercased canonical form).
        total_lines: Number of dialogue lines spoken.
        avg_line_length: Average words per dialogue line.
        vocabulary_richness: Type-token ratio (unique words / total words).
        common_words: Top 5 most used words (excluding stop words).
        speaking_style: ``"terse"``, ``"casual"``, ``"verbose"``, or ``"formal"``.
        emotional_tone: ``"neutral"``, ``"angry"``, ``"sad"``, ``"happy"``, or
            ``"anxious"``.
    """

    name: str
    total_lines: int = 0
    avg_line_length: float = 0.0
    vocabulary_richness: float = 0.0
    common_words: list[str] = field(default_factory=list)
    speaking_style: str = "neutral"
    emotional_tone: str = "neutral"


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _classify_speaking_style(avg_line_length: float) -> str:
    """Classify speaking style based on average words per line.

    Args:
        avg_line_length: Mean words per dialogue line.

    Returns:
        ``"terse"`` (<=5), ``"casual"`` (6-15), ``"verbose"`` (16-30),
        or ``"formal"`` (>30).
    """
    if avg_line_length <= 5:
        return "terse"
    elif avg_line_length <= 15:
        return "casual"
    elif avg_line_length <= 30:
        return "verbose"
    else:
        return "formal"


def _classify_emotional_tone(text: str) -> str:
    """Classify the dominant emotional tone of dialogue text.

    Uses two strategies:
      1. Lexicon-based: Count occurrences of words from each emotional lexicon.
      2. Textblob sentiment (if available): Polarity + subjectivity analysis.

    The category with the highest count wins. Ties are broken by priority:
    angry > sad > happy > anxious > neutral.

    Args:
        text: The full dialogue text for a character.

    Returns:
        One of ``"neutral"``, ``"angry"``, ``"sad"``, ``"happy"``,
        ``"anxious"``.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())

    scores = {
        "angry": sum(1 for w in words if w in _ANGER_WORDS),
        "sad": sum(1 for w in words if w in _SADNESS_WORDS),
        "happy": sum(1 for w in words if w in _JOY_WORDS),
        "anxious": sum(1 for w in words if w in _ANXIETY_WORDS),
    }

    # Priority tiebreak order
    for tone in ("angry", "sad", "happy", "anxious"):
        count = scores[tone]
        if count > 0:
            # Check if any other tone has a higher count
            others = sum(v for k, v in scores.items() if k != tone)
            if count > others or count >= 3:
                return tone

    # ── Textblob sentiment (if available) ─────────────────────────────
    try:
        from textblob import TextBlob
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # -1.0 to 1.0
        subjectivity = blob.sentiment.subjectivity  # 0.0 to 1.0

        if polarity < -0.3:
            return "sad"
        elif polarity > 0.3:
            return "happy"
        elif subjectivity > 0.6 and abs(polarity) > 0.1:
            # High subjectivity with moderate polarity suggests emotional
            return "anxious" if polarity < 0 else "happy"
    except ImportError:
        pass  # textblob not installed — skip sentiment strategy
    except Exception:
        pass  # Other errors — skip gracefully

    return "neutral"


# ---------------------------------------------------------------------------
# Dialogue extraction
# ---------------------------------------------------------------------------


def _extract_dialogue_by_character(
    screenplay: Screenplay,
) -> dict[str, list[str]]:
    """Parse the screenplay and group dialogue lines by character.

    Args:
        screenplay: The screenplay data model.

    Returns:
        A dict mapping character name (uppercased) to a list of their
        dialogue line texts.
    """
    char_dialogue: dict[str, list[str]] = {}

    def _process_lines(lines: list[str]) -> None:
        """Process raw Fountain-formatted lines for dialogue."""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line:
                continue

            # Check for character cue (UPPERCASE, 2-20 chars)
            if line.isupper() and len(line.split()[0]) <= 20:
                # Extract character name (strip parenthetical extensions)
                char_name = line.split("(")[0].strip()
                # Collect dialogue lines following this cue
                dialogue_lines: list[str] = []
                while i < len(lines):
                    dial = lines[i].strip()
                    if not dial:
                        break
                    # Check if next line is another character cue
                    if dial.isupper() and len(dial.split()[0]) <= 20:
                        break
                    # Skip parentheticals
                    if _PARENTHETICAL_RE.match(dial):
                        i += 1
                        continue
                    dialogue_lines.append(dial)
                    i += 1

                if char_name and dialogue_lines:
                    char_dialogue.setdefault(char_name, []).extend(dialogue_lines)

    # Try elements first, then scenes
    if screenplay.elements:
        current_char: Optional[str] = None
        for elem in screenplay.elements:
            if elem.element_type == "character":
                current_char = elem.text.strip().split("(")[0].strip()
            elif elem.element_type == "dialogue" and current_char:
                char_dialogue.setdefault(current_char, []).append(elem.text.strip())
            elif elem.element_type == "parenthetical":
                pass  # skip
            else:
                current_char = None

    if screenplay.scenes and not char_dialogue:
        for scene in screenplay.scenes:
            scene_lines = scene.content.split("\n")
            _process_lines(scene_lines)

    return char_dialogue


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_voices(screenplay: Screenplay) -> list[CharacterVoice]:
    """Analyze character dialogue patterns in a screenplay.

    Produces a per-character voice profile with metrics derived purely from
    the text (no LLM required).  Characters are sorted by total_lines
    (most talkative first).

    Args:
        screenplay: The screenplay data model to analyse.

    Returns:
        A list of :class:`CharacterVoice` objects, one per character with
        dialogue. Returns an empty list if the screenplay has no dialogue.

    Example:
        >>> from cosmic_script.models import Screenplay, Scene
        >>> sp = Screenplay(scenes=[
        ...     Scene(heading="INT. ROOM - DAY",
        ...           content="JOHN\\nHello there.\\n\\nSARAH\\nHi!"),
        ... ])
        >>> voices = analyze_voices(sp)
        >>> len(voices)
        2
        >>> voices[0].name
        'JOHN'
    """
    # Return early for empty screenplay
    has_content = bool(screenplay.elements or screenplay.scenes)
    if not has_content:
        return []

    char_dialogue = _extract_dialogue_by_character(screenplay)
    if not char_dialogue:
        return []

    results: list[CharacterVoice] = []

    for char_name, lines in char_dialogue.items():
        if not lines:
            continue

        total_lines = len(lines)
        all_text = " ".join(lines)
        all_words = re.findall(r"[a-zA-Z']+", all_text)

        total_words = len(all_words)
        avg_line_length = total_words / total_lines if total_lines > 0 else 0.0

        # Vocabulary richness (type-token ratio)
        unique_words = len(set(w.lower() for w in all_words))
        vocabulary_richness = unique_words / total_words if total_words > 0 else 0.0

        # Most common words (excluding stop words)
        word_counts: Counter = Counter()
        for w in all_words:
            wl = w.lower()
            if wl not in _STOP_WORDS and len(wl) > 1:
                word_counts[wl] += 1
        common_words = [w for w, _ in word_counts.most_common(5)]

        # Style and tone
        speaking_style = _classify_speaking_style(avg_line_length)
        emotional_tone = _classify_emotional_tone(all_text)

        results.append(CharacterVoice(
            name=char_name,
            total_lines=total_lines,
            avg_line_length=round(avg_line_length, 1),
            vocabulary_richness=round(vocabulary_richness, 3),
            common_words=common_words,
            speaking_style=speaking_style,
            emotional_tone=emotional_tone,
        ))

    # Sort by total_lines descending (most talkative first)
    results.sort(key=lambda v: v.total_lines, reverse=True)
    return results
