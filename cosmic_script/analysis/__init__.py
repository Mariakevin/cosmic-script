"""Screenplay analysis tools: coverage reports, logline generation,
character voice analysis, and scene pacing analysis.

Public API:
    - generate_coverage(screenplay, ...) -> ScriptCoverage
    - generate_logline(screenplay, ...) -> str
    - analyze_voices(screenplay) -> list[CharacterVoice]
    - analyze_pacing(screenplay) -> PacingReport
"""

from __future__ import annotations

from cosmic_script.analysis.coverage import ScriptCoverage, generate_coverage
from cosmic_script.analysis.logline import generate_logline
from cosmic_script.analysis.voice import CharacterVoice, analyze_voices
from cosmic_script.analysis.pacing import ScenePacing, PacingReport, analyze_pacing

__all__ = [
    "ScriptCoverage",
    "CharacterVoice",
    "ScenePacing",
    "PacingReport",
    "generate_coverage",
    "generate_logline",
    "analyze_voices",
    "analyze_pacing",
]
