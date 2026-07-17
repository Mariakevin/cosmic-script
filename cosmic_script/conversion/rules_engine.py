"""Rule-based screenplay conversion — no LLM required.

Converts novel prose to Fountain 1.1 using NLP + deterministic algorithms.
Works offline, instant, free. Quality is lower than AI mode (full paragraphs
as action rather than condensed beats) but produces valid, structured output.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from cosmic_script.models import (
    Chapter,
    ElementType,
    Scene,
    Screenplay,
    ScreenplayElement,
)
from cosmic_script.conversion.registry import CharacterRegistry


# ── Constants ────────────────────────────────────────────────────────────────

_INT_KEYWORDS: frozenset[str] = frozenset(
    {
        "office",
        "room",
        "house",
        "apartment",
        "car",
        "building",
        "hall",
        "kitchen",
        "bedroom",
        "hospital",
        "school",
        "restaurant",
        "bar",
        "shop",
        "store",
        "library",
        "church",
        "prison",
        "cell",
        "bathroom",
        "corridor",
        "lobby",
        "den",
        "attic",
        "basement",
        "garage",
        "studio",
        "flat",
        "dorm",
        "hotel",
        "motel",
        "theater",
        "theatre",
        "cafe",
        "diner",
        "washroom",
        "closet",
        "tent",
        "spaceship",
        "cockpit",
        "bridge",
        "cabin",
        "elevator",
        "stairwell",
        "lab",
        "courtroom",
        "jury room",
        "dressing room",
        "backstage",
        "green room",
        "waiting room",
        "exam room",
        "operating room",
        "icu",
        "ward",
        "reception",
        "penthouse",
        "cottage",
        "yurt",
        "igloo",
        "bunker",
        "shelter",
        "vault",
        "archive",
        "warehouse",
        "factory",
        "plant",
        "mill",
        "foundry",
        "workshop",
        "atelier",
        "cubicle",
        "conference room",
        "boardroom",
        "break room",
        "cafeteria",
        "pantry",
        "alcove",
        "conservatory",
        "sunroom",
        "nursery",
        "playroom",
        "study",
    }
)

_EXT_KEYWORDS: frozenset[str] = frozenset(
    {
        "park",
        "street",
        "road",
        "garden",
        "forest",
        "field",
        "mountain",
        "beach",
        "river",
        "lake",
        "sky",
        "yard",
        "sidewalk",
        "rooftop",
        "courtyard",
        "alley",
        "bridge",
        "highway",
        "desert",
        "jungle",
        "swamp",
        "meadow",
        "cliff",
        "canyon",
        "valley",
        "hill",
        "pond",
        "ocean",
        "sea",
        "island",
        "shore",
        "coast",
        "campground",
        "cemetery",
        "playground",
        "parking",
        "lot",
        "driveway",
        "porch",
        "balcony",
        "terrace",
        "patio",
        "lawn",
        "plaza",
        "square",
        "intersection",
        "crosswalk",
        "tunnel",
        "underpass",
        "overpass",
        "viaduct",
        "dam",
        "pier",
        "dock",
        "harbor",
        "port",
        "marina",
        "airfield",
        "airstrip",
        "helipad",
        "launch pad",
        "train tracks",
        "railway",
        "station",
        "platform",
        "bus stop",
        "taxi stand",
        "trail",
        "path",
        "bike lane",
        "boardwalk",
        "promenade",
        "jetty",
        "breakwater",
        "seawall",
        "levee",
        "dike",
        "causeway",
        "cul-de-sac",
    }
)

_TIME_KEYWORDS: dict[str, str] = {
    "morning": "MORNING",
    "dawn": "DAWN",
    "afternoon": "AFTERNOON",
    "evening": "EVENING",
    "night": "NIGHT",
    "midnight": "MIDNIGHT",
    "dusk": "DUSK",
    "late": "NIGHT",
    "early": "MORNING",
    "noon": "AFTERNOON",
    "sunset": "DUSK",
    "sunrise": "DAWN",
}

# Scene-break signals (strong = new scene likely)
_LOCATION_SHIFT_RE = re.compile(
    r"\b(?:in the|at the|at|inside the|outside the|back at the|"
    r"arriving at|arrived at|near the|by the|on the)\s+"
    r"(office|room|house|park|street|school|hospital|bar|restaurant|"
    r"building|station|car|apartment|hotel|cafe|library|museum|"
    r"shop|store|church|prison|garden|beach|forest|river|mountain|"
    r"road|alley|rooftop|courtyard|lobby|kitchen|bedroom|bathroom|"
    r"garage|attic|basement|den|hall|corridor|patio|balcony|porch|"
    r"backyard|frontyard|yard|playground|cemetery|campground|home)",
    re.IGNORECASE,
)

_TIME_SHIFT_RE = re.compile(
    r"\b(?:the next (?:morning|day|afternoon|evening|night)|"
    r"hours? later|days? passed|later that (?:day|night|morning|evening)|"
    r"that (?:evening|night|morning|afternoon)|"
    r"the following (?:morning|day|night)|"
    r"a few (?:hours|minutes|days) later|"
    r"soon after|eventually|meanwhile|"
    r"the next day|the next morning|the next night)",
    re.IGNORECASE,
)

_CHARACTER_MOVEMENT_RE = re.compile(
    r"\b(?:arrived? at|entered (?:the|a)|walked into|left for|"
    r"stepped into|moved to|headed to|went to|returned to|"
    r"arrived|departed|left|entered|exited|climbed|ran to|"
    r"walked to|stepped out|came back|returned|retreated)",
    re.IGNORECASE,
)

_SECTION_BREAK_RE = re.compile(
    r"^\s*(?:\*{3,}|-{3,}|\*\s*\*\s*\*)\s*$",
    re.MULTILINE,
)

# Fountain element detection patterns
_CENTERED_RE = re.compile(r"^>\s*.+\s*<$")
_FOUNTAIN_SECTION_RE = re.compile(r"^#{1,6}\s+.+")
_SYNOPSIS_RE = re.compile(r"^=\s*.+")
_LYRIC_RE = re.compile(r"^~\s*.+")
_PAGE_BREAK_RE = re.compile(r"^={3,}\s*$")

# Weak signals (keep same scene)
_CONTINUATION_WORDS_RE = re.compile(
    r"\b(?:meanwhile|at the same time|inside|outside|"
    r"back inside|still|again|there|here)\b",
    re.IGNORECASE,
)

# Inner thought tags to strip (keep surrounding text)
_INNER_THOUGHT_TAGS_RE = re.compile(
    r"\b(?:he|she|they|I)\s+"
    r"(?:thought|wondered|pondered|reflected|considered|realized|"
    r"knew|felt|believed|imagined|recalled|remembered|"
    r"decided|noticed|observed|saw|heard)\s+(?:that\s+)?",
    re.IGNORECASE,
)

# Dialogue extraction patterns
_DIALOGUE_QUOTED_RE = re.compile(
    r'((?:"([^"]*)")|'
    r"(\u201c([^\u201d]*)\u201d)|"
    r"('([^']*)'))",
    re.UNICODE,
)

# Attribution after: "dialogue" said/asked/etc. Name
_DIALOGUE_ATTRIB_AFTER_RE = re.compile(
    r"(?:said|asked|replied|answered|called|shouted|whispered|"
    r"yelled|exclaimed|muttered|cried|laughed|smiled|nodded|"
    r"continued|began|started|added|finished|"
    r"murmured|breathed|sighed|mumbled|stammered|lisped|"
    r"bellowed|roared|howled|barked|snapped|"
    r"stated|declared|announced|proclaimed|mentioned|remarked|noted|observed|"
    r"sobbed|wailed|gasped|choked|groaned|moaned|wept|cried out|"
    r"blurted|blurted out|burst out|cut in|interjected|piped up|"
    r"conceded|admitted|retorted|"
    r"drawled|rambled|grumbled|groused|complained|griped)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
)

# Attribution before: Name said, "dialogue" or Name said.
_DIALOGUE_ATTRIB_BEFORE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+"
    r"(?:said|asked|replied|answered|called|shouted|whispered|"
    r"yelled|exclaimed|muttered|cried|laughed|smiled|nodded|"
    r"continued|began|started|added|finished|"
    r"murmured|breathed|sighed|mumbled|stammered|lisped|"
    r"bellowed|roared|howled|barked|snapped|"
    r"stated|declared|announced|proclaimed|mentioned|remarked|noted|observed|"
    r"sobbed|wailed|gasped|choked|groaned|moaned|wept|cried out|"
    r"blurted|blurted out|burst out|cut in|interjected|piped up|"
    r"conceded|admitted|retorted|"
    r"drawled|rambled|grumbled|groused|complained|griped)[,.\s]+"
    r"['\"\u201c]",
)

# V.O. cue patterns
_VO_CUE_RE = re.compile(
    r"\b(?:thought|pondered|wondered|reflected|considered|muttered "
    r"to (?:himself|herself|themselves)|whispered to (?:himself|herself|"
    r"themselves)|said to (?:himself|herself|themselves)|"
    r"asked (?:himself|herself|themselves)|"
    r"muttered under (?:his|her|their) breath)\b",
    re.IGNORECASE,
)

# Dialogue interruption pattern
_INTERRUPTED_RE = re.compile(
    r'\u2014|"?\s*\.\.\.|[—–]',
)

# Skip words for character names (common false positives)
_NAME_SKIP_WORDS: frozenset[str] = frozenset(
    {
        "THE",
        "A",
        "AN",
        "AND",
        "OR",
        "BUT",
        "NOT",
        "IN",
        "ON",
        "AT",
        "TO",
        "FOR",
        "OF",
        "WITH",
        "BY",
        "FROM",
        "AS",
        "IS",
        "IT",
        "BE",
        "HE",
        "SHE",
        "WE",
        "THEY",
        "ME",
        "HIM",
        "HER",
        "US",
        "THEM",
        "THIS",
        "THAT",
        "THESE",
        "THOSE",
        "WHAT",
        "WHEN",
        "WHERE",
        "WHY",
        "HOW",
        "WHO",
        "WHICH",
        "SOME",
        "ALL",
        "MORE",
        "MOST",
        "JUST",
        "VERY",
        "WELL",
        "SO",
        "IF",
        "THEN",
        "ELSE",
        "ALSO",
        "ONLY",
        "YES",
        "NO",
        "OK",
        "OH",
        "AH",
        "UM",
        "HMM",
        "HEY",
        "HI",
        "HELLO",
        "GOODBYE",
        "PLEASE",
        "THANKS",
        "SORRY",
        "WAIT",
    }
)


# ── Component 1: DialogueExtractor ──────────────────────────────────────────


class DialogueExtractor:
    """Parse quoted dialogue from novel text.

    Handles both straight and curly quotes, attribution before/after,
    interruptions, and V.O. cues.
    """

    def extract(self, text: str) -> list[dict[str, str | bool]]:
        """Extract dialogue blocks from *text*.

        Returns:
            List of dicts with keys: character (str), text (str), vo (bool).
        """
        if not text or not text.strip():
            return []

        results: list[dict[str, str | bool]] = []

        for match in _DIALOGUE_QUOTED_RE.finditer(text):
            # Group 2 = straight double, group 4 = curly double, group 6 = single
            dialogue_text = match.group(2) or match.group(4) or match.group(6) or ""
            if not dialogue_text.strip():
                continue

            # Determine character from attribution
            character = self._find_attribution(text, match.start(), match.end())
            vo = self._detect_vo(text, match.end())

            results.append(
                {
                    "character": character,
                    "text": dialogue_text.strip(),
                    "vo": vo,
                }
            )

        return results

    def _find_attribution(self, text: str, quote_start: int, quote_end: int) -> str:
        """Find character attribution near a quote.

        Checks after the quote first (more common), then before.
        """
        # Look after the quote (within ~80 chars)
        after_region = text[quote_end : quote_end + 80]
        after_match = _DIALOGUE_ATTRIB_AFTER_RE.search(after_region)
        if after_match:
            name = after_match.group(1).strip()
            if name.upper() not in _NAME_SKIP_WORDS:
                return name.upper()

        # Look before the quote (within ~80 chars)
        before_start = max(0, quote_start - 80)
        before_region = text[before_start : quote_start + 1]
        before_match = _DIALOGUE_ATTRIB_BEFORE_RE.search(before_region)
        if before_match:
            name = before_match.group(1).strip()
            if name.upper() not in _NAME_SKIP_WORDS:
                return name.upper()

        return "UNKNOWN"

    def _detect_vo(self, text: str, after_pos: int) -> bool:
        """Detect voice-over cues after a quote."""
        region = text[after_pos : after_pos + 60]
        return bool(_VO_CUE_RE.search(region))


# ── Component 2: SceneBreakDetector ─────────────────────────────────────────


class SceneBreakDetector:
    """Determine scene boundaries from narration.

    Uses paragraph breaks, location/time shifts, character movement,
    and section breaks to identify scene boundaries.
    """

    def detect(self, text: str) -> list[dict[str, Any]]:
        """Split *text* into scene groups.

        Returns:
            List of dicts with keys: heading (str), paragraphs (list[str]).
        """
        if not text or not text.strip():
            return []

        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        scenes: list[dict[str, Any]] = []
        current_paragraphs: list[str] = [paragraphs[0]]

        for i in range(1, len(paragraphs)):
            prev_para = paragraphs[i - 1]
            curr_para = paragraphs[i]

            if self._is_scene_break(prev_para, curr_para):
                scenes.append(
                    {
                        "heading": "",  # Will be inferred later
                        "paragraphs": current_paragraphs,
                    }
                )
                current_paragraphs = [curr_para]
            else:
                current_paragraphs.append(curr_para)

        # Don't forget the last group
        scenes.append(
            {
                "heading": "",
                "paragraphs": current_paragraphs,
            }
        )

        return scenes

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into non-empty paragraphs."""
        paras = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paras if p.strip()]

    def _is_scene_break(self, prev: str, curr: str) -> bool:
        """Determine if *curr* paragraph starts a new scene."""
        # Strong signal: section break
        if _SECTION_BREAK_RE.match(curr.strip()):
            return True

        score = 0

        # Location shift
        if _LOCATION_SHIFT_RE.search(curr):
            score += 3

        # Time shift
        if _TIME_SHIFT_RE.search(curr):
            score += 3

        # Character movement
        if _CHARACTER_MOVEMENT_RE.search(curr):
            score += 2

        # Weak signal: continuation words in current paragraph
        if _CONTINUATION_WORDS_RE.match(curr.strip()):
            score -= 2

        return score >= 2


