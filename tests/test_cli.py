"""Tests for the cosmic-script CLI."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, PropertyMock, patch

import pytest
from typer.testing import CliRunner

from cosmic_script.cli import app

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def temp_txt_file():
    """Create a temporary .txt file for testing."""
    with tempfile.NamedTemporaryFile(
        suffix=".txt", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("Test story content.\n\nChapter 1\n\nIt was dark.")
        tmp_path = f.name
    yield Path(tmp_path)
    if Path(tmp_path).exists():
        Path(tmp_path).unlink()


@pytest.fixture
def temp_fountain_file():
    """Create a temporary valid .fountain file."""
    content = (
        "Title:\n    Test Screenplay\nAuthor:\n    Test Author\n\n"
        "INT. HOUSE - DAY\n\nJohn enters.\n\nJOHN\nHello!\n\n"
        "EXT. STREET - NIGHT\n\nIt is dark.\n\n"
    )
    with tempfile.NamedTemporaryFile(
        suffix=".fountain", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        tmp_path = f.name
    yield Path(tmp_path)
    if Path(tmp_path).exists():
        Path(tmp_path).unlink()


@pytest.fixture
def temp_empty_fountain_file():
    """Create a temporary empty .fountain file."""
    with tempfile.NamedTemporaryFile(
        suffix=".fountain", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        tmp_path = f.name
    yield Path(tmp_path)
    if Path(tmp_path).exists():
        Path(tmp_path).unlink()


# ── Convert command ───────────────────────────────────────────────────────


class TestConvertCommand:
    """Tests for the `convert` subcommand."""

    # ── Happy path ──────────────────────────────────────────

    def test_convert_basic(self, temp_txt_file):
        """Happy path: basic conversion with minimal args."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Test story content.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ) as mock_exp:
                mock_conv.return_value = MagicMock()
                mock_exp.return_value = "Fountain content"

                result = runner.invoke(app, ["convert", str(temp_txt_file)])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output_path = temp_txt_file.with_suffix(".fountain")
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert content == "Fountain content"
        output_path.unlink()

    def test_convert_custom_output(self, temp_txt_file):
        """Happy path: custom output path via --output."""
        with tempfile.NamedTemporaryFile(
            suffix=".fountain", mode="w", delete=False, encoding="utf-8"
        ) as f:
            custom_output = f.name

        try:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                with patch(
                    "cosmic_script.cli._load_document",
                    return_value="Test story.",
                ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                    "cosmic_script.cli._export_fountain"
                ) as mock_exp:
                    mock_conv.return_value = MagicMock()
                    mock_exp.return_value = "Custom output content"

                    result = runner.invoke(
                        app,
                        [
                            "convert",
                            str(temp_txt_file),
                            "--output",
                            custom_output,
                        ],
                    )

            assert result.exit_code == 0
            assert Path(custom_output).exists()
            content = Path(custom_output).read_text(encoding="utf-8")
            assert content == "Custom output content"
        finally:
            Path(custom_output).unlink()

    def test_convert_with_all_options(self, temp_txt_file):
        """Happy path: all options specified."""
        with tempfile.NamedTemporaryFile(
            suffix=".out", mode="w", delete=False, encoding="utf-8"
        ) as f:
            custom_output = f.name

        try:
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ) as mock_exp:
                mock_conv.return_value = MagicMock()
                mock_exp.return_value = "Result"

                result = runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--output",
                        custom_output,
                        "--format",
                        "txt",
                        "--model",
                        "gemini/gemini-2.0-pro",
                        "--api-key",
                        "test-key-123",
                        "--title",
                        "My Story",
                        "--author",
                        "John Doe",
                    ],
                )

            assert result.exit_code == 0
            assert Path(custom_output).exists()
            Path(custom_output).unlink()
        finally:
            if Path(custom_output).exists():
                Path(custom_output).unlink()

    def test_convert_custom_title(self, temp_txt_file):
        """Happy path: custom title passed to conversion."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--title",
                        "My Custom Title",
                    ],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("title") == "My Custom Title"

    def test_convert_custom_author(self, temp_txt_file):
        """Happy path: custom author passed to conversion."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--author",
                        "Jane Doe",
                    ],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("author") == "Jane Doe"

    def test_convert_default_author(self, temp_txt_file):
        """Invariant: default author is 'AI Adaptation'."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    ["convert", str(temp_txt_file)],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("author") == "AI Adaptation"

    # ── API key ─────────────────────────────────────────────

    def test_convert_api_key_from_env(self, temp_txt_file):
        """Input variation: API key read from GEMINI_API_KEY env var."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key-456"}, clear=False):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    ["convert", str(temp_txt_file)],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("api_key") == "env-key-456"

    def test_convert_api_key_precedence(self, temp_txt_file):
        """Invariant: --api-key flag overrides GEMINI_API_KEY env var."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=False):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--api-key",
                        "flag-key",
                    ],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("api_key") == "flag-key"

    # ── Error path ──────────────────────────────────────────

    def test_convert_missing_input(self):
        """Error path: non-existent input file prints error."""
        result = runner.invoke(app, ["convert", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_convert_no_api_key(self, temp_txt_file):
        """Error path: no API key provided shows helpful message."""
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(
                app,
                ["convert", str(temp_txt_file)],
            )
            assert result.exit_code != 0
            assert "API key" in result.stdout

    def test_convert_load_error(self, temp_txt_file):
        """Error path: file loading raises handled error."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                side_effect=FileNotFoundError("File not found"),
            ):
                result = runner.invoke(app, ["convert", str(temp_txt_file)])
                assert result.exit_code != 0

    def test_convert_conversion_error(self, temp_txt_file):
        """Error path: LLM conversion error handled gracefully."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch(
                "cosmic_script.cli._run_conversion",
                side_effect=RuntimeError("LLM API error"),
            ):
                result = runner.invoke(app, ["convert", str(temp_txt_file)])
                assert result.exit_code != 0

    # ── Output format ───────────────────────────────────────

    def test_convert_txt_format(self, temp_txt_file):
        """Input variation: --format txt produces .txt output."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ) as mock_exp:
                mock_conv.return_value = MagicMock()
                mock_exp.return_value = "Plain text output"

                result = runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--format",
                        "txt",
                    ],
                )

            assert result.exit_code == 0
            expected = temp_txt_file.with_suffix(".txt")
            assert expected.exists()
            expected.unlink()

    def test_convert_default_format(self, temp_txt_file):
        """Invariant: default output format is fountain."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ) as mock_exp:
                mock_conv.return_value = MagicMock()
                mock_exp.return_value = "Fountain content"
                result = runner.invoke(app, ["convert", str(temp_txt_file)])
                assert result.exit_code == 0
                expected = temp_txt_file.with_suffix(".fountain")
                assert expected.exists()
                expected.unlink()

    def test_convert_default_model(self, temp_txt_file):
        """Invariant: default model is gemini/gemini-2.5-flash."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "DEMO_MODE": "false"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(app, ["convert", str(temp_txt_file)])
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("model") == "gemini/gemini-2.5-flash"

    def test_convert_custom_model(self, temp_txt_file):
        """Input variation: custom model passed to conversion."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "DEMO_MODE": "false"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(
                    app,
                    [
                        "convert",
                        str(temp_txt_file),
                        "--model",
                        "anthropic/claude-sonnet-4",
                    ],
                )
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                assert kwargs.get("model") == "anthropic/claude-sonnet-4"

    # ── Default title from filename ─────────────────────────

    def test_convert_title_from_filename(self, temp_txt_file):
        """Invariant: default title is derived from filename."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch(
                "cosmic_script.cli._load_document",
                return_value="Story.",
            ), patch("cosmic_script.cli._run_conversion") as mock_conv, patch(
                "cosmic_script.cli._export_fountain"
            ):
                runner.invoke(app, ["convert", str(temp_txt_file)])
                mock_conv.assert_called_once()
                kwargs = mock_conv.call_args.kwargs
                expected_title = temp_txt_file.stem.replace("_", " ").replace("-", " ").strip().title()
                assert kwargs.get("title") == expected_title


