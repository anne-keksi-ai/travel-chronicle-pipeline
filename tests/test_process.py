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
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"])

        # Change to temp directory to isolate output
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
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"])
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        # Verify trip info is displayed
        assert "Test Trip" in captured.out
        assert "Number of Clips: 2" in captured.out

    def test_process_displays_travelers(self, sample_zip_file, monkeypatch, capsys, temp_dir):
        """Test that travelers/talent are displayed correctly."""
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"])
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
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file), "--verbose"])

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

    def test_process_handles_old_metadata_structure(self, temp_dir, monkeypatch, mocker, capsys):
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

    def test_process_missing_audio_file(
        self, temp_dir, monkeypatch, mocker, sample_gemini_response, capsys
    ):
        """Test handling of missing audio file."""
        # Create metadata with clip that points to non-existent audio file
        metadata = {
            "trip": {"id": "trip_123", "name": "Test Trip", "talent": []},
            "clips": [
                {
                    "id": "clip_001",
                    "filename": "audio/missing.webm",
                    "recordedAt": "2025-12-22T10:00:00.000Z",
                    "durationSeconds": 10,
                }
            ],
        }

        import zipfile

        extract_dir = temp_dir / "missing_audio_export"
        extract_dir.mkdir()

        with open(extract_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        audio_dir = extract_dir / "audio"
        audio_dir.mkdir()
        # Don't create the audio file

        zip_path = temp_dir / "missing_audio_export.zip"
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

        process.main()

        captured = capsys.readouterr()

        # Verify error was caught and processing completed
        assert "Error:" in captured.out
        assert "0/1 clips successfully" in captured.out
        assert "Errors: 1" in captured.out

    def test_process_dry_run_with_voice_reference(
        self, sample_zip_file, temp_dir, monkeypatch, capsys
    ):
        """Test dry-run mode with voice reference displays correctly."""
        # Create a dummy voice reference file
        voice_ref = temp_dir / "voice_ref.webm"
        voice_ref.write_bytes(b"\x1a\x45\xdf\xa3")

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "process.py",
                str(sample_zip_file),
                "--dry-run",
                "--voice-reference",
                str(voice_ref),
            ],
        )
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        # Verify dry run shows voice reference info
        assert "DRY RUN MODE" in captured.out
        assert (
            "Voice reference: voice_ref.webm" in captured.out
            or "[DRY RUN] Voice reference:" in captured.out
        )

    def test_process_exception_during_clip_processing(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys, temp_dir
    ):
        """Test that exceptions during clip processing are caught and logged."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)

        # Mock analyze_audio to raise an exception
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.side_effect = [
            RuntimeError("Unexpected error during analysis"),
            sample_gemini_response,
        ]

        process.main()

        captured = capsys.readouterr()

        # Verify exception was caught and processing continued
        assert "Error:" in captured.out
        assert "Unexpected error" in captured.out
        assert "1/2 clips successfully" in captured.out
        assert "Errors: 1" in captured.out

    def test_process_top_level_exception(self, temp_dir, monkeypatch, mocker, capsys):
        """Test that top-level exceptions are caught and reported."""
        # Create a malformed ZIP that will cause extract_zip to fail
        bad_zip = temp_dir / "bad.zip"
        bad_zip.write_text("This is not a valid ZIP file")

        monkeypatch.setattr(sys, "argv", ["process.py", str(bad_zip)])
        monkeypatch.chdir(temp_dir)

        with pytest.raises(SystemExit) as exc_info:
            process.main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()

        # Verify error was printed
        assert "Error:" in captured.err


class TestBuildClipContext:
    """Tests for build_clip_context function."""

    def test_build_context_with_all_fields(self):
        """Test building context with all fields present."""
        clip = {
            "location": {"placeName": "Golden Gate Bridge", "lat": 37.8199},
            "storyBeatContext": "Story about the bridge",
            "recordedAt": "2025-12-22T10:00:00.000Z",
        }
        travelers = [{"name": "Alice", "age": 9}]

        context = process.build_clip_context(clip, travelers)

        assert context["travelers"] == travelers
        assert context["location"] == "Golden Gate Bridge"
        assert context["storyBeatContext"] == "Story about the bridge"
        assert context["recordedAt"] == "2025-12-22T10:00:00.000Z"

    def test_build_context_with_empty_travelers(self):
        """Test building context with empty travelers list."""
        clip = {"recordedAt": "2025-12-22T10:00:00.000Z"}
        travelers: list[dict[str, str]] = []

        context = process.build_clip_context(clip, travelers)

        assert context["travelers"] == []
        assert "location" not in context

    def test_build_context_with_no_location(self):
        """Test building context when location is missing."""
        clip = {"storyBeatContext": "A story"}
        travelers = [{"name": "Bob"}]

        context = process.build_clip_context(clip, travelers)

        assert "location" not in context
        assert context["storyBeatContext"] == "A story"

    def test_build_context_with_none_location(self):
        """Test building context when location is None."""
        clip = {"location": None}
        travelers: list[dict[str, str]] = []

        context = process.build_clip_context(clip, travelers)

        assert "location" not in context

    def test_build_context_with_location_missing_placename(self):
        """Test building context when location has no placeName."""
        clip = {"location": {"lat": 37.8199, "lng": -122.4783}}
        travelers: list[dict[str, str]] = []

        context = process.build_clip_context(clip, travelers)

        assert "location" not in context


class TestProcessingStats:
    """Tests for ProcessingStats dataclass."""

    def test_default_values(self):
        """Test that ProcessingStats has correct default values."""
        stats = process.ProcessingStats()

        assert stats.processed_count == 0
        assert stats.error_count == 0
        assert stats.audio_type_counts == {}
        assert stats.total_utterances == 0
        assert stats.total_audio_events == 0

    def test_mutable_default_dict(self):
        """Test that audio_type_counts dict is not shared between instances."""
        stats1 = process.ProcessingStats()
        stats2 = process.ProcessingStats()

        stats1.audio_type_counts["speech"] = 5

        assert "speech" not in stats2.audio_type_counts

    def test_stats_modification(self):
        """Test modifying stats values."""
        stats = process.ProcessingStats()

        stats.processed_count = 10
        stats.error_count = 2
        stats.audio_type_counts["speech"] = 8
        stats.audio_type_counts["ambient"] = 2
        stats.total_utterances = 100
        stats.total_audio_events = 50

        assert stats.processed_count == 10
        assert stats.error_count == 2
        assert stats.audio_type_counts == {"speech": 8, "ambient": 2}
        assert stats.total_utterances == 100
        assert stats.total_audio_events == 50


class TestPrintHeader:
    """Tests for print_header function."""

    def test_header_normal_mode(self, capsys):
        """Test header output in normal mode."""
        process.print_header(dry_run=False, voice_reference=None)

        captured = capsys.readouterr()
        assert "TRAVEL CHRONICLE PROCESSING PIPELINE" in captured.out
        assert "DRY RUN" not in captured.out
        assert "Voice Reference" not in captured.out

    def test_header_dry_run_mode(self, capsys):
        """Test header output in dry run mode."""
        process.print_header(dry_run=True, voice_reference=None)

        captured = capsys.readouterr()
        assert "DRY RUN MODE" in captured.out

    def test_header_with_voice_reference(self, capsys):
        """Test header output with voice reference."""
        process.print_header(dry_run=False, voice_reference="/path/to/voice.webm")

        captured = capsys.readouterr()
        assert "Voice Reference: voice.webm" in captured.out


class TestPrintFinalSummary:
    """Tests for print_final_summary function."""

    def test_summary_dry_run(self, capsys):
        """Test summary output in dry run mode."""
        stats = process.ProcessingStats()

        process.print_final_summary(stats, num_clips=10, dry_run=True)

        captured = capsys.readouterr()
        assert "Dry run complete! Would process 10 clips" in captured.out
        assert "utterances" not in captured.out

    def test_summary_success(self, capsys):
        """Test summary output after successful processing."""
        stats = process.ProcessingStats(
            processed_count=8,
            error_count=2,
            audio_type_counts={"speech": 6, "ambient": 2},
            total_utterances=50,
            total_audio_events=20,
        )

        process.print_final_summary(stats, num_clips=10, dry_run=False)

        captured = capsys.readouterr()
        assert "Done! Processed 8/10 clips successfully" in captured.out
        assert "Errors: 2 clips failed" in captured.out
        assert "Audio Type Breakdown:" in captured.out
        assert "speech" in captured.out
        assert "50 utterances transcribed" in captured.out
        assert "20 audio events detected" in captured.out

    def test_summary_no_errors(self, capsys):
        """Test summary output with no errors."""
        stats = process.ProcessingStats(
            processed_count=5,
            error_count=0,
            audio_type_counts={"speech": 5},
            total_utterances=25,
            total_audio_events=10,
        )

        process.print_final_summary(stats, num_clips=5, dry_run=False)

        captured = capsys.readouterr()
        assert "Done! Processed 5/5 clips successfully" in captured.out
        assert "Errors:" not in captured.out


class TestPrintTripSummary:
    """Tests for print_trip_summary function."""

    def test_trip_summary_new_format(self, capsys, sample_metadata):
        """Test trip summary with new metadata format."""
        trip_data, clips, travelers = process.print_trip_summary(sample_metadata)

        captured = capsys.readouterr()
        assert "TRIP SUMMARY" in captured.out
        assert "Test Trip" in captured.out
        assert "Number of Clips: 2" in captured.out
        assert "Alice" in captured.out
        assert "age 9" in captured.out

        assert trip_data["id"] == "trip_test123"
        assert len(clips) == 2
        assert len(travelers) == 4

    def test_trip_summary_old_format(self, capsys):
        """Test trip summary with old metadata format."""
        old_metadata = {
            "tripName": "Old Trip",
            "travelers": [{"name": "Charlie"}],
            "clips": [{"id": "clip_1"}],
        }

        trip_data, clips, travelers = process.print_trip_summary(old_metadata)

        captured = capsys.readouterr()
        assert "Old Trip" in captured.out
        assert "Charlie" in captured.out

        assert len(clips) == 1
        assert travelers == [{"name": "Charlie"}]

    def test_trip_summary_no_travelers(self, capsys):
        """Test trip summary with no travelers."""
        metadata = {"trip": {"name": "Solo Trip"}, "clips": []}

        process.print_trip_summary(metadata)

        captured = capsys.readouterr()
        assert "Talent/Travelers: None specified" in captured.out
