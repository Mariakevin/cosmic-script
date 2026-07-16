"""CLI for cosmic-script screenplay converter.

Provides three subcommands:
  - convert:  Convert a free-form text story into Fountain screenplay format
  - validate: Validate a Fountain file for correctness
  - info:     Display metadata about a story or screenplay file
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.progress import Progress, TextColumn
from rich.table import Table

# Load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from cosmic_script import __version__
from cosmic_script.models import Screenplay

app = typer.Typer(
    name="cosmic-script",
    help="Convert free-form text stories into proper screenplay format.",
    no_args_is_help=True,
)
console = Console(force_terminal=True)

# ── Internal helpers (wired to pipeline modules) ──────────────────────────


def _load_document(path: str) -> str:
    """Load text content from *path* using the ingestion pipeline.

    Delegates to ``cosmic_script.ingestion.loader.load_document``.
    """
    try:
        from cosmic_script.ingestion.loader import load_document

        return load_document(path)
    except ImportError:
        # Fallback: read raw file when ingestion module not yet available
        return Path(path).read_text(encoding="utf-8")


def _run_conversion(
    text: str,
    *,
    model: str,
    api_key: str,
    title: str,
    author: str,
    genre: str | None = None,
) -> Screenplay:
    """Run LLM-based conversion via the conversion pipeline.

    Returns a ``Screenplay`` object.
    """
    from cosmic_script.conversion.pipeline import convert

    return convert(  # type: ignore[return-value]
        text=text,
        model=model,
        api_key=api_key,
        title=title,
        author=author,
        genre=genre,
    )


def _export_fountain(screenplay: Screenplay) -> str:
    """Export a screenplay object to Fountain-formatted text."""
    from cosmic_script.export.fountain import generate_fountain

    return generate_fountain(screenplay)


# ── Shared utilities ──────────────────────────────────────────────────────


def _resolve_api_key(provided: Optional[str]) -> str:
    """Return the API key from *provided* or ``GEMINI_API_KEY``."""
    key = provided or os.environ.get("GEMINI_API_KEY")
    if not key:
        console.print(
            "[red]Error:[/] No API key found. "
            "Provide --api-key or set the [bold]GEMINI_API_KEY[/] environment variable."
        )
        raise typer.Exit(code=1)
    return key


def _default_title(path: Path) -> str:
    """Derive a readable title from a filename."""
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def _format_size(num_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def _detect_encoding(path: Path) -> str:
    """Detect text file encoding heuristically."""
    import locale

    # Read a small sample and try common encodings
    raw = path.read_bytes()[:4096]
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return locale.getpreferredencoding()


# ── Fountain validation helpers ───────────────────────────────────────────


def _parse_fountain(text: str) -> object:
    """Parse Fountain text and return a ``Script`` object.

    Requires the optional ``screenplay-tools`` package. Raises ImportError
    if the package is not installed.
    """
    try:
        from screenplay_tools.fountain.parser import Parser
    except ImportError as exc:
        raise ImportError(
            "screenplay-tools is required for advanced validation. "
            "Install it with: pip install screenplay-tools"
        ) from exc

    parser = Parser()
    parser.add_text(text)
    parser.finalize()
    return parser.script


def _validate_fountain(text: str) -> List[dict]:
    """Run validation checks on Fountain text using FountainValidator.

    Delegates to the canonical ``FountainValidator`` instead of
    duplicating validation logic. Returns a list of dicts with keys
    ``severity``, ``line``, ``message`` for CLI display.
    """
    from cosmic_script.export.validator import FountainValidator

    validator = FountainValidator()
    result = validator.validate(text)

    issues: List[dict] = []
    for error in result["errors"]:
        issues.append({
            "severity": "error",
            "line": error.get("line", 0),
            "message": f"{error['code']}: {error['message']}",
        })
    for warning in result.get("warnings", []):
        issues.append({
            "severity": "warning",
            "line": warning.get("line", 0),
            "message": warning.get("message", ""),
        })
    return issues


# ── Commands ──────────────────────────────────────────────────────────────


@app.command()
def convert(
    input_file: Path = typer.Argument(
        ...,
        help="Input story file (.txt, .md, etc.)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: input filename with new extension)",
    ),
    format: str = typer.Option(
        "fountain",
        "--format",
        "-f",
        help="Output format (fountain, txt)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Gemini API key (can also use GEMINI_API_KEY env var)",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Screenplay title (default: derived from filename)",
    ),
    author: str = typer.Option(
        "AI Adaptation",
        "--author",
        "-a",
        help="Screenplay author name",
    ),
    genre: Optional[str] = typer.Option(
        None,
        "--genre",
        "-g",
        help="Genre preset (classic, modern, tarantino, noir, comedy, horror, action, drama)",
    ),
) -> None:
    """Convert a free-form story into Fountain screenplay format.

    Reads INPUT_FILE, processes it through an LLM-powered conversion
    pipeline, and writes the result to the specified output.
    """
    # --- Resolve parameters ---
    resolved_title = title or _default_title(input_file)
    resolved_api_key = _resolve_api_key(api_key)

    # Determine model: demo mode overrides, otherwise auto
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    model = "demo" if demo_mode else "auto"
    if demo_mode:
        console.print("[dim]Demo mode enabled (DEMO_MODE=true)[/dim]")

    output_suffix = ".fountain" if format == "fountain" else ".txt"
    resolved_output = output or input_file.with_suffix(output_suffix)

    # --- Pipeline ---
    try:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Load
            task_load = progress.add_task(
                "[yellow]Loading file...", total=None
            )
            text = _load_document(str(input_file))
            progress.remove_task(task_load)

            # Step 2: Convert
            task_convert = progress.add_task(
                "[yellow]Converting with LLM...", total=None
            )
            screenplay = _run_conversion(
                text=text,
                model=model,
                api_key=resolved_api_key,
                title=resolved_title,
                author=author,
                genre=genre,
            )
            progress.remove_task(task_convert)

            # Step 3: Export
            task_export = progress.add_task(
                "[yellow]Exporting to Fountain...", total=None
            )
            result = _export_fountain(screenplay)
            progress.remove_task(task_export)

        # Step 4: Write
        resolved_output.write_text(result, encoding="utf-8")

    except FileNotFoundError:
        console.print(
            f"[red]Error:[/] Input file not found: [bold]{input_file}[/]"
        )
        raise typer.Exit(code=1)

    except ImportError as exc:
        console.print(
            f"[red]Error:[/] Missing pipeline module: {exc}\n"
            f"The conversion pipeline has not been fully implemented yet. "
            f"Ensure [bold]cosmic_script.ingestion.loader[/], "
            f"[bold]cosmic_script.conversion.pipeline[/], and "
            f"[bold]cosmic_script.export.fountain[/] exist and expose the "
            f"expected API."
        )
        raise typer.Exit(code=1)

    except Exception as exc:
        console.print(f"[red]Error during conversion:[/] {exc}")
        raise typer.Exit(code=1)

    else:
        console.print(
            f"[green]Success:[/] Converted [bold]{input_file.name}[/] "
            f"-> [bold]{resolved_output}[/]"
        )


@app.command()
def validate(
    input_file: Path = typer.Argument(
        ...,
        help="Fountain file to validate",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Validate a Fountain screenplay file for structural correctness.

    Returns exit code 0 if valid (warnings only), 1 if errors are found.
    """
    try:
        text = input_file.read_text(encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]Error:[/] Could not read file: {exc}")
        raise typer.Exit(code=1)

    issues = _validate_fountain(text)

    # Filter by severity
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    infos = [i for i in issues if i.get("severity") == "info"]

    if not issues:
        console.print(
            f"[green]Valid![/] No issues found in [bold]{input_file.name}[/]"
        )
        raise typer.Exit(code=0)

    # Display issues
    if errors:
        console.print(f"[red]Errors ({len(errors)}):[/]")
        for issue in errors:
            loc = f"line {issue['line']}" if issue["line"] else "file"
            console.print(f"  [red]x[/] [{loc}] {issue['message']}")
        console.print()

    if warnings:
        console.print(f"[yellow]Warnings ({len(warnings)}):[/]")
        for issue in warnings:
            loc = f"line {issue['line']}" if issue["line"] else "file"
            console.print(f"  [yellow]![/] [{loc}] {issue['message']}")
        console.print()

    if infos:
        console.print(f"[dim]Info ({len(infos)}):[/dim]")
        for issue in infos:
            loc = f"line {issue['line']}" if issue["line"] else "file"
            console.print(f"  [dim]i[/] [{loc}] {issue['message']}")
        console.print()

    if errors:
        raise typer.Exit(code=1)

    console.print(
        f"[green]Valid with warnings.[/] [bold]{input_file.name}[/] "
        f"has {len(warnings)} warning(s) and {len(infos)} info(s)."
    )
    raise typer.Exit(code=0)


