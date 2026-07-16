# Cosmic Script

> Transform narratives into screenplays with AI.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-439%20passing-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Cosmic Script converts novels, short stories, and free-form text into industry-standard **Fountain** screenplay format using LLMs. It features automatic chapter detection, character tracking, genre-aware conversion, and a professional web interface.

---

## Features

### Core Pipeline
- **Multi-format input** — `.txt`, `.md`, `.pdf`, `.epub`, `.docx`, `.fountain`
- **Smart chapter detection** — Arabic numerals, Roman numerals, "Part" patterns, markdown headings
- **Character registry** — fuzzy matching with dialogue-tag detection, tracks characters across chapters
- **Fountain 1.1 output** — scene headings, action, dialogue, parentheticals, transitions, centered text, sections, synopses, lyrics, page breaks

### AI-Powered
- **Prompt engineering** — role-defined system prompt with few-shot examples, anti-patterns, and character formatting rules (~2300 tokens)
- **Genre/tonal control** — 8 presets: classic, modern, tarantino, noir, comedy, horror, action, drama
- **Self-healing pipeline** — validates LLM output, retries with error context if validation fails
- **Content-hash LLM cache** — SQLite-backed, SHA256 key, 24h TTL, saves API costs during iteration
- **Multi-model fallback** — Google AI Studio → 8 OpenRouter free models with automatic fallback

### Analysis
- **Script coverage AI** — logline, synopsis, strengths, weaknesses, rating, recommendation
- **Logline generator** — 25-50 word logline from converted screenplay
- **Character voice analysis** — per-character line count, vocabulary richness, speaking style, emotional tone
- **Scene pacing analysis** — dialogue ratio, pacing score, issues, and recommendations per scene

