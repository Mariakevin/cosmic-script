"""Integration tests -- end-to-end pipeline verification.

Tests the complete conversion pipeline from ingestion through export,
covering AI (demo) mode, plus analysis features.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Set demo mode for deterministic AI output
os.environ["DEMO_MODE"] = "true"

from cosmic_script.analysis.coverage import generate_coverage
from cosmic_script.analysis.logline import generate_logline
from cosmic_script.analysis.pacing import analyze_pacing
from cosmic_script.analysis.voice import analyze_voices
from cosmic_script.conversion.converter import ConversionConfig, ScreenplayConverter
from cosmic_script.conversion.pipeline import convert
from cosmic_script.export.exporter import export_screenplay
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.pdf_export import export_pdf
from cosmic_script.export.validator import FountainValidator
from cosmic_script.ingestion.chapterizer import split_into_chapters
from cosmic_script.ingestion.loader import load_document
from cosmic_script.models import Screenplay

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =========================================================================
# 1. Full Pipeline -- AI (Demo) Mode
# =========================================================================


class TestFullPipelineAIMode:
    """Test complete conversion pipeline in AI (demo) mode."""

    def test_demo_mode_conversion(self):
        """Demo mode produces deterministic output without API calls."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        config = ConversionConfig(model="demo")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters, title="Demo Test")

        assert screenplay is not None
        assert len(screenplay.scenes) > 0, "Demo mode must produce scenes"

    def test_demo_mode_deterministic(self):
        """Running demo mode twice produces identical output."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        config = ConversionConfig(model="demo")
        converter = ScreenplayConverter(config)

        sp1 = converter.convert_novel(chapters, title="Deterministic")
        fountain1 = generate_fountain(sp1)

        sp2 = converter.convert_novel(chapters, title="Deterministic")
        fountain2 = generate_fountain(sp2)

        assert fountain1 == fountain2, "Demo mode must be deterministic"

    def test_demo_output_valid_fountain(self):
        """Demo mode output must be valid Fountain."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        config = ConversionConfig(model="demo")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters, title="Demo Validation")

        fountain_text = generate_fountain(screenplay)
        validator = FountainValidator()
        result = validator.validate(fountain_text)
        assert result["valid"], f"Demo output must be valid: {result['errors']}"

    def test_demo_mode_via_pipeline(self):
        """Demo mode works through the high-level pipeline.convert() API."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        screenplay = convert(text, model="demo", title="Pipeline Demo")

        assert screenplay is not None
        assert len(screenplay.scenes) > 0

        fountain_text = generate_fountain(screenplay)
        assert "FADE IN" in fountain_text or "INT." in fountain_text, (
            "Demo output must contain screenplay elements"
        )


# =========================================================================
# 2. Ingestion Pipeline
# =========================================================================


class TestIngestionPipeline:
    """Test document loading and chapter splitting."""

    def test_load_txt_file(self):
        """Load .txt file successfully."""
        text = load_document(str(FIXTURES_DIR / "sample.txt"))
        assert text, "sample.txt must not be empty"
        assert "plain text file" in text

    def test_load_md_file(self):
        """Load .md file and strip Markdown syntax."""
        text = load_document(str(FIXTURES_DIR / "sample.md"))
        assert text, "sample.md must not be empty"
        # Markdown markers should be stripped
        assert "**" not in text, "Bold markers should be stripped"
        assert "##" not in text, "Heading markers should be stripped"
        # But content should remain
        assert "dark and stormy" in text.lower()

    def test_load_sample_story(self):
        """Load sample_story.txt fixture."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        assert text, "sample_story.txt must not be empty"
        assert len(text) > 100, "Sample story must have substantial content"

    def test_chapter_splitting_with_headings(self):
        """Chapter splitting with explicit chapter headings."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        chapters = split_into_chapters(text)

        assert len(chapters) >= 2, "Must detect at least 2 chapters"
        for ch in chapters:
            assert ch.number > 0, "Chapter numbers must be positive"
            assert ch.text, "Chapter text must not be empty"

    def test_chapter_splitting_without_headings(self):
        """Chapter splitting falls back to chunking when no headings exist."""
        text = load_document(str(FIXTURES_DIR / "no_chapters.txt"))
        chapters = split_into_chapters(text)

        assert len(chapters) >= 1, "Must produce at least one chunk"
        for ch in chapters:
            assert ch.text, "Each chunk must have text"

    def test_chapter_splitting_empty_text(self):
        """Chapter splitting handles empty text gracefully."""
        chapters = split_into_chapters("")
        assert chapters == [], "Empty text should produce empty list"

    def test_chapter_splitting_sample_story(self):
        """Sample story (single paragraph) splits into chunks."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        assert len(chapters) >= 1, "Must produce at least one chapter"
        assert chapters[0].number == 1
        assert chapters[0].text, "First chapter must have text"

    def test_sample_story_fixture_loads_and_splits(self):
        """Sample story fixture loads and splits correctly through full path."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        assert len(chapters) > 0
        combined = "\n".join(ch.text for ch in chapters)
        assert len(combined) > 500, "Recombined text must be substantial"


# =========================================================================
# 3. Export Pipeline
# =========================================================================


class TestExportPipeline:
    """Test export to various formats."""

    def test_export_fountain(self, tmp_path):
        """Export to .fountain format."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, model="demo", title="Fountain Export")

        out_path = str(tmp_path / "output.fountain")
        result_path = export_screenplay(screenplay, out_path, fmt="fountain")

        assert result_path == os.path.abspath(out_path)
        assert os.path.exists(out_path)
        content = Path(out_path).read_text(encoding="utf-8")
        assert content, "Exported file must not be empty"

    def test_export_txt(self, tmp_path):
        """Export to .txt format."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, model="demo", title="TXT Export")

        out_path = str(tmp_path / "output.txt")
        result_path = export_screenplay(screenplay, out_path, fmt="txt")

        assert result_path == os.path.abspath(out_path)
        assert os.path.exists(out_path)
        content = Path(out_path).read_text(encoding="utf-8")
        assert content, "Exported file must not be empty"
        assert len(content) > 20, "Exported file must have meaningful content"

    def test_export_pdf(self, tmp_path):
        """Export to .pdf format (verify file created, size > 0)."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, model="demo", title="PDF Export")

        out_path = str(tmp_path / "output.pdf")
        result_path = export_pdf(screenplay, out_path)

        assert result_path
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0, "PDF must have content"

    def test_export_fountain_validates(self, tmp_path):
        """Exported Fountain file must pass validation."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, model="demo", title="Validated Export")

        out_path = str(tmp_path / "validated.fountain")
        export_screenplay(screenplay, out_path, fmt="fountain")

        content = Path(out_path).read_text(encoding="utf-8")
        validator = FountainValidator()
        result = validator.validate(content)
        # Should have no critical errors
        critical = [e for e in result["errors"] if e["code"] in {"E1", "E3", "E8", "E9"}]
        assert len(critical) == 0, f"Critical errors in exported Fountain: {critical}"

    def test_export_unsupported_format(self, tmp_path):
        """Export with unsupported format raises ValueError."""
        text = load_document(str(FIXTURES_DIR / "sample.txt"))
        screenplay = convert(text, model="demo")

        out_path = str(tmp_path / "output.xyz")
        with pytest.raises(ValueError, match="Unsupported format"):
            export_screenplay(screenplay, out_path, fmt="xyz")


# =========================================================================
# 4. Analysis Pipeline
# =========================================================================


class TestAnalysisPipeline:
    """Test analysis features in demo mode."""

    def _make_screenplay(self) -> Screenplay:
        """Helper: create a screenplay from the sample story in demo mode."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        return convert(text, model="demo", title="Analysis Test")

    def test_coverage_analysis(self):
        """Generate coverage report in demo mode."""
        screenplay = self._make_screenplay()
        coverage = generate_coverage(screenplay, model="demo")

        assert coverage is not None
        assert coverage.logline, "Coverage must have a logline"
        assert coverage.synopsis, "Coverage must have a synopsis"
        assert 1 <= coverage.rating <= 10, "Rating must be 1-10"
        assert coverage.recommendation in ("Pass", "Consider", "Strong Consider")
        assert len(coverage.strengths) > 0, "Must list strengths"
        assert len(coverage.weaknesses) > 0, "Must list weaknesses"

    def test_logline_generation(self):
        """Generate logline in demo mode."""
        screenplay = self._make_screenplay()
        logline = generate_logline(screenplay, model="demo")

        assert logline, "Logline must not be empty"
        assert len(logline) > 10, "Logline must be meaningful"
        assert len(logline.split()) <= 60, "Logline should be concise"

    def test_voice_analysis(self):
        """Analyze character voices (pure text, no LLM)."""
        from cosmic_script.models import Scene

        # Build a screenplay with dialogue for voice analysis
        screenplay = Screenplay(
            title="Voice Test",
            scenes=[
                Scene(
                    heading="INT. OFFICE - DAY",
                    content=(
                        "JOHN\n"
                        "I cannot believe this is happening.\n\n"
                        "JANE\n"
                        "We have no choice but to move forward.\n\n"
                        "JOHN\n"
                        "What about the consequences?"
                    ),
                ),
            ],
        )

        voices = analyze_voices(screenplay)

        assert len(voices) > 0, "Must detect at least one character voice"
        for voice in voices:
            assert voice.name, "Voice must have a name"
            assert voice.total_lines > 0, "Voice must have dialogue lines"
            assert voice.speaking_style in ("terse", "casual", "verbose", "formal", "neutral")
            assert voice.emotional_tone in ("neutral", "angry", "sad", "happy", "anxious")

    def test_pacing_analysis(self):
        """Analyze scene pacing."""
        screenplay = self._make_screenplay()
        report = analyze_pacing(screenplay)

        assert report is not None
        assert report.overall_pacing in ("fast", "medium", "slow")
        assert report.avg_scene_length >= 0
        # With scenes present, we should get scene-level pacing
        if screenplay.scenes:
            assert len(report.scenes) > 0, "Must have per-scene pacing data"

    def test_analysis_on_demo_mode_screenplay(self):
        """Analysis works on demo-mode generated screenplays."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, model="demo", title="Analysis on Demo")

        # Coverage in demo mode
        coverage = generate_coverage(screenplay, model="demo")
        assert coverage.logline

        # Logline in demo mode
        logline = generate_logline(screenplay, model="demo")
        assert logline

        # Pacing (no LLM)
        pacing = analyze_pacing(screenplay)
        assert pacing.overall_pacing in ("fast", "medium", "slow")


# =========================================================================
# 5. Edge Cases and Error Handling
# =========================================================================


class TestEdgeCases:
    """Edge cases for the full pipeline."""

    def test_load_nonexistent_file(self):
        """Loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_document(str(FIXTURES_DIR / "nonexistent.txt"))

    def test_load_unsupported_extension(self):
        """Loading an unsupported file type raises ValueError."""
        # Create a temp file with unsupported extension
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"content")
            temp_path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                load_document(temp_path)
        finally:
            os.unlink(temp_path)

    def test_chapter_splitting_whitespace_only(self):
        """Whitespace-only text produces empty chapter list."""
        chapters = split_into_chapters("   \n  \n  ")
        assert chapters == []

    def test_convert_with_empty_chapters(self):
        """Converting empty chapter list produces empty screenplay."""
        config = ConversionConfig()
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel([], title="Empty")
        assert screenplay.scenes == []
        assert screenplay.elements == []
