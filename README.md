# Travel Chronicle Pipeline

AI-powered audio analysis pipeline for Travel Chronicle using a hybrid approach: **OpenAI** for transcription with speaker diarization and **Gemini 3 Flash** for scene analysis. Automatically transcribes family audio clips with speaker identification, scene descriptions, and emotional tone analysis.

[![Tests](https://img.shields.io/badge/tests-128%20passing-success)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-92%25-success)](htmlcov/)
[![Type Checked](https://img.shields.io/badge/mypy-passing-success)](pyproject.toml)
[![Security](https://img.shields.io/badge/bandit-passing-success)](pyproject.toml)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000)](https://docs.astral.sh/ruff/)

## Features

- 🎯 **Context-Aware Transcription**: Uses family member names and trip context for accurate speaker identification
- 🗣️ **Per-Traveler Voice References**: Individual voice reference files for each family member enable precise speaker identification
- 📖 **Story Beat Integration**: Links audio clips to story beats with starred favorites support
- 🌍 **Multilingual Support**: Handles multiple languages (e.g., English, Finnish) in the same audio clip
- ⏱️ **Timestamped Transcripts**: Every utterance includes precise timestamps
- 🎭 **Emotional Tone Analysis**: Detects the mood and feeling of each clip (happy, calm, excited, etc.)
- 🔊 **Audio Event Detection**: Identifies non-speech sounds (background music, laughter, ambient noise, etc.)
- 📝 **Scene Descriptions**: Generates context-aware descriptions of what's happening in each clip
- 📦 **Batch Processing**: Process entire Travel Chronicle export files at once
- 🚀 **Progress Tracking**: Real-time progress indicators with percentage completion
- 🔍 **Verbose Mode**: Optional detailed output showing full transcripts during processing

## Installation

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [OpenAI API key](https://platform.openai.com/api-keys) (for transcription)
- [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key) (for analysis)

### Setup

1. **Install uv** (if not already installed)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Or with Homebrew
   brew install uv
   ```

2. **Clone the repository**
   ```bash
   git clone https://github.com/anne-keksi-ai/travel-chronicle-pipeline.git
   cd travel-chronicle-pipeline
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Configure API key**
   ```bash
   cp .env.example .env
   # Edit .env and add your Gemini API key
   ```

## Configuration

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your API keys from:
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Gemini**: [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key)

## Usage

### Basic Usage

Process a Travel Chronicle export ZIP file:

```bash
uv run python process.py /path/to/export.zip
```

### With Voice References

For improved speaker identification, the pipeline automatically detects individual voice reference files for each traveler in the `voice_references/` folder:

```bash
# Voice references are auto-detected if present in the ZIP
uv run python process.py /path/to/export.zip
# Output: "Voice references found: Ellen, Mom, Dad (3/4 travelers)"
# Output: "Missing voice reference: Alina"
```

### Verbose Mode

Show full transcripts during processing:

```bash
uv run python process.py /path/to/export.zip --verbose
```

### Dry Run

Preview what would be processed without making API calls:

```bash
uv run python process.py /path/to/export.zip --dry-run
```

### Combined Options

```bash
uv run python process.py /path/to/export.zip --verbose --dry-run
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `zip_path` | Path to the Travel Chronicle export ZIP file (required) |
| `--verbose`, `-v` | Show full transcripts for each clip during processing |
| `--dry-run` | Preview processing without making API calls |
| `--help`, `-h` | Show help message |

**Note:** Voice references are automatically detected from the `voice_references/` folder in the export ZIP file.

## Output

The pipeline generates an `enriched_metadata.json` file in the `output/` directory with:

### For Each Audio Clip:

```json
{
  "analysis": {
    "audioType": "mixed",
    "transcript": [
      {
        "timestamp": "00:00",
        "speaker": "Anne",
        "text": "So, I was just thinking about creating some audio clips today..."
      }
    ],
    "audioEvents": [
      {
        "timestamp": "00:00",
        "event": "quiet indoor background noise"
      }
    ],
    "sceneDescription": "Anne introduces her family members and explains her plan to record their daily activities.",
    "emotionalTone": "calm"
  }
}
```

### Summary Statistics:

```
Done! Processed 5/5 clips successfully

Audio Type Breakdown:
  2 mixed, 3 speech

Story Beats: 5 (2 starred)
  3 clips are reactions to story beats

Totals:
  32 utterances transcribed
  8 audio events detected
```

## Example Workflow

1. **Export your Travel Chronicle trip** to a ZIP file
2. **(Optional) Record voice references** - each family member records their voice in the app
3. **Run the pipeline:**
   ```bash
   uv run python process.py my_trip_export.zip --verbose
   ```
4. **Review the results** in `output/enriched_metadata.json`

## Project Structure

```
travel-chronicle-pipeline/
├── process.py              # Main pipeline (orchestrates both APIs)
├── transcribe.py           # OpenAI transcription with speaker diarization
├── analyze.py              # Gemini audio analysis (scene understanding)
├── audio_utils.py          # Audio file utilities
├── utils.py                # Helper functions (ZIP extraction, JSON handling)
├── tests/                  # Comprehensive test suite (128 tests, 92% coverage)
│   ├── conftest.py         # Shared test fixtures
│   ├── test_analyze.py     # Tests for audio analysis
│   ├── test_transcribe.py  # Tests for transcription
│   ├── test_process.py     # Tests for main pipeline
│   ├── test_audio_utils.py # Tests for audio utilities
│   └── test_utils.py       # Tests for utility functions
├── pyproject.toml          # Project metadata and dependencies (uv)
├── uv.lock                 # Locked dependency versions
├── .pre-commit-config.yaml # Pre-commit hooks configuration
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore patterns
├── README.md               # This file (user documentation)
└── CLAUDE.md               # Developer documentation
```

**Note:** This project uses [uv](https://docs.astral.sh/uv/) for fast, reliable Python package management.

## How It Works

The pipeline uses a **hybrid approach** combining OpenAI and Gemini:

1. **Extract** the Travel Chronicle export ZIP
2. **Load** metadata about the trip, travelers, and story beats
3. **Detect** per-traveler voice references from `voice_references/` folder
4. **Encode** voice references as base64 data URLs for OpenAI
5. **Process** each audio clip:
   - **OpenAI** (`gpt-4o-transcribe-diarize`): Transcribe with speaker identification using voice references
   - **Gemini** (`gemini-3-flash-preview`): Analyze for audioType, audioEvents, sceneDescription, emotionalTone
   - **Merge** results from both APIs
   - Resolve story beat ID to full story beat object
6. **Save** enriched metadata with all analysis results

**Why hybrid?** OpenAI provides superior speaker diarization with explicit voice reference support, while Gemini excels at scene understanding and audio event detection.

## Voice Reference Best Practices

The pipeline automatically detects individual voice reference files for each traveler. Voice references are stored in the `voice_references/` folder and linked via the `voiceReferenceFile` field in each traveler's metadata.

For optimal speaker identification, each family member should:
- Say their name clearly
- Speak for 2-3 seconds
- Use their natural voice

Example export structure:
```
trip-export.zip
├── metadata.json
├── audio/
│   └── ...
└── voice_references/
    ├── ellen.webm
    ├── mom.webm
    └── dad.webm
```

When the pipeline runs, you'll see:
- `Voice references found: Ellen, Mom, Dad (3/4 travelers)` - voice references detected
- `Missing voice reference: Alina` - travelers without voice references
- `No voice references (speaker ID may be less accurate)` - no voice references found

## API Costs

This pipeline uses both OpenAI and Gemini APIs:

**OpenAI (Transcription):**
- Model: `gpt-4o-transcribe-diarize`
- Cost: ~$0.006/min
- 50 clips (30 sec avg) ≈ $0.15

**Gemini (Analysis):**
- Model: `gemini-3-flash-preview`
- Cost: ~$0.001/clip
- 50 clips ≈ $0.05

**Total estimate:** ~$0.20 for 50 clips

Check current pricing:
- [OpenAI Pricing](https://openai.com/pricing)
- [Google AI Pricing](https://ai.google.dev/pricing)

## Development

### Code Quality

This project uses comprehensive defensive programming tools to ensure code quality and security:

- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checking to catch type errors before runtime
- **bandit** - Security linter to detect common security issues
- **pip-audit** - Dependency vulnerability scanner
- **pre-commit** - Automated hooks that run before each commit

### Running Tests

The project includes a comprehensive test suite with 92% code coverage:

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=. --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_analyze.py
```

### Code Quality Checks

```bash
# Format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Type checking
uv run mypy analyze.py process.py utils.py

# Security scan
uv run bandit -r .

# Check for dependency vulnerabilities
uv run pip-audit
```

### Pre-commit Hooks

Pre-commit hooks are automatically installed and will run on every commit:

```bash
# Install hooks (one-time setup, already done if you followed install steps)
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files
```

The hooks automatically check for:
- Code formatting (ruff)
- Type errors (mypy)
- Security issues (bandit)
- Secrets in code (git-secrets)
- Trailing whitespace, file endings, YAML/JSON/TOML syntax

For more detailed development documentation, see [CLAUDE.md](CLAUDE.md).

## Troubleshooting

### API Key Not Found
```
Error: GEMINI_API_KEY not found in .env file
Error: OPENAI_API_KEY not found in .env file
```
**Solution:** Create a `.env` file with both API keys (see Configuration section)

### File Not Found
```
Error: ZIP file not found: export.zip
```
**Solution:** Provide the full path to your ZIP file

### Voice References Not Detected
```
No voice references (speaker ID may be less accurate)
```
**Solution:** Ensure voice references are properly configured:
- Each traveler's `voiceReferenceFile` field points to a valid file path
- Voice reference files exist in the `voice_references/` folder
- File paths in metadata match actual file names (e.g., `"voice_references/ellen.webm"`)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks:
   ```bash
   uv run pytest
   uv run ruff check --fix .
   uv run ruff format .
   uv run mypy analyze.py process.py utils.py
   ```
5. Commit your changes (pre-commit hooks will run automatically)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

See [CLAUDE.md](CLAUDE.md) for detailed development documentation.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Transcription by [OpenAI gpt-4o-transcribe-diarize](https://platform.openai.com/docs/models/gpt-4o-transcribe-diarize)
- Analysis by [Google Gemini 3 Flash](https://ai.google.dev/gemini-api)
- Part of the Travel Chronicle ecosystem
- 🤖 Developed with [Claude Code](https://claude.com/claude-code)

---

**Note:** This pipeline is designed to work with Travel Chronicle export files. Make sure your audio files are in a supported format (WebM recommended).