### Export
- **Fountain** — industry-standard `.fountain` files
- **PDF** — US Letter, Courier 12pt, title page, page numbers, (CONT'D)/(MORE) markers
- **Plain text** — `.txt` export
- **Page count estimation** — ~55 lines = 1 page, with confidence levels
- **Validation** — 20-point checks (E1-E20) covering format errors and warnings

### Web Interface
- **React/Vite frontend** — cinematic screenplay-first design with dark mode
- **FastAPI backend** — REST API with analysis, conversion, and export endpoints
- **Step indicator** — visual pipeline progress (Upload → Configure → Result)
- **Syntax highlighting** — color-coded Fountain elements in preview
- **Copy to clipboard** — one-click copy of raw Fountain text
- **Download** — `.fountain` and `.txt` export from browser

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Mariakevin/cosmic-script.git
cd cosmic-script

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# Install in development mode
pip install -e .
```

---

## Quick Start

### Convert a novel to screenplay

```bash
cosmic-script convert sample_story.txt --output screenplay.fountain
```

### Convert with options

```bash
cosmic-script convert novel.pdf \
  --output screenplay.fountain \
  --title "My Screenplay" \
  --author "Your Name" \
  --genre tarantino \
  --model gemini/gemini-2.5-flash
```

### Demo mode (no API key needed)

```bash
DEMO_MODE=true cosmic-script convert sample_story.txt
```

### Validate a Fountain file

```bash
cosmic-script validate screenplay.fountain
```

### Get file info

```bash
cosmic-script info screenplay.fountain
```

---

## Web Interface

Start both the backend and frontend:

```bash
# Terminal 1: Backend
uvicorn cosmic_script.web.app:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Or use the convenience script:

```bash
run-dev.bat  # Windows
```

Then open [http://localhost:5173](http://localhost:5173).

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload and parse a document |
| `POST` | `/api/chapters` | Extract chapters from text |
| `POST` | `/api/convert` | Convert text to screenplay |
| `POST` | `/api/characters` | Extract character registry |
| `POST` | `/api/export` | Export screenplay to format |
| `POST` | `/api/validate` | Validate Fountain output |
| `POST` | `/api/coverage` | Generate script coverage |
| `POST` | `/api/logline` | Generate logline |
| `GET`  | `/api/estimate` | Estimate page count |
| `GET`  | `/api/genres` | List genre presets |
| `GET`  | `/api/models` | List available models |

---

## Configuration

### API Keys

Set environment variables in `.env`:

```bash
GEMINI_API_KEY=your_google_ai_key
OPENROUTER_API_KEY=your_openrouter_key
```

Or pass directly:

```bash
cosmic-script convert novel.txt --api-key YOUR_KEY
```

### Model Selection

Default chain tries Google AI Studio first, then falls back to OpenRouter free models:

```bash
cosmic-script convert novel.txt --model gemini/gemini-2.5-flash
cosmic-script convert novel.txt --model openrouter/meta-llama/llama-3.3-70b-instruct:free
```

### Genre Styles

```bash
cosmic-script convert novel.txt --genre tarantino
cosmic-script convert novel.txt --genre noir
cosmic-script convert novel.txt --genre comedy
```

Available: `classic`, `modern`, `tarantino`, `noir`, `comedy`, `horror`, `action`, `drama`

---

## Architecture

```
cosmic_script/
├── cli.py                  # Typer CLI interface
├── models.py               # Pydantic data models
├── ingestion/              # Text loading and chapter detection
│   ├── loader.py           # Multi-format document loader
│   └── chapterizer.py      # Chapter pattern detection
├── conversion/             # LLM-powered conversion
│   ├── converter.py        # Main conversion logic + cache + self-healing
│   ├── registry.py         # Character state management
│   ├── prompts.py          # LLM prompt templates (few-shot)
│   ├── cache.py            # Content-hash LLM cache (SQLite)
│   ├── genres.py           # Genre/tonal presets
│   └── model_router.py     # Multi-provider model fallback
├── analysis/               # AI-powered analysis
│   ├── coverage.py         # Script coverage generator
│   ├── logline.py          # Logline generator
│   ├── voice.py            # Character voice analysis
│   └── pacing.py           # Scene pacing analysis
├── export/                 # Output generation
│   ├── fountain.py         # Fountain format generator
│   ├── validator.py        # 20-point validation (E1-E20)
│   ├── exporter.py         # Multi-format export
│   ├── pdf_export.py       # PDF export (fpdf2)
│   └── page_estimator.py   # Page count estimation
└── web/                    # FastAPI web interface
    ├── app.py              # Application setup
    ├── schemas.py          # Request/response models
    └── routers/            # API endpoints
        ├── conversion.py   # Convert, models, chapters
        ├── documents.py    # Upload
        ├── characters.py   # Character extraction
        ├── export.py       # Export + validation
        └── analysis.py     # Coverage, logline, estimate, genres

frontend/
├── src/
│   ├── App.tsx             # Main app with step indicator
│   ├── App.css             # Cinematic screenplay-first styles
│   ├── index.css           # Design system (Playfair + DM Sans)
│   ├── components/
│   │   ├── FileUpload.tsx       # Drag-and-drop upload
│   │   ├── StoryPreview.tsx     # File stats + text preview
│   │   ├── ChapterList.tsx      # Detected chapters
│   │   ├── ConversionPanel.tsx  # Conversion settings
│   │   ├── FountainPreview.tsx  # Syntax-highlighted output
│   │   └── CharacterRegistry.tsx # Character cards
│   ├── api/client.ts       # API client
│   └── types/index.ts      # TypeScript interfaces
└── package.json
```

---

## Screenplay Format Example

```
INT. COFFEE SHOP - DAY

Sarah sits at a corner table, stirring her coffee nervously.

SARAH
(quietly)
I can't believe you said that.

She doesn't look up from her phone.

JOHN (V.O.)
I didn't mean it like that.

CUT TO:
```

---

## Development

### Run tests

```bash
pytest tests/ -v
```

### Run tests with coverage

```bash
pytest tests/ --cov=cosmic_script --cov-report=term-missing
```

### Test count

**439 tests** covering: models, ingestion, conversion, export, CLI, validation, analysis, web API, genres, PDF export, page estimation, voice analysis, pacing analysis.

---

## Roadmap

- [ ] Streaming/SSE progress for LLM calls
- [ ] FDX (Final Draft) import/export
- [ ] Three-act structure mapping
- [ ] Continuity checker
- [ ] Table read mode (TTS)
- [ ] Real-time collaboration (WebSocket + CRDT)

---

## License

MIT License