# ── Validate command ──────────────────────────────────────────────────────


class TestValidateCommand:
    """Tests for the `validate` subcommand."""

    def test_validate_valid(self, temp_fountain_file):
        """Happy path: valid fountain file reports no errors."""
        result = runner.invoke(app, ["validate", str(temp_fountain_file)])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower() or "no errors" in result.stdout.lower()

    def test_validate_empty_file(self, temp_empty_fountain_file):
        """Boundary: empty fountain file shows warning."""
        result = runner.invoke(app, ["validate", str(temp_empty_fountain_file)])
        assert result.exit_code == 0

    def test_validate_missing_file(self):
        """Error path: non-existent file prints error."""
        result = runner.invoke(app, ["validate", "missing.fountain"])
        assert result.exit_code != 0

    def test_validate_non_fountain_ext(self):
        """Input variation: .txt file treated as invalid fountain."""
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("Just some text.")
            tmp_path = f.name
        try:
            result = runner.invoke(app, ["validate", tmp_path])
            assert result.exit_code in (0, 1)
        finally:
            Path(tmp_path).unlink()


# ── Info command ──────────────────────────────────────────────────────────


class TestInfoCommand:
    """Tests for the `info` subcommand."""

    def test_info_txt_file(self, temp_txt_file):
        """Happy path: show info for a plain text file."""
        result = runner.invoke(app, ["info", str(temp_txt_file)])
        assert result.exit_code == 0
        assert "txt" in result.stdout.lower()
        assert str(temp_txt_file.name) in result.stdout

    def test_info_fountain_file(self, temp_fountain_file):
        """Happy path: show info for a fountain file with scenes."""
        result = runner.invoke(app, ["info", str(temp_fountain_file)])
        assert result.exit_code == 0
        out = result.stdout.lower()
        assert "fountain" in out
        # "scene" appears if screenplay-tools is installed, or "parse" if not
        assert "scene" in out or "parse" in out

    def test_info_empty_fountain(self, temp_empty_fountain_file):
        """Boundary: show info for an empty fountain file."""
        result = runner.invoke(app, ["info", str(temp_empty_fountain_file)])
        assert result.exit_code == 0

    def test_info_missing_file(self):
        """Error path: non-existent file prints error."""
        result = runner.invoke(app, ["info", "missing.txt"])
        assert result.exit_code != 0

    def test_info_file_size_displayed(self, temp_txt_file):
        """Invariant: file size is shown in output."""
        result = runner.invoke(app, ["info", str(temp_txt_file)])
        assert result.exit_code == 0
        assert "size" in result.stdout.lower() or "bytes" in result.stdout.lower()