# ── Component 3: LocationInferencer ─────────────────────────────────────────


class LocationInferencer:
    """Infer INT./EXT. and time-of-day from text context."""

    def infer(self, paragraphs: list[str]) -> str:
        """Infer a scene heading from *paragraphs*.

        Returns:
            A scene heading like "INT. KITCHEN - DAY".
        """
        combined = " ".join(paragraphs).lower()

        # Infer location type
        location_type = "INT"
        for kw in _INT_KEYWORDS:
            if kw in combined:
                location_type = "INT"
                break
        for kw in _EXT_KEYWORDS:
            if kw in combined:
                location_type = "EXT"
                break

        # Infer specific location
        location_name = self._extract_location_name(combined)

        # Infer time of day
        time_of_day = "DAY"
        for kw, tod in _TIME_KEYWORDS.items():
            if kw in combined:
                time_of_day = tod
                break

        return f"{location_type}. {location_name} - {time_of_day}"

    def _extract_location_name(self, text: str) -> str:
        """Extract a location name from text."""
        # Try "in the X" / "at the X" patterns
        match = re.search(
            r"(?:in the|at the|inside the|near the|by the|on the|"
            r"through the|arrived at|entered the|walked into|returned to|"
            r"went to|headed to|stepped into|moved to)\s+"
            r"([a-z]+(?:\s+[a-z]+)?)",
            text,
        )
        if match:
            raw = match.group(1).strip()
            # Take only first 3 words max
            words = raw.split()[:3]
            return " ".join(words).upper()

        return "LOCATION"


