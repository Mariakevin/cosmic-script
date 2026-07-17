"""Fountain validator error codes, messages, and helper functions.

Defines error constants (E1-E20), warning constants, and helper functions
to create standardized error and warning dictionaries.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Error Codes
# ---------------------------------------------------------------------------

E1 = "E1"
E2 = "E2"
E3 = "E3"
E4 = "E4"
E5 = "E5"
E6 = "E6"
E7 = "E7"
E8 = "E8"
E9 = "E9"
E10 = "E10"
E11 = "E11"
E12 = "E12"
E13 = "E13"
E14 = "E14"
E15 = "E15"
E16 = "E16"
E17 = "E17"
E18 = "E18"
E19 = "E19"
E20 = "E20"

# Warning Codes
W1 = "W1"

# ---------------------------------------------------------------------------
# Error Messages
# ---------------------------------------------------------------------------

ERROR_MESSAGES: dict[str, str] = {
    E1: "Scene heading missing INT/EXT prefix",
    E2: "Scene heading missing time-of-day",
    E3: "Orphaned dialogue (no preceding character)",
    E4: "Character name not uppercase",
    E5: "Transition not ending with TO:",
    E6: "Transition not uppercase",
    E7: "Parenthetical outside dialogue context",
    E8: "Unclosed boneyard (missing */)",
    E9: "Unclosed note (missing ]])",
    E10: "Character name inconsistency",
    E11: "Dual dialogue marker without matching second character",
    E12: "Invalid scene number format",
    E13: "Centered text formatting issue",
    E14: "Section heading formatting issue",
    E15: "Synopsis formatting issue",
    E16: "Lyric line formatting issue",
    E17: "Page break formatting issue",
    E18: "Forced scene heading issue",
    E19: "Forced action/character/transition issue",
    E20: "Emphasis formatting issue",
}

WARNING_MESSAGES: dict[str, str] = {
    W1: "Note found in Fountain text",
}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def make_error(
    code: str,
    message: str,
    text: str,
    line: int,
) -> dict:
    """Create a standardized error dictionary.

    Args:
        code: Error code (e.g., E1, E2).
        message: Human-readable error message.
        text: The offending text content.
        line: 1-indexed line number where the error occurred.

    Returns:
        A dict with keys: code, message, text, line.
    """
    return {
        "code": code,
        "message": message,
        "text": text,
        "line": line,
    }


def make_warning(
    code: str,
    message: str,
    text: str,
    line: int,
) -> dict:
    """Create a standardized warning dictionary.

    Args:
        code: Warning code (e.g., W1).
        message: Human-readable warning message.
        text: The text that triggered the warning.
        line: 1-indexed line number where the warning occurred.

    Returns:
        A dict with keys: code, message, text, line.
    """
    return {
        "code": code,
        "message": message,
        "text": text,
        "line": line,
    }
