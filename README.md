# Travel Chronicle Pipeline

AI-powered audio analysis pipeline for Travel Chronicle using Gemini 3 Flash. Automatically transcribes family audio clips with speaker identification, scene descriptions, and emotional tone analysis.

[![Tests](https://img.shields.io/badge/tests-49%20passing-success)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-96%25-success)](htmlcov/)
[![Type Checked](https://img.shields.io/badge/mypy-passing-success)](pyproject.toml)
[![Security](https://img.shields.io/badge/bandit-passing-success)](pyproject.toml)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000)](https://docs.astral.sh/ruff/)

## Features

- 🎯 **Context-Aware Transcription**: Uses family member names and trip context for accurate speaker identification
- 🗣️ **Voice Reference Support**: Upload a voice reference file where family members introduce themselves for even better accuracy
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
- [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)

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
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your API key from [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key).

## Usage

### Basic Usage

Process a Travel Chronicle export ZIP file:

```bash
uv run python process.py /path/to/export.zip
```

### With Voice Reference

For improved speaker identification, provide a voice reference file where each family member introduces themselves:

```bash
uv run python process.py /path/to/export.zip --voice-reference voice_intro.webm
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
uv run python process.py /path/to/export.zip --voice-reference voice.webm --verbose
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `zip_path` | Path to the Travel Chronicle export ZIP file (required) |
| `--voice-reference PATH` | Path to voice reference audio file for better speaker identification |
| `--verbose`, `-v` | Show full transcripts for each clip during processing |
| `--dry-run` | Preview processing without making API calls |
| `--help`, `-h` | Show help message |

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

Totals:
  32 utterances transcribed
  8 audio events detected
```

## Example Workflow

1. **Export your Travel Chronicle trip** to a ZIP file
2. **(Optional) Record a voice reference** where each family member says their name
3. **Run the pipeline:**
   ```bash
   uv run python process.py my_trip_export.zip --voice-reference voices.webm --verbose
   ```
4. **Review the results** in `output/enriched_metadata.json`

## Project Structure

```
travel-chronicle-pipeline/
├── analyze.py              # Core audio analysis with Gemini API
├── process.py              # Main pipeline for batch processing
├── utils.py                # Helper functions (ZIP extraction, JSON handling)
├── tests/                  # Comprehensive test suite (49 tests, 96% coverage)
│   ├── conftest.py         # Shared test fixtures
│   ├── test_analyze.py     # Tests for audio analysis
│   ├── test_process.py     # Tests for main pipeline
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

1. **Extract** the Travel Chronicle export ZIP
2. **Load** metadata about the trip and travelers
3. **Upload** voice reference (if provided) to Gemini once
4. **Process** each audio clip:
   - Upload audio file to Gemini
   - Send context-aware prompt with traveler info, location, timestamps
   - Receive structured JSON analysis
   - Parse and validate results
5. **Save** enriched metadata with all analysis results

## Voice Reference Best Practices

For optimal speaker identification, create a voice reference where each family member:
- Says their name clearly
- Speaks for 2-3 seconds
- Uses their natural voice

Example:
```
"Hi, I'm Ellen, I'm 8 years old."
"This is Alina, age 9."
"I'm Anne, the mom."
"And I'm Geoff, the dad."
```

## API Costs

This pipeline uses Google's Gemini 3 Flash API. Costs depend on:
- Number of audio clips
- Length of each clip
- Whether voice references are used

Check current pricing at [Google AI Pricing](https://ai.google.dev/pricing).

## Development

### Code Quality

This project uses comprehensive defensive programming tools to ensure code quality and security:

- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checking to catch type errors before runtime
- **bandit** - Security linter to detect common security issues
- **pip-audit** - Dependency vulnerability scanner
- **pre-commit** - Automated hooks that run before each commit

### Running Tests

The project includes a comprehensive test suite with 96% code coverage:

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
```
**Solution:** Create a `.env` file with your API key (see Configuration section)

### File Not Found
```
Error: ZIP file not found: export.zip
```
**Solution:** Provide the full path to your ZIP file

### Voice Reference Issues
```
Error: Voice reference file not found
```
**Solution:** Ensure the voice reference file path is correct and the file exists

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

- Built with [Google Gemini 3 Flash](https://ai.google.dev/gemini-api)
- Part of the Travel Chronicle ecosystem
- 🤖 Developed with [Claude Code](https://claude.com/claude-code)

---

**Note:** This pipeline is designed to work with Travel Chronicle export files. Make sure your audio files are in a supported format (WebM recommended).