# ── Component 4: ActionFormatter ────────────────────────────────────────────


class ActionFormatter:
    """Convert narration paragraphs to action lines.

    Strips inner thought tags and preserves paragraph structure.
    """

    def format_paragraph(self, paragraph: str) -> str:
        """Clean a paragraph for use as an action line.

        - Strips inner thought tags (he thought, she wondered, etc.)
        - Condenses action lines (removes filter words, simplifies phrasing)
        - Preserves original tense (no conversion)
        - Returns cleaned text
        """
        if not paragraph or not paragraph.strip():
            return ""

        text = paragraph.strip()

        # Strip inner thought tags
        text = _INNER_THOUGHT_TAGS_RE.sub("", text)

        # Clean up any double spaces left behind
        text = re.sub(r"\s{2,}", " ", text).strip()

        # Condense action line
        text = self._condense_action(text)

        return text

    def _condense_action(self, text: str) -> str:
        """Condense an action line for standard screenplay format.

        - Removes filter words (very, really, quite, etc.)
        - Removes unnecessary 'that' after verbs of cognition
        - Simplifies 'began to' / 'started to'
        - Removes redundant adverbs after speech verbs
        - Truncates to ~58 chars (standard screenplay width)
        """
        if not text or not text.strip():
            return ""

        result = text.strip()

        # Remove filter words
        filter_words = ["very", "really", "quite", "somewhat", "rather", "fairly"]
        for word in filter_words:
            # Match the word as a whole token, case-insensitive
            result = re.sub(rf"\b{word}\b\s*", "", result, flags=re.IGNORECASE)

        # Remove unnecessary "that" after cognition verbs
        # "He realized that she was gone" -> "He realized she was gone"
        # But keep "that" when it's a demonstrative ("He grabbed that book")
        cognition_verbs = (
            r"(?:realized|thought|wondered|knew|felt|believed|imagined|"
            r"recalled|remembered|decided|noticed|observed|saw|heard|"
            r"understood|recognized|discovered|noticed|assumed|expected|"
            r"hoped|feared|suspected|found|concluded)"
        )
        result = re.sub(
            rf"({cognition_verbs})\s+that\b",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )

        # Simplify "began to" / "started to"
        began_to_pattern = re.compile(r"\b(\w+)\s+began\s+to\b", re.IGNORECASE)
        started_to_pattern = re.compile(r"\b(\w+)\s+started\s+to\b", re.IGNORECASE)

        def _simplify_began_to(match: re.Match[str]) -> str:
            subject = match.group(1)
            # Extract the infinitive that follows "began to"
            rest = match.group(0)
            # "He began to run" -> "He ran"
            # Find the word after "to "
            after_to = rest[rest.lower().index("to") + 3 :]
            verb = after_to.strip().split()[0] if after_to.strip() else ""
            if not verb:
                return match.group(0)
            # Simple past tense: just use the verb as-is for now
            # (full conjugation is complex; keep it simple)
            return f"{subject} {verb}"

        result = began_to_pattern.sub(_simplify_began_to, result)
        result = started_to_pattern.sub(_simplify_began_to, result)

        # Remove redundant adverbs after speech/action verbs
        speech_verbs = (
            r"(?:whispered|muttered|murmured|shouted|yelled|cried|"
            r"exclaimed|stated|declared|announced|remarked|noted|"
            r"observed|replied|answered|snapped|barked|roared|"
            r"bellowed|howled|sobbed|wailed|gasped|choked|groaned|"
            r"moaned|wept|blurted|drawled|grumbled|complained)"
        )
        redundant_adverbs = (
            r"softly|loudly|quietly|angrily|calmly|gently|harshly|"
            r"briefly|quickly|slowly|eagerly|happily|sadly|coldly|"
            r"warmly|bitterly|sweetly|dryly|flatly|sharply|"
            r"wearily|hollowly|thickly|hoarsely"
        )
        result = re.sub(
            rf"({speech_verbs})\s+({redundant_adverbs})\b",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )

        # Clean up any double spaces left from removals
        result = re.sub(r"\s{2,}", " ", result).strip()

        # Truncate to ~58 chars (standard screenplay width) if longer
        if len(result) > 62:
            # Try to cut at a word boundary near 58 chars
            truncated = result[:58]
            last_space = truncated.rfind(" ")
            if last_space > 40:
                result = truncated[:last_space]
            else:
                result = truncated

        return result


