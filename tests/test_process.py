# Tests for process.py

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Import needs to happen after sys.argv is set in some tests
import process


class TestProcessMain:
    """Tests for the main processing pipeline."""

    def test_dry_run_mode(self, sample_zip_file, monkeypatch, capsys, temp_dir):
        """Test dry run mode (no API calls)."""
        # Set command line arguments
        monkeypatch.setattr(
            sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"]
        )

        # Change to temp directory to isolate output
        import os
        monkeypatch.chdir(temp_dir)

        # Run main
        process.main()

        # Capture output
        captured = capsys.readouterr()

        # Verify dry run messages
        assert "DRY RUN MODE" in captured.out
        assert "Would analyze" in captured.out
        assert "Dry run complete" in captured.out

    def test_process_validates_zip_exists(self, temp_dir, monkeypatch, capsys):
        """Test that process validates ZIP file exists."""
        nonexistent_zip = temp_dir / "nonexistent.zip"
        monkeypatch.setattr(sys, "argv", ["process.py", str(nonexistent_zip)])

        with pytest.raises(SystemExit) as exc_info:
            process.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ZIP file not found" in captured.out

    def test_process_validates_voice_reference_exists(
        self, sample_zip_file, temp_dir, monkeypatch, capsys
    ):
        """Test that process validates voice reference file exists."""
        nonexistent_voice = temp_dir / "nonexistent_voice.webm"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "process.py",
                str(sample_zip_file),
                "--voice-reference",
                str(nonexistent_voice),
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            process.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Voice reference file not found" in captured.out

    def test_process_requires_api_key_for_non_dry_run(
        self, sample_zip_file, monkeypatch, capsys, temp_dir
    ):
        """Test that API key is required when not in dry-run mode."""
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.chdir(temp_dir)

        with pytest.raises(SystemExit) as exc_info:
            process.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "GEMINI_API_KEY not found" in captured.err

    def test_process_extracts_and_loads_metadata(
        self, sample_zip_file, sample_metadata, monkeypatch, capsys, temp_dir
    ):
        """Test that ZIP is extracted and metadata is loaded correctly."""
        monkeypatch.setattr(
            sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"]
        )
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        # Verify trip info is displayed
        assert "Test Trip" in captured.out
        assert "Number of Clips: 2" in captured.out

    def test_process_displays_travelers(self, sample_zip_file, monkeypatch, capsys, temp_dir):
        """Test that travelers/talent are displayed correctly."""
        monkeypatch.setattr(
            sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"]
        )
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        assert "Alice" in captured.out
        assert "age 9" in captured.out
        assert "Bob" in captured.out
        assert "Mom" in captured.out

    @pytest.mark.integration
    def test_process_with_mocked_api(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys, temp_dir
    ):
        """Test full processing with mocked Gemini API."""
        # Set environment and args
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)

        # Mock analyze_audio to avoid actual API calls
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify processing happened
        assert "PROCESSING CLIPS" in captured.out
        assert "Done! Processed" in captured.out
        assert "2/2 clips successfully" in captured.out

    def test_process_verbose_flag(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys
    ):
        """Test that --verbose flag shows transcripts."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(
            sys, "argv", ["process.py", str(sample_zip_file), "--verbose"]
        )

        # Mock analyze_audio
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify transcript is displayed
        assert "Transcript:" in captured.out
        assert "Alice" in captured.out or "Mom" in captured.out

    def test_process_with_voice_reference(
        self, sample_zip_file, temp_dir, monkeypatch, mocker, sample_gemini_response, capsys
    ):
        """Test processing with voice reference file."""
        # Create a dummy voice reference file
        voice_ref = temp_dir / "voice_ref.webm"
        voice_ref.write_bytes(b"\x1a\x45\xdf\xa3")

        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "process.py",
                str(sample_zip_file),
                "--voice-reference",
                str(voice_ref),
            ],
        )
        monkeypatch.chdir(temp_dir)

        # Mock the genai module at import time
        mock_client = Mock()
        mock_voice_file = Mock()
        mock_voice_file.name = "voice_ref"
        mock_client.files.upload.return_value = mock_voice_file

        # Import genai and patch it at the point it's used
        import google.genai
        mocker.patch.object(google.genai, "Client", return_value=mock_client)

        # Mock analyze_audio
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify voice reference upload message
        assert "UPLOADING VOICE REFERENCE" in captured.out
        assert "voice_ref.webm" in captured.out

    def test_process_continues_on_clip_error(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys, temp_dir
    ):
        """Test that processing continues when individual clips fail."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)

        # Mock analyze_audio to fail on first clip, succeed on second
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.side_effect = [
            {"error": "Analysis failed", "error_details": "Mock error"},
            sample_gemini_response,
        ]

        process.main()

        captured = capsys.readouterr()

        # Verify error was reported but processing continued
        assert "Analysis failed" in captured.out
        assert "1/2 clips successfully" in captured.out
        assert "Errors: 1" in captured.out

    def test_process_saves_enriched_metadata(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response
    ):
        """Test that enriched metadata is saved correctly."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])

        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        # Check that enriched_metadata.json was created
        output_file = Path("output/enriched_metadata.json")
        assert output_file.exists()

        # Load and verify content
        with open(output_file, encoding="utf-8") as f:
            enriched = json.load(f)

        # Verify clips have analysis
        assert "clips" in enriched
        for clip in enriched["clips"]:
            if "analysis" in clip:
                assert "audioType" in clip["analysis"]
                assert "transcript" in clip["analysis"]

    def test_process_tracks_statistics(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys
    ):
        """Test that statistics are tracked and displayed."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])

        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify statistics are displayed
        assert "Audio Type Breakdown:" in captured.out
        assert "speech" in captured.out
        assert "utterances transcribed" in captured.out
        assert "audio events detected" in captured.out

    def test_process_handles_old_metadata_structure(
        self, temp_dir, monkeypatch, mocker, capsys
    ):
        """Test processing with old metadata structure (travelers instead of talent)."""
        # Create ZIP with old-style metadata
        old_metadata = {
            "tripName": "Old Format Trip",
            "travelers": [{"name": "Alice"}, {"name": "Bob"}],
            "clips": [
                {
                    "id": "clip_001",
                    "filename": "audio/clip_001.webm",
                    "recordedAt": "2025-12-22T10:00:00.000Z",
                    "durationSeconds": 10,
                }
            ],
        }

        # Create old-format export
        import zipfile

        extract_dir = temp_dir / "old_export"
        extract_dir.mkdir()

        with open(extract_dir / "metadata.json", "w") as f:
            json.dump(old_metadata, f)

        audio_dir = extract_dir / "audio"
        audio_dir.mkdir()
        (audio_dir / "clip_001.webm").write_bytes(b"\x1a\x45\xdf\xa3")

        zip_path = temp_dir / "old_export.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(extract_dir.parent)
                    zipf.write(file_path, arcname)

        monkeypatch.setattr(sys, "argv", ["process.py", str(zip_path), "--dry-run"])
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        # Verify old format is handled
        assert "Old Format Trip" in captured.out
        assert "Alice" in captured.out
        assert "Bob" in captured.out

    def test_process_displays_progress_percentage(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys, temp_dir
    ):
        """Test that progress percentages are displayed."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)

        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify progress indicators
        assert "(50%)" in captured.out or "(100%)" in captured.out
        assert "1/2" in captured.out or "2/2" in captured.out

    def test_process_handles_missing_optional_fields(
        self, temp_dir, monkeypatch, mocker, sample_gemini_response
    ):
        """Test processing clips with missing optional fields (location, storyBeat)."""
        # Create metadata with minimal clip info
        minimal_metadata = {
            "trip": {"id": "trip_123", "name": "Minimal Trip", "talent": []},
            "clips": [
                {
                    "id": "clip_001",
                    "filename": "audio/clip_001.webm",
                    "recordedAt": "2025-12-22T10:00:00.000Z",
                    "durationSeconds": 10,
                    # No location, no storyBeatContext
                }
            ],
        }

        # Create export
        import zipfile

        extract_dir = temp_dir / "minimal_export"
        extract_dir.mkdir()

        with open(extract_dir / "metadata.json", "w") as f:
            json.dump(minimal_metadata, f)

        audio_dir = extract_dir / "audio"
        audio_dir.mkdir()
        (audio_dir / "clip_001.webm").write_bytes(b"\x1a\x45\xdf\xa3")

        zip_path = temp_dir / "minimal_export.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(extract_dir.parent)
                    zipf.write(file_path, arcname)

        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(zip_path)])
        monkeypatch.chdir(temp_dir)

        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        # Should not raise an error
        process.main()

        # Verify analyze was called with minimal context
        call_args = mock_analyze.call_args
        context = call_args[1]["context"]
        assert "location" not in context
        assert "storyBeatContext" not in context
