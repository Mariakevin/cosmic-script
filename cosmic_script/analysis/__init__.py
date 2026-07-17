"""Screenplay analysis tools: coverage reports, logline generation,
character voice analysis, scene pacing analysis, and quality metrics.

Public API:
    - generate_coverage(screenplay, ...) -> ScriptCoverage
    - generate_logline(screenplay, ...) -> str
    - analyze_voices(screenplay) -> list[CharacterVoice]
    - analyze_pacing(screenplay) -> PacingReport
    - format_score(screenplay) -> float
    - structure_score(screenplay) -> float
    - dialogue_score(screenplay) -> float
    - overall_quality(screenplay) -> float
    - compute_metrics(screenplay) -> QualityMetrics
"""

from __future__ import annotations

from cosmic_script.analysis.coverage import ScriptCoverage, generate_coverage
from cosmic_script.analysis.logline import generate_logline
from cosmic_script.analysis.voice import CharacterVoice, analyze_voices
from cosmic_script.analysis.pacing import ScenePacing, PacingReport, analyze_pacing
from cosmic_script.analysis.quality_metrics import (
    QualityMetrics,
    compute_metrics,
    format_score,
    structure_score,
    dialogue_score,
    overall_quality,
)

__all__ = [
    "ScriptCoverage",
    "CharacterVoice",
    "ScenePacing",
    "PacingReport",
    "QualityMetrics",
    "generate_coverage",
    "generate_logline",
    "analyze_voices",
    "analyze_pacing",
    "format_score",
    "structure_score",
    "dialogue_score",
    "overall_quality",
    "compute_metrics",
]