# ── Component 5: FountainAssembler ──────────────────────────────────────────


class FountainAssembler:
    """Assemble screenplay elements into valid Fountain format.

    Produces Screenplay objects with proper scene headings, action lines,
    character cues, and dialogue in Fountain 1.1 format.
    """

    def __init__(
        self,
        title: str = "Untitled",
        author: str = "Unknown",
    ) -> None:
        self.title = title
        self.author = author

    def assemble(
        self,
        scenes: list[dict[str, Any]],
    ) -> Screenplay:
        """Convert scene groups into a Screenplay object.

        Args:
            scenes: List of dicts with 'heading' (str) and 'paragraphs' (list).

        Returns:
            A complete Screenplay object.
        """
        screenplay = Screenplay(title=self.title, author=self.author)
        dialogue_extractor = DialogueExtractor()
        action_formatter = ActionFormatter()

        for i, scene_data in enumerate(scenes):
            heading = scene_data["heading"]
            paragraphs = scene_data["paragraphs"]

            # Build scene content as Fountain text
            content_parts: list[str] = []

            for para in paragraphs:
                # Check if this paragraph contains dialogue
                dialogues = dialogue_extractor.extract(para)

                if dialogues:
                    # Split paragraph into dialogue and action segments
                    self._add_dialogue_segments(para, dialogues, content_parts, action_formatter)
                else:
                    # Pure action
                    cleaned = action_formatter.format_paragraph(para)
                    if cleaned:
                        content_parts.append(cleaned)

            # Build the scene
            content = "\n\n".join(content_parts)
            scene = Scene(heading=heading, content=content)
            screenplay.scenes.append(scene)

            # Convert scene to elements
            self._scene_to_elements(scene, screenplay.elements)

        return screenplay

    def _add_dialogue_segments(
        self,
        paragraph: str,
        dialogues: list[dict[str, str | bool]],
        content_parts: list[str],
        action_formatter: ActionFormatter,
    ) -> None:
        """Add dialogue segments to content_parts.

        Splits the paragraph around quotes and interleaves action + character
        + dialogue elements.
        """
        # Find quote positions in the paragraph
        quote_positions: list[tuple[int, int, dict[str, str | bool]]] = []
        for match in _DIALOGUE_QUOTED_RE.finditer(paragraph):
            dialogue_text = match.group(2) or match.group(4) or match.group(6) or ""
            if dialogue_text.strip():
                # Find matching dialogue entry
                for d in dialogues:
                    if d["text"] == dialogue_text.strip():
                        quote_positions.append((match.start(), match.end(), d))
                        break

        if not quote_positions:
            # Fallback: just add as action
            cleaned = action_formatter.format_paragraph(paragraph)
            if cleaned:
                content_parts.append(cleaned)
            return

        # Process segments between and around quotes
        last_end = 0
        for start, end, dialogue in quote_positions:
            # Action before this quote
            action_text = paragraph[last_end:start].strip()
            if action_text:
                cleaned = action_formatter.format_paragraph(action_text)
                if cleaned:
                    content_parts.append(cleaned)

            # Character cue
            character = dialogue["character"]
            vo_ext = " (V.O.)" if dialogue["vo"] else ""
            content_parts.append(f"{character}{vo_ext}")

            # Dialogue text
            content_parts.append(str(dialogue["text"]))

            last_end = end

        # Action after last quote
        action_text = paragraph[last_end:].strip()
        if action_text:
            cleaned = action_formatter.format_paragraph(action_text)
            if cleaned:
                content_parts.append(cleaned)

    def _scene_to_elements(
        self,
        scene: Scene,
        elements: list[ScreenplayElement],
    ) -> None:
        """Convert a Scene's content string into ScreenplayElements."""
        # Add scene heading
        elements.append(
            ScreenplayElement(
                element_type=ElementType.SCENE_HEADING,
                text=scene.heading,
            )
        )

        if not scene.content.strip():
            return

        lines = scene.content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Centered text: >text<
            if _CENTERED_RE.match(line):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.CENTERED,
                        text=line,
                    )
                )
                i += 1
                continue

            # Section heading: # Title
            if _FOUNTAIN_SECTION_RE.match(line):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.SECTION,
                        text=line,
                    )
                )
                i += 1
                continue

            # Synopsis: = text
            if _SYNOPSIS_RE.match(line):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.SYNOPSIS,
                        text=line,
                    )
                )
                i += 1
                continue

            # Lyric: ~ text
            if _LYRIC_RE.match(line):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.LYRIC,
                        text=line,
                    )
                )
                i += 1
                continue

            # Page break: ===
            if _PAGE_BREAK_RE.match(line):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.PAGE_BREAK,
                        text=line,
                    )
                )
                i += 1
                continue

            # Character cue (ALL CAPS, short line)
            if (
                line == line.upper()
                and len(line) <= 30
                and not line.startswith(("INT.", "EXT.", "FADE", ">"))
                and not line.endswith("TO:")
                and any(c.isalpha() for c in line)
            ):
                elements.append(
                    ScreenplayElement(
                        element_type=ElementType.CHARACTER,
                        text=line,
                    )
                )
                i += 1
                # Collect following dialogue lines
                while i < len(lines):
                    dial_line = lines[i].strip()
                    if not dial_line:
                        i += 1
                        continue
                    if (
                        dial_line == dial_line.upper() and len(dial_line) <= 30
                    ) or dial_line.startswith(("INT.", "EXT.")):
                        break
                    if dial_line.startswith("(") and dial_line.endswith(")"):
                        elements.append(
                            ScreenplayElement(
                                element_type=ElementType.PARENTHETICAL,
                                text=dial_line,
                            )
                        )
                    else:
                        elements.append(
                            ScreenplayElement(
                                element_type=ElementType.DIALOGUE,
                                text=dial_line,
                            )
                        )
                    i += 1
                continue

            # Default: action
            elements.append(
                ScreenplayElement(
                    element_type=ElementType.ACTION,
                    text=line,
                )
            )
            i += 1


