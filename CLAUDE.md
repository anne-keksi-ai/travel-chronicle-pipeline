# Travel Chronicle: Audio Processing Pipeline

## Project Overview

A Python script that processes audio exports from the Red Button app, analyzing each clip to extract transcripts, timestamps, speaker identification, and audio descriptions—all in preparation for episode generation.

**Input:** ZIP file exported from the Red Button app
**Output:** Enriched metadata with transcripts, timestamps, and audio analysis

## Tech Stack

- **Python 3.9+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager (replaces pip + venv)
- **Google Gemini 3 Flash** — handles everything: transcription, timestamps, speaker ID, audio description
- **python-dotenv** — for loading API keys from .env file

## File Structure

```
travel-chronicle-pipeline/
├── process.py              # Main entry point
├── analyze.py              # Gemini audio analysis
├── utils.py                # Helper functions
├── tests/                  # Test suite
│   ├── conftest.py         # Shared test fixtures
│   ├── test_utils.py       # Tests for utils.py
│   ├── test_analyze.py     # Tests for analyze.py
│   └── test_process.py     # Tests for process.py
├── pyproject.toml          # Project config & dependencies (uv)
├── uv.lock                 # Locked dependency versions
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── requirements.txt        # Legacy (deprecated, use uv)
├── .env                    # API keys (not committed)
├── .env.example            # Template for API keys
├── .gitignore
├── README.md               # User-facing documentation
└── CLAUDE.md               # This file (development notes)
```

## Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# OR: brew install uv

# Install dependencies (including dev dependencies like ruff)
uv sync
```

## Development Workflow

### Code Quality

This project uses **[ruff](https://docs.astral.sh/ruff/)** for linting and formatting.

**Run after making changes:**

```bash
# Check code for issues
uv run ruff check .

# Auto-fix issues where possible
uv run ruff check --fix .

# Format code
uv run ruff format .

# Run both check and format together
uv run ruff check --fix . && uv run ruff format .
```

Configuration is in `pyproject.toml` under `[tool.ruff]`.

### Testing

This project uses **[pytest](https://docs.pytest.org/)** for testing with comprehensive test coverage.

**Run after making changes:**

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=. --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_utils.py

# Run specific test function
uv run pytest tests/test_utils.py::TestExtractZip::test_extract_valid_zip

# Run tests excluding slow ones
uv run pytest -m "not slow"

# Run only integration tests
uv run pytest -m integration

# Run tests in parallel (faster)
uv run pytest -n auto  # requires pytest-xdist
```

**Test Structure:**

```
tests/
├── conftest.py              # Shared fixtures and test setup
├── test_utils.py            # Tests for utils.py (ZIP, JSON handling)
├── test_analyze.py          # Tests for analyze.py (audio analysis)
└── test_process.py          # Tests for process.py (main pipeline)
```

**Coverage:**
- Coverage reports are generated in HTML format at `htmlcov/index.html`
- Target: >80% code coverage
- Configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`

### Defensive Programming

This project uses multiple layers of defensive programming tools to catch bugs and security issues early.

#### Type Checking with mypy

**[mypy](https://mypy.readthedocs.io/)** performs static type checking to catch type errors before runtime.

```bash
# Check all Python files for type errors
uv run mypy .

# Check specific file
uv run mypy analyze.py

# Strict mode (more thorough)
uv run mypy --strict analyze.py
```

Configuration is in `pyproject.toml` under `[tool.mypy]`.

#### Security Scanning with bandit

**[bandit](https://bandit.readthedocs.io/)** scans code for common security issues.

```bash
# Scan all Python files
uv run bandit -r .

# Scan specific file
uv run bandit analyze.py

# Show only high severity issues
uv run bandit -r . -ll

# Generate HTML report
uv run bandit -r . -f html -o bandit-report.html
```

Configuration is in `pyproject.toml` under `[tool.bandit]`.

#### Dependency Vulnerability Scanning with pip-audit

**[pip-audit](https://pypi.org/project/pip-audit/)** checks dependencies for known security vulnerabilities.

```bash
# Check all dependencies
uv run pip-audit

# Fix vulnerabilities automatically (when possible)
uv run pip-audit --fix

# Output as JSON
uv run pip-audit --format json
```

#### Pre-commit Hooks

**[pre-commit](https://pre-commit.com/)** automatically runs checks before each git commit.

```bash
# Install hooks (one-time setup)
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files

# Run specific hook
uv run pre-commit run mypy --all-files

# Update hook versions
uv run pre-commit autoupdate
```

**Hooks configured:**
- `ruff` - Linting and formatting
- `mypy` - Type checking
- `bandit` - Security scanning
- `git-secrets` - Prevent committing secrets
- `trailing-whitespace` - Remove trailing whitespace
- `end-of-file-fixer` - Ensure files end with newline
- `check-yaml` - Validate YAML files
- `check-json` - Validate JSON files
- `check-toml` - Validate TOML files
- `check-added-large-files` - Prevent large files (>1MB)
- `detect-private-key` - Detect private keys

Configuration is in `.pre-commit-config.yaml`.

**Recommended Workflow:**

```bash
# Before committing (pre-commit runs automatically)
git add .
git commit -m "Your message"

# Or run checks manually first
uv run ruff check --fix .
uv run ruff format .
uv run mypy .
uv run bandit -r .
uv run pytest
git commit -m "Your message"
```

## Environment Variables

Create a `.env` file:
```
GEMINI_API_KEY=AI...
```

## Input Format

ZIP file structure from Red Button app:
```
export.zip
├── metadata.json
└── audio/
    ├── clip_001.m4a
    ├── clip_002.m4a
    └── ...
