# Travel Chronicle: Audio Processing Pipeline

## Project Overview

A Python script that processes audio exports from the Red Button app, analyzing each clip to extract transcripts, timestamps, speaker identification, and audio descriptions—all in preparation for episode generation.

**Input:** ZIP file exported from the Red Button app
**Output:** Enriched metadata with transcripts, timestamps, and audio analysis

## Tech Stack

- **Python 3.9+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager (replaces pip + venv)
- **OpenAI gpt-4o-transcribe-diarize** — transcription with speaker diarization (uses voice references)
- **Google Gemini 3 Flash** — audio analysis (audioType, audioEvents, sceneDescription, emotionalTone)
- **python-dotenv** — for loading API keys from .env file

### Hybrid Pipeline Architecture

The pipeline uses a hybrid approach combining two AI services:

```
┌─────────────────────────────────────────────────────────────┐
│                      Audio Clip                              │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────┐
│  OpenAI gpt-4o-transcribe│     │  Gemini 3 Flash             │
│  -diarize                │     │                             │
│                         │     │  - audioType                │
│  - transcript[]         │     │  - audioEvents[]            │
│    (with speakers)      │     │  - sceneDescription         │
│                         │     │  - emotionalTone            │
└─────────────────────────┘     └─────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Combined Result                            │
└─────────────────────────────────────────────────────────────┘
```

**Why hybrid?** OpenAI's transcription model provides superior speaker diarization with explicit voice reference support, while Gemini excels at scene understanding and audio event detection.

## File Structure

```
travel-chronicle-pipeline/
├── process.py              # Main entry point (orchestrates both APIs)
├── analyze.py              # Gemini audio analysis (non-transcript)
├── transcribe.py           # OpenAI transcription with speaker diarization
├── audio_utils.py          # Audio file utilities
├── utils.py                # Helper functions (ZIP, JSON)
├── tests/                  # Test suite (128 tests, 92% coverage)
│   ├── conftest.py         # Shared test fixtures
│   ├── test_utils.py       # Tests for utils.py
│   ├── test_analyze.py     # Tests for analyze.py
│   ├── test_process.py     # Tests for process.py
│   ├── test_audio_utils.py # Tests for audio_utils.py
│   └── test_transcribe.py  # Tests for transcribe.py (TODO)
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
- Current coverage: 92% (128 tests)
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
OPENAI_API_KEY=sk-...
```

Both API keys are required for the hybrid pipeline:
- **GEMINI_API_KEY**: For audio analysis (audioType, audioEvents, sceneDescription, emotionalTone)
- **OPENAI_API_KEY**: For transcription with speaker diarization

## Input Format

ZIP file structure from Travel Chronicle app:
```
trip-name.zip
├── metadata.json
├── audio/
│   ├── clip_001.webm (or .m4a on iOS)
│   ├── clip_002.webm
│   └── ...
└── voice_references/
    ├── ellen.webm
    ├── dad.webm
    └── ...
```

metadata.json structure:
```json
{
  "trip": {
    "id": "trip_abc123",
    "name": "Puerto Rico Dec 2024",
    "createdAt": "2024-12-27T10:00:00Z",
    "exportedAt": "2025-01-02T18:00:00Z",
    "status": "active",
    "talent": [
      {
        "name": "Ellen",
        "age": 7,
        "voiceReferenceFile": "voice_references/ellen.webm"
      },
      {
        "name": "Dad",
        "age": null,
        "voiceReferenceFile": null
      }
    ]
  },
  "clips": [
    {
      "id": "clip_xyz789",
      "filename": "audio/clip_001.webm",
      "recordedAt": "2024-12-28T14:34:22Z",
      "durationSeconds": 34,
      "mimeType": "audio/webm",
      "location": {
        "lat": 18.2731,
        "lng": -65.7877,
        "placeName": "La Mina Falls, El Yunque",
        "accuracy": 10
      },
      "highlights": [
        { "timestampSeconds": 12 },
        { "timestampSeconds": 28 }
      ],
      "storyBeatId": "storybeat_abc123"
    }
  ],
  "storyBeats": [
    {
      "id": "storybeat_abc123",
      "location": "La Mina Falls, Puerto Rico",
      "text": "Once upon a time at La Mina Falls...",
      "starred": true,
      "createdAt": "2024-12-28T15:00:00Z"
    }
  ]
}
```

Key fields:
- `talent[].voiceReferenceFile`: Per-traveler voice reference path (can be `null`)
- `talent[].age`: Can be a number or `null`
- `clips[].storyBeatId`: References a story beat by ID (can be `null`)
- `storyBeats[]`: Separate array of story beats with `id`, `text`, and `starred` status

## Output Format

