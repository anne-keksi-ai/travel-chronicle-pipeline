# Shared fixtures for Travel Chronicle Pipeline tests

import json
import zipfile
from pathlib import Path
from typing import Any, Optional

import pytest

# Constant: Minimal WebM file header (EBML + Segment markers)
# This is a valid file signature but not playable audio
WEBM_STUB = b"\x1a\x45\xdf\xa3\xa3\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04"


@pytest.fixture
def sample_metadata():
    """Sample metadata matching Travel Chronicle export format."""
    return {
        "trip": {
            "id": "trip_test123",
            "name": "Test Trip",
            "createdAt": "2025-12-22T10:00:00.000Z",
            "talent": [
                {"name": "Alice", "age": 9},
                {"name": "Bob", "age": 7},
                {"name": "Mom"},
                {"name": "Dad"},
            ],
            "status": "active",
            "exportedAt": "2025-12-22T12:00:00.000Z",
        },
        "clips": [
            {
                "id": "clip_001",
                "filename": "audio/clip_001.webm",
                "recordedAt": "2025-12-22T10:30:00.000Z",
                "durationSeconds": 15,
                "mimeType": "audio/webm; codecs=opus",
                "location": {
                    "lat": 37.7749,
                    "lng": -122.4194,
                    "placeName": "San Francisco, CA",
                    "accuracy": 10.5,
                },
                "highlights": [],
            },
            {
                "id": "clip_002",
                "filename": "audio/clip_002.webm",
                "recordedAt": "2025-12-22T11:00:00.000Z",
                "durationSeconds": 30,
                "mimeType": "audio/webm; codecs=opus",
                "location": {
                    "lat": 37.8080,
                    "lng": -122.4177,
                    "placeName": "Golden Gate Bridge",
                    "accuracy": 15.0,
                },
                "highlights": [],
                "storyBeatContext": "Story about the Golden Gate Bridge",
            },
        ],
    }


@pytest.fixture
def sample_gemini_response():
    """Sample Gemini API response for audio analysis."""
    return {
        "audioType": "speech",
        "transcript": [
            {"timestamp": "00:00", "speaker": "Alice", "text": "Look at that!"},
            {"timestamp": "00:03", "speaker": "Mom", "text": "It's beautiful!"},
        ],
        "audioEvents": [
            {"timestamp": "00:01", "event": "wind blowing"},
            {"timestamp": "00:05", "event": "car passing by"},
        ],
        "sceneDescription": "Family viewing the Golden Gate Bridge on a windy day.",
        "emotionalTone": "excited",
    }


@pytest.fixture
def temp_dir(tmp_path):
    """Temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def sample_metadata_file(temp_dir, sample_metadata):
    """Creates a temporary metadata.json file."""
    metadata_path = temp_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(sample_metadata, f, indent=2, ensure_ascii=False)
    return metadata_path


@pytest.fixture
def sample_zip_file(temp_dir, sample_metadata):
    """Creates a sample ZIP file with metadata and audio directory structure."""
    # Create a folder structure to zip
    extract_dir = temp_dir / "test_export"
    extract_dir.mkdir()

    # Create metadata.json
    metadata_path = extract_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(sample_metadata, f, indent=2, ensure_ascii=False)

    # Create audio directory with placeholder files
    audio_dir = extract_dir / "audio"
    audio_dir.mkdir()

    # Create minimal WebM files (just headers, not real audio)
    for i in range(1, 3):
        audio_file = audio_dir / f"clip_{i:03d}.webm"
        audio_file.write_bytes(WEBM_STUB)

    # Create ZIP file
    zip_path = temp_dir / "test_export.zip"
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file_path in extract_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(extract_dir.parent)
                zipf.write(file_path, arcname)

    return zip_path


@pytest.fixture
def create_test_zip(temp_dir):
    """
    Factory fixture for creating test ZIP files with custom metadata.

    Usage:
        def test_something(create_test_zip):
            zip_path = create_test_zip(metadata, audio_files=["clip1.webm"])
    """

    def _create_zip(
        metadata: dict[str, Any],
        audio_files: Optional[list[str]] = None,
        name: str = "test_export",
    ) -> Path:
        """
        Create a test ZIP file with given metadata and audio files.

        Args:
            metadata: Metadata dict to save as metadata.json
            audio_files: List of audio filenames to create (default: derived from clips)
            name: Name for the export directory

        Returns:
            Path to the created ZIP file
        """
        extract_dir: Path = temp_dir / name
        extract_dir.mkdir(exist_ok=True)

        # Create metadata.json
        with open(extract_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Determine audio files to create
        if audio_files is None:
            # Extract from clips in metadata
            audio_files = [
                clip.get("filename", "").replace("audio/", "")
                for clip in metadata.get("clips", [])
                if clip.get("filename")
            ]

        # Create audio directory with stub files
        if audio_files:
            audio_dir = extract_dir / "audio"
            audio_dir.mkdir(exist_ok=True)
            for filename in audio_files:
                (audio_dir / filename).write_bytes(WEBM_STUB)

        # Create ZIP file
        zip_path: Path = temp_dir / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(extract_dir.parent)
                    zipf.write(file_path, arcname)

        return zip_path

    return _create_zip


@pytest.fixture
def webm_stub_file(temp_dir):
    """Create a temporary WebM stub file and return its path."""
    audio_path = temp_dir / "test_audio.webm"
    audio_path.write_bytes(WEBM_STUB)
    return audio_path


@pytest.fixture
def mock_gemini_client(mocker, sample_gemini_response):
    """Mocks the Gemini API client."""
    mock_client = mocker.Mock()

    # Mock file upload
    mock_uploaded_file = mocker.Mock()
    mock_uploaded_file.name = "uploaded_file_name"
    mock_client.files.upload.return_value = mock_uploaded_file

    # Mock generate_content response
    mock_response = mocker.Mock()
    mock_response.text = json.dumps(sample_gemini_response)
    mock_client.models.generate_content.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_genai_module(mocker, mock_gemini_client):
    """Mocks the entire google.genai module."""
    mock_genai = mocker.patch("analyze.genai")
    mock_genai.Client.return_value = mock_gemini_client
    return mock_genai
