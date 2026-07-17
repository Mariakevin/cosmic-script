"""Integration tests -- end-to-end pipeline verification.

Tests the complete conversion pipeline from ingestion through export,
covering both rules mode and AI (demo) mode, plus analysis features.
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
from cosmic_script.conversion.pipeline import convert, convert_file
from cosmic_script.conversion.registry import CharacterRegistry
from cosmic_script.conversion.rules_engine import (
    DialogueExtractor,
    LocationInferencer,
    SceneBreakDetector,
    convert_chapter_with_rules,
    convert_with_rules,
)
from cosmic_script.export.exporter import export_screenplay
from cosmic_script.export.fountain import generate_fountain
from cosmic_script.export.pdf_export import export_pdf
from cosmic_script.export.validator import FountainValidator
from cosmic_script.ingestion.chapterizer import split_into_chapters
from cosmic_script.ingestion.loader import load_document
from cosmic_script.models import Chapter, Screenplay

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =========================================================================
# 1. Full Pipeline -- Rules Mode
# =========================================================================


class TestFullPipelineRulesMode:
    """Test complete conversion pipeline in rules mode (no LLM)."""

    def test_load_and_convert_rules(self):
        """Load text file, split chapters, convert with rules, validate output."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        assert text, "Loaded text must not be empty"

        chapters = split_into_chapters(text)
        assert len(chapters) > 0, "Must detect at least one chapter"

        screenplay = convert(text, mode="rules", title="Test Pipeline")
        assert screenplay is not None
        assert screenplay.title == "Test Pipeline"

        fountain_text = generate_fountain(screenplay)
        assert fountain_text, "Fountain output must not be empty"

    def test_rules_output_valid_fountain(self):
        """Rules mode output must be valid Fountain."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="Validation Test")

        fountain_text = generate_fountain(screenplay)
        validator = FountainValidator()
        result = validator.validate(fountain_text)

        # Rules engine should produce valid or near-valid Fountain
        # Allow minor warnings but no critical structural errors
        critical_codes = {"E1", "E3", "E8", "E9"}
        critical_errors = [e for e in result["errors"] if e["code"] in critical_codes]
        assert len(critical_errors) == 0, f"Critical Fountain errors found: {critical_errors}"

    def test_rules_export_to_pdf(self):
        """Rules mode output can be exported to PDF."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="PDF Test")

        pdf_path = str(FIXTURES_DIR / "_test_output.pdf")
        try:
            result_path = export_pdf(screenplay, pdf_path)
            assert result_path, "export_pdf must return a path"
            assert os.path.exists(result_path), "PDF file must exist"
            assert os.path.getsize(result_path) > 0, "PDF file must not be empty"
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

    def test_rules_screenplay_has_scenes(self):
        """Converted screenplay must contain scenes."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules")

        assert len(screenplay.scenes) > 0, "Screenplay must have at least one scene"
        for scene in screenplay.scenes:
            assert scene.heading, "Every scene must have a heading"
            assert "INT" in scene.heading or "EXT" in scene.heading, (
                f"Scene heading must start with INT/EXT: {scene.heading}"
            )

    def test_rules_full_pipeline_with_sample_story(self):
        """Full pipeline on the sample story fixture."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        assert text, "Sample story must not be empty"

        screenplay = convert(text, mode="rules", title="Sample Story")
        fountain_text = generate_fountain(screenplay)
        assert fountain_text, "Fountain output must not be empty"

        validator = FountainValidator()
        result = validator.validate(fountain_text)
        assert result["valid"], f"Output must be valid Fountain: {result['errors']}"


# =========================================================================
# 2. Full Pipeline -- AI (Demo) Mode
# =========================================================================