Enriched metadata.json:
```json
{
  "trip": { ... },
  "clips": [
    {
      "id": "clip_xyz789",
      "filename": "audio/clip_001.webm",
      "recordedAt": "2024-12-28T14:34:22Z",
      "durationSeconds": 34,
      "location": { ... },
      "highlights": [ ... ],
      "storyBeatId": "storybeat_abc123",
      "storyBeat": {
        "id": "storybeat_abc123",
        "text": "Once upon a time at La Mina Falls...",
        "starred": true
      },
      "analysis": {
        "audioType": "speech",
        "transcript": [
          { "timestamp": "00:02", "speaker": "Ellen", "text": "Can we go swimming?" },
          { "timestamp": "00:05", "speaker": "Mom", "text": "No, it's too cold!" },
          { "timestamp": "00:08", "speaker": "Ellen", "text": "Watch me!" }
        ],
        "audioEvents": [
          { "timestamp": "00:00", "event": "waterfall rushing in background" },
          { "timestamp": "00:07", "event": "splashing water" },
          { "timestamp": "00:10", "event": "laughter" }
        ],
        "sceneDescription": "A family is at a waterfall. A child asks to swim while an adult warns about the cold water.",
        "emotionalTone": "playful"
      }
    }
  ],
  "storyBeats": [ ... ]
}
```

Key additions:
- `clips[].storyBeat`: Resolved story beat with `id`, `text`, and `starred` status
- `clips[].analysis`: All Gemini analysis results grouped under `analysis` key
- Speaker names use actual traveler names when voice references are provided

## Core Functions

The pipeline uses two core functions for the hybrid approach:

### transcribe_with_diarization() - OpenAI

Transcribes audio with speaker identification using voice references:

```python
from openai import OpenAI

def transcribe_with_diarization(
    clip_path: Path,
    voice_references: list[tuple[dict, Path]],
    api_key: str,
) -> dict:
    """
    Transcribe with speaker diarization using OpenAI.
    Returns: transcript with speaker names matched to voice references
    """
    client = OpenAI(api_key=api_key)

    # Encode voice references as base64 data URLs
    known_speaker_names = [t["name"] for t, _ in voice_references]
    known_speaker_references = [encode_audio_as_data_url(p) for _, p in voice_references]

    with open(clip_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe-diarize",
            file=audio_file,
            response_format="json",
            extra_body={
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
                "known_speaker_names": known_speaker_names,
                "known_speaker_references": known_speaker_references,
            },
        )

    # Returns {"transcript": [{"timestamp": "00:05", "speaker": "Anne", "text": "..."}]}
```

### analyze_audio() - Gemini

Analyzes audio for scene understanding (no transcript):

```python
from google import genai

def analyze_audio(audio_path: str, api_key: str, context: dict = None) -> dict:
    """
    Analyze audio using Gemini.
    Returns: audioType, audioEvents, sceneDescription, emotionalTone
    (Transcript is handled separately by OpenAI)
    """
    client = genai.Client(api_key=api_key)

    # Upload and analyze
    uploaded_file = client.files.upload(file=audio_file)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[uploaded_file, prompt]
    )

    # Returns {"audioType": "speech", "audioEvents": [...], ...}
```

### process_single_clip() - Orchestrator

Combines both APIs for each clip:

```python
def process_single_clip(clip, audio_path, context, api_keys, voice_references, ...):
    # Step 1: Transcribe with OpenAI (speaker diarization)
    if voice_references:
        transcription = transcribe_with_diarization(audio_path, voice_references, api_keys.openai)
    else:
        transcription = transcribe_without_diarization(audio_path, api_keys.openai)

    # Step 2: Analyze with Gemini (scene understanding)
    analysis = analyze_audio(str(audio_path), api_keys.gemini, context=context)

    # Step 3: Merge results
    clip["analysis"] = {
        "audioType": analysis["audioType"],
        "transcript": transcription["transcript"],  # From OpenAI
        "audioEvents": analysis["audioEvents"],
        "sceneDescription": analysis["sceneDescription"],
        "emotionalTone": analysis["emotionalTone"],
    }
```

## Pipeline Steps

```
1. EXTRACT ZIP
   └── Unzip to output directory

2. LOAD METADATA
   ├── Parse metadata.json
   ├── Build story beats lookup by ID
   └── Load per-traveler voice references

3. LOAD VOICE REFERENCES (once)
   └── Encode each traveler's voice reference as base64 data URL for OpenAI

4. FOR EACH CLIP:
   ├── Print progress: "Processing clip 1/10: audio/clip_001.webm"
   ├── Build context (travelers, location, story beat)
   ├── Call OpenAI transcribe_with_diarization() with voice references
   ├── Call Gemini analyze_audio() for scene analysis
   ├── Merge transcript (OpenAI) with analysis (Gemini)
   ├── Resolve story beat ID to full object
   └── Add results to clip metadata

5. SAVE OUTPUT
   └── Write enriched_metadata.json

6. PRINT SUMMARY
   ├── "Processed 10 clips: 7 speech, 2 ambient, 1 mixed"
   ├── "Story Beats: 5 (2 starred)"
   └── "Voice references found: Ellen, Mom (2/4 travelers)"
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

The hybrid pipeline uses both OpenAI and Gemini APIs:

**OpenAI (Transcription):**
- gpt-4o-transcribe-diarize: ~$0.006/min
- 30 second clip = ~$0.003
- 50 clips = ~$0.15

**Gemini (Analysis):**
- Gemini 3 Flash: ~$0.001 per clip
- 50 clips = ~$0.05

**Total estimate:** ~$0.20 for 50 clips (30 seconds average)

Note: Voice references are encoded as base64 and sent with each transcription request, which may slightly increase costs.

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
