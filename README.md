# Cosmic Script

Convert free-form text stories into proper screenplay format.

## What It Does

Cosmic Script takes your novel, short story, or any free-form text and transforms it into a properly formatted screenplay using the industry-standard Fountain format.

### Features

- **Multi-format input**: Supports .txt, .md, .pdf, and .epub files
- **Smart chapter detection**: Automatically detects chapter boundaries using multiple patterns
- **Character tracking**: Maintains character registry across chapters for consistency
- **Fountain output**: Generates industry-standard Fountain screenplay format
- **Validation**: 15-point validation catches format errors before export
- **CLI interface**: Simple command-line tool for quick conversions

## Installation

```bash
pip install -e .
```

Or install dependencies manually:

```bash
pip install typer litellm screenplay-tools rapidfuzz pymupdf ebooklib pydantic rich
```

## Usage

### Convert a Novel to Screenplay

```bash
cosmic-script convert novel.txt --output screenplay.fountain
```

### Convert with Options

```bash
cosmic-script convert novel.pdf \
  --output screenplay.fountain \
  --title "My Screenplay" \
  --author "John Doe" \
  --model gemini/gemini-1.5-flash \
  --api-key YOUR_API_KEY
```

### Validate a Fountain File

```bash
cosmic-script validate screenplay.fountain
```

### Get File Info

```bash
cosmic-script info screenplay.fountain
```

## Configuration

### API Key

Set your Gemini API key via environment variable:

```bash
export GEMINI_API_KEY=your_api_key_here
```

Or pass it directly:

```bash
cosmic-script convert novel.txt --api-key YOUR_KEY
```

### Model Selection

Default model is `gemini/gemini-1.5-flash`. You can use other models:

```bash
cosmic-script convert novel.txt --model gemini/gemini-1.5-pro
```

## How It Works

1. **Ingestion**: Loads your text file and extracts plain content
2. **Chapter Detection**: Splits text into chapters using regex patterns
3. **LLM Conversion**: Processes each chapter through Gemini, converting prose to screenplay format
4. **Character Registry**: Tracks characters across chapters for consistency
5. **Fountain Export**: Generates valid Fountain markup
6. **Validation**: Checks for format errors and provides fixes

## Screenplay Format

Cosmic Script generates standard screenplay format:

```
INT. COFFEE SHOP - DAY

Sarah sits at a corner table, stirring her coffee nervously.

SARAH
I can't believe you said that.

She doesn't look up from her phone.

JOHN (V.O.)
I didn't mean it like that.

CUT TO:
```

## Architecture

```
cosmic_script/
├── cli.py              # Typer CLI interface
├── models.py           # Pydantic data models
├── ingestion/          # Text loading and chapter detection
│   ├── loader.py       # Multi-format document loader
│   └── chapterizer.py  # Chapter pattern detection
├── conversion/         # LLM-powered conversion
│   ├── converter.py    # Main conversion logic
│   ├── registry.py     # Character state management
│   └── prompts.py      # LLM prompt templates
└── export/             # Output generation
    ├── fountain.py     # Fountain format generator
    ├── validator.py    # Deterministic validation
    └── exporter.py     # Multi-format export
```

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Test Coverage

- 187 tests covering all modules
- Models, ingestion, conversion, export, CLI, validation

## License

MIT License