```

metadata.json structure:
```json
{
  "exportedAt": "2025-01-02T18:00:00Z",
  "trip": {
    "id": "trip_abc123",
    "name": "Puerto Rico Dec 2024",
    "talent": [
      { "name": "Alina", "age": 8 },
      { "name": "Ellen", "age": 7 },
      { "name": "Mom" },
      { "name": "Dad" }
    ]
  },
  "clips": [
    {
      "id": "clip_xyz789",
      "filename": "clip_001.m4a",
      "recordedAt": "2024-12-28T14:34:22Z",
      "durationSeconds": 34,
      "location": {
        "lat": 18.2731,
        "lng": -65.7877,
        "placeName": "La Mina Falls, El Yunque"
      },
      "highlights": [{ "timestampSeconds": 12 }],
      "storyBeatContext": "Story about the waterfall...",
      "storyBeatMarks": [{ "timestampSeconds": 45 }]
    }
  ]
}
```

## Output Format

Enriched metadata.json:
```json
{
  "exportedAt": "2025-01-02T18:00:00Z",
  "processedAt": "2025-01-03T10:00:00Z",
  "trip": { ... },
  "clips": [
    {
      "id": "clip_xyz789",
      "filename": "clip_001.m4a",
      "recordedAt": "2024-12-28T14:34:22Z",
      "durationSeconds": 34,
      "location": { ... },
      "highlights": [ ... ],
      "storyBeatContext": "...",
      "storyBeatMarks": [ ... ],

      "audioType": "speech",
      "transcript": [
        { "timestamp": "00:02", "speaker": "Child", "text": "Can we go swimming?" },
        { "timestamp": "00:05", "speaker": "Adult Female", "text": "No, it's too cold!" },
        { "timestamp": "00:08", "speaker": "Child", "text": "Watch me!" }
      ],
      "audioEvents": [
        { "timestamp": "00:00", "description": "waterfall rushing in background" },
        { "timestamp": "00:07", "description": "splashing water" },
        { "timestamp": "00:10", "description": "laughter" }
      ],
      "sceneDescription": "A family is at a waterfall. A child asks to swim while an adult warns about the cold water.",
      "emotionalTone": "playful, excited"
    }
  ]
}
```

## Core Function: analyze_audio()

Single Gemini call that returns everything:

```python
import google.generativeai as genai

def analyze_audio(audio_path: str, api_key: str) -> dict:
    """
    Analyze an audio clip using Gemini.
    Returns: audioType, transcript, audioEvents, sceneDescription, emotionalTone
    """
    genai.configure(api_key=api_key)

    # Upload file to Gemini
    audio_file = genai.upload_file(audio_path)

    # Analyze with Gemini
    model = genai.GenerativeModel("gemini-3-flash-preview")

    prompt = """
    Analyze this audio clip recorded during a family trip.

    Respond in this exact JSON format:
    {
      "audioType": "speech" or "ambient" or "mixed" or "music" or "silent",
      "transcript": [
        {"timestamp": "MM:SS", "speaker": "Child" or "Adult Female" or "Adult Male", "text": "what they said"}
      ],
      "audioEvents": [
        {"timestamp": "MM:SS", "description": "description of non-speech sound"}
      ],
      "sceneDescription": "1-2 sentences describing what's happening",
      "emotionalTone": "the mood (e.g., excited, peaceful, chaotic, tender)"
    }

    Rules:
    - For audioType: choose the primary type
    - For transcript: include timestamps in MM:SS format, identify speakers as Child/Adult Female/Adult Male
    - For audioEvents: note significant non-speech sounds (water, wind, laughter, music, etc.) with timestamps
    - If no speech, transcript should be an empty array []
    - If no notable audio events, audioEvents should be an empty array []

    Return ONLY valid JSON, no other text.
    """

    response = model.generate_content([audio_file, prompt])

    # Parse JSON response
    import json
    result = json.loads(response.text)

    return result
```

## Pipeline Steps

```
1. EXTRACT ZIP
   └── Unzip to temp directory

2. LOAD METADATA
   └── Parse metadata.json

3. FOR EACH CLIP:
   ├── Print progress: "Processing clip 1/10: clip_001.m4a"
   ├── Upload audio to Gemini
   ├── Call analyze_audio()
   ├── Add results to clip metadata
   └── Save progress (in case of crash)

4. SAVE OUTPUT
   └── Write enriched_metadata.json

5. PRINT SUMMARY
   └── "Processed 10 clips: 7 speech, 2 ambient, 1 mixed"
```

## Usage

```bash
# Process a ZIP file
uv run python process.py /path/to/export.zip

# Output saved to ./output/enriched_metadata.json
# Audio files extracted to ./output/audio/
```

## Error Handling

- If Gemini fails for a clip: log warning, set all analysis fields to null, continue
- If JSON parsing fails: log warning, save raw response, continue
- If audio file is corrupted: log error, skip clip
- Save progress after each clip (resume capability)

## Cost Estimates

Gemini 2.5 Flash pricing is very low:
- ~$0.001 per audio clip (30 seconds average)
- 50 clips = ~$0.05 total

Free tier: 15 requests per minute, 1 million tokens per day (more than enough)

## Development Steps

1. Project scaffolding (files, requirements, .env)
2. ZIP extraction and metadata loading
3. Single audio file analysis with Gemini (test)
4. Full pipeline with all clips
5. JSON parsing and error handling
6. Progress logging and resume capability
7. Output formatting

## Testing

Test with a small export (2-3 clips) before processing full trip data.

```bash
uv run python process.py test_export.zip
cat output/enriched_metadata.json
```

## Notes

- Gemini's Files API requires uploading the file first, then referencing it
- Files are automatically deleted after 48 hours
- For audio timestamps to work accurately, use gemini-3-flash-preview or newer
- M4A files work directly, no conversion needed