class TestFullPipelineAIMode:
    """Test complete conversion pipeline in AI (demo) mode."""

    def test_demo_mode_conversion(self):
        """Demo mode produces deterministic output without API calls."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        config = ConversionConfig(model="demo", mode="ai")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters, title="Demo Test")

        assert screenplay is not None
        assert len(screenplay.scenes) > 0, "Demo mode must produce scenes"

    def test_demo_mode_deterministic(self):
        """Running demo mode twice produces identical output."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        chapters = split_into_chapters(text)

        config = ConversionConfig(model="demo", mode="ai")
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

        config = ConversionConfig(model="demo", mode="ai")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters, title="Demo Validation")

        fountain_text = generate_fountain(screenplay)
        validator = FountainValidator()
        result = validator.validate(fountain_text)
        assert result["valid"], f"Demo output must be valid: {result['errors']}"

    def test_demo_mode_via_pipeline(self):
        """Demo mode works through the high-level pipeline.convert() API."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        screenplay = convert(text, model="demo", mode="ai", title="Pipeline Demo")

        assert screenplay is not None
        assert len(screenplay.scenes) > 0

        fountain_text = generate_fountain(screenplay)
        assert "FADE IN" in fountain_text or "INT." in fountain_text, (
            "Demo output must contain screenplay elements"
        )


# =========================================================================
# 3. Ingestion Pipeline
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
# 4. Export Pipeline
# =========================================================================


class TestExportPipeline:
    """Test export to various formats."""

    def test_export_fountain(self, tmp_path):
        """Export to .fountain format."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="Fountain Export")

        out_path = str(tmp_path / "output.fountain")
        result_path = export_screenplay(screenplay, out_path, fmt="fountain")

        assert result_path == os.path.abspath(out_path)
        assert os.path.exists(out_path)
        content = Path(out_path).read_text(encoding="utf-8")
        assert content, "Exported file must not be empty"

    def test_export_txt(self, tmp_path):
        """Export to .txt format."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="TXT Export")

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
        screenplay = convert(text, mode="rules", title="PDF Export")

        out_path = str(tmp_path / "output.pdf")
        result_path = export_pdf(screenplay, out_path)

        assert result_path
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0, "PDF must have content"

    def test_export_fountain_validates(self, tmp_path):
        """Exported Fountain file must pass validation."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="Validated Export")

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
        screenplay = convert(text, mode="rules")

        out_path = str(tmp_path / "output.xyz")
        with pytest.raises(ValueError, match="Unsupported format"):
            export_screenplay(screenplay, out_path, fmt="xyz")


# =========================================================================
# 5. Analysis Pipeline
# =========================================================================