@app.command()
def info(
    input_file: Path = typer.Argument(
        ...,
        help="File to inspect",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Display metadata about a story or screenplay file.

    For Fountain files, also shows scene count, character list,
    and dialogue statistics.
    """
    # Basic file info
    stat = input_file.stat()
    ext = input_file.suffix.lower()
    encoding = _detect_encoding(input_file)
    size_str = _format_size(stat.st_size)

    table = Table(title=f"File: {input_file.name}")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")

    table.add_row("Path", str(input_file.resolve()))
    table.add_row("Size", size_str)
    table.add_row("Encoding", encoding)
    table.add_row("Type", ext.upper() if ext else "Unknown")

    # Fountain-specific analysis
    if ext in (".fountain", ".sp"):
        try:
            text = input_file.read_text(encoding=encoding)
            script = _parse_fountain(text)

            # Count scenes (scene headings)
            from screenplay_tools.screenplay import ElementType

            scene_count = sum(
                1 for e in script.elements if e.type == ElementType.HEADING
            )

            # Collect character names (from CHARACTER elements)
            characters = sorted(
                set(
                    e.name
                    for e in script.elements
                    if e.type == ElementType.CHARACTER
                )
            )

            # Count dialogue blocks
            dialogue_count = sum(
                1 for e in script.elements if e.type == ElementType.DIALOGUE
            )

            # Count action lines
            action_count = sum(
                1 for e in script.elements if e.type == ElementType.ACTION
            )

            table.add_row("Scenes", str(scene_count))
            table.add_row("Dialogue blocks", str(dialogue_count))
            table.add_row("Action lines", str(action_count))

            if characters:
                table.add_row(
                    "Characters",
                    ", ".join(f"[bold]{c}[/]" for c in characters),
                )

            # Title page info
            for entry in script.titleEntries:
                label, _, value = entry.text.partition("\n")
                label = label.strip().rstrip(":")
                value = value.strip()
                if label and value:
                    table.add_row(f"Title: {label}", value)

        except Exception as exc:
            table.add_row("Parse status", f"[red]Could not parse: {exc}[/]")

    console.print(table)


# ── Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    """Typer entry point (invoked via ``cosmic-script`` console script)."""
    app()


if __name__ == "__main__":
    main()