# ── Public API ──────────────────────────────────────────────────────────────


def convert_with_rules(
    text: str,
    title: str = "Untitled",
    author: str = "Unknown",
) -> Screenplay:
    """Convert novel text to screenplay using rules only. No LLM needed.

    Args:
        text: Plain-text novel content.
        title: Screenplay title.
        author: Screenplay author.

    Returns:
        A Screenplay object with scenes, characters, and elements.
    """
    if not text or not text.strip():
        return Screenplay(title=title, author=author)

    # Step 1: Detect scene breaks
    scene_detector = SceneBreakDetector()
    raw_scenes = scene_detector.detect(text)

    if not raw_scenes:
        return Screenplay(title=title, author=author)

    # Step 2: Infer location/time for each scene
    location_inferencer = LocationInferencer()
    for scene_data in raw_scenes:
        paragraphs = scene_data["paragraphs"]
        scene_data["heading"] = location_inferencer.infer(paragraphs)

    # Step 3: Assemble into Fountain
    assembler = FountainAssembler(title=title, author=author)
    screenplay = assembler.assemble(raw_scenes)

    return screenplay


def convert_chapter_with_rules(
    chapter: Chapter,
    registry: CharacterRegistry,
) -> list[Scene]:
    """Convert a single chapter using rule-based approach.

    Updates the character registry with detected names and returns
    a list of Scene objects.

    Args:
        chapter: A Chapter object with number, text, and optional title.
        registry: CharacterRegistry to update with detected names.

    Returns:
        List of Scene objects for this chapter.
    """
    if not chapter.text or not chapter.text.strip():
        return []

    # Update registry with character names from this chapter
    registry.update_from_text(chapter.text, chapter.number)

    # Detect scene breaks
    scene_detector = SceneBreakDetector()
    raw_scenes = scene_detector.detect(chapter.text)

    if not raw_scenes:
        return []

    # Infer location/time for each scene
    location_inferencer = LocationInferencer()
    for scene_data in raw_scenes:
        paragraphs = scene_data["paragraphs"]
        scene_data["heading"] = location_inferencer.infer(paragraphs)

    # Assemble scenes
    dialogue_extractor = DialogueExtractor()
    action_formatter = ActionFormatter()
    scenes: list[Scene] = []

    for scene_data in raw_scenes:
        heading = scene_data["heading"]
        paragraphs = scene_data["paragraphs"]

        content_parts: list[str] = []
        for para in paragraphs:
            dialogues = dialogue_extractor.extract(para)
            if dialogues:
                # Split around dialogue
                quote_positions: list[tuple[int, int, dict]] = []
                for match in _DIALOGUE_QUOTED_RE.finditer(para):
                    dtext = match.group(2) or match.group(4) or match.group(6) or ""
                    if dtext.strip():
                        for d in dialogues:
                            if d["text"] == dtext.strip():
                                quote_positions.append((match.start(), match.end(), d))
                                break

                last_end = 0
                for start, end, dialogue in quote_positions:
                    action_text = para[last_end:start].strip()
                    if action_text:
                        cleaned = action_formatter.format_paragraph(action_text)
                        if cleaned:
                            content_parts.append(cleaned)

                    character = dialogue["character"]
                    vo_ext = " (V.O.)" if dialogue["vo"] else ""
                    content_parts.append(f"{character}{vo_ext}")
                    content_parts.append(dialogue["text"])
                    last_end = end

                action_text = para[last_end:].strip()
                if action_text:
                    cleaned = action_formatter.format_paragraph(action_text)
                    if cleaned:
                        content_parts.append(cleaned)
            else:
                cleaned = action_formatter.format_paragraph(para)
                if cleaned:
                    content_parts.append(cleaned)

        content = "\n\n".join(content_parts)
        scenes.append(Scene(heading=heading, content=content))

    return scenes