class TestAnalysisPipeline:
    """Test analysis features in demo mode."""

    def _make_screenplay(self) -> Screenplay:
        """Helper: create a screenplay from the sample story in demo mode."""
        text = load_document(str(FIXTURES_DIR / "sample_story.txt"))
        return convert(text, model="demo", mode="ai", title="Analysis Test")

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

    def test_analysis_on_rules_mode_screenplay(self):
        """Analysis works on rules-mode generated screenplays."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        screenplay = convert(text, mode="rules", title="Analysis on Rules")

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
# 6. Rules Engine Specific
# =========================================================================


class TestRulesEngineSpecific:
    """Test rules engine components through integration paths."""

    def test_dialogue_extraction_from_prose(self):
        """DialogueExtractor extracts quoted dialogue from prose."""
        extractor = DialogueExtractor()
        text = 'She looked at him and said, "I cannot stay here any longer." He replied, "Then go."'
        dialogues = extractor.extract(text)

        assert len(dialogues) == 2, f"Expected 2 dialogues, got {len(dialogues)}"
        assert dialogues[0]["text"] == "I cannot stay here any longer."
        assert dialogues[1]["text"] == "Then go."

    def test_scene_break_detection(self):
        """SceneBreakDetector identifies scene boundaries."""
        detector = SceneBreakDetector()
        text = (
            "They arrived at the office and began working.\n\n"
            "Later that evening, she walked to the park.\n\n"
            "The next morning brought unexpected news."
        )
        scenes = detector.detect(text)

        assert len(scenes) >= 1, "Must detect at least one scene group"
        for scene in scenes:
            assert "paragraphs" in scene
            assert len(scene["paragraphs"]) > 0

    def test_location_inference(self):
        """LocationInferencer generates INT/EXT headings."""
        inferencer = LocationInferencer()
        paragraphs = ["He walked into the kitchen and opened the fridge."]
        heading = inferencer.infer(paragraphs)

        assert heading.startswith("INT.") or heading.startswith("EXT."), (
            f"Location must start with INT/EXT: {heading}"
        )
        assert " - " in heading, f"Location must have time-of-day: {heading}"

    def test_full_chapter_conversion(self):
        """Convert a single chapter through the rules engine."""
        chapter = Chapter(
            number=1,
            text=(
                "In the morning, Sarah walked into the office. "
                '"Good morning," she said to John. '
                '"Good morning," John replied. '
                "She sat down at her desk and began working."
            ),
        )
        registry = CharacterRegistry()
        scenes = convert_chapter_with_rules(chapter, registry)

        assert len(scenes) > 0, "Must produce at least one scene"
        for scene in scenes:
            assert scene.heading, "Scene must have a heading"
            assert scene.content, "Scene must have content"

    def test_rules_mode_via_converter(self):
        """ScreenplayConverter in rules mode skips LLM calls."""
        chapter = Chapter(
            number=1,
            text=(
                "They arrived at the hospital. The nurse greeted them. "
                'The doctor said, "We need to run more tests."'
            ),
        )
        config = ConversionConfig(mode="rules")
        converter = ScreenplayConverter(config)
        registry = CharacterRegistry()

        scenes = converter.convert_chapter(chapter, registry)
        assert len(scenes) > 0

    def test_rules_mode_full_pipeline(self):
        """Full pipeline: load -> split -> convert (rules) -> validate."""
        text = load_document(str(FIXTURES_DIR / "chapters.txt"))
        chapters = split_into_chapters(text)
        assert len(chapters) >= 2

        config = ConversionConfig(mode="rules")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel(chapters, title="Rules Full")

        fountain = generate_fountain(screenplay)
        validator = FountainValidator()
        result = validator.validate(fountain)

        # Must have no critical structural errors
        critical = {"E1", "E3", "E8", "E9"}
        critical_errs = [e for e in result["errors"] if e["code"] in critical]
        assert len(critical_errs) == 0, f"Critical errors: {critical_errs}"

    def test_convert_file_rules_mode(self, tmp_path):
        """convert_file works with rules mode on a real file."""
        # Create a temp text file
        input_path = tmp_path / "input.txt"
        input_path.write_text(
            "Chapter 1: The Start\n\n"
            "It was the beginning of something new.\n\n"
            "Chapter 2: The Journey\n\n"
            "They set off at dawn.",
            encoding="utf-8",
        )

        screenplay, fountain_text = convert_file(
            str(input_path), mode="rules", title="File Convert"
        )
        assert screenplay is not None
        assert fountain_text, "Fountain text must not be empty"
        assert len(screenplay.scenes) > 0

    def test_empty_text_rules_mode(self):
        """Rules mode handles empty text gracefully."""
        screenplay = convert("", mode="rules")
        assert screenplay is not None
        assert len(screenplay.scenes) == 0
        assert len(screenplay.elements) == 0

    def test_single_paragraph_rules_mode(self):
        """Rules mode handles a single paragraph."""
        screenplay = convert(
            "He walked into the room and sat down.",
            mode="rules",
            title="Single Para",
        )
        assert screenplay is not None
        assert len(screenplay.scenes) >= 1


# =========================================================================
# 7. Edge Cases and Error Handling
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
        config = ConversionConfig(mode="rules")
        converter = ScreenplayConverter(config)
        screenplay = converter.convert_novel([], title="Empty")
        assert screenplay.scenes == []
        assert screenplay.elements == []
