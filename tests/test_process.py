# Tests for process.py

import json
import sys
from pathlib import Path

import pytest
from conftest import WEBM_STUB

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

    def test_process_with_legacy_voice_reference(
        self,
        create_test_zip,
        sample_metadata,
        temp_dir,
        monkeypatch,
        mocker,
        sample_gemini_response,
        capsys,
    ):
        """Test processing with legacy voice reference file shows not supported message."""
        # Create ZIP with legacy voice reference inside
        zip_path = create_test_zip(
            sample_metadata, name="test_with_voice", include_voice_reference=True
        )

        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(zip_path)])
        monkeypatch.chdir(temp_dir)

        # Mock analyze_audio
        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        captured = capsys.readouterr()

        # Verify legacy voice reference was detected but noted as not supported
        assert "Legacy voice reference found: voice_reference.webm" in captured.out
        assert "Legacy format not supported" in captured.out

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
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, temp_dir
    ):
        """Test that enriched metadata is saved correctly."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)  # Use temp directory to avoid polluting repo

        mock_analyze = mocker.patch("process.analyze_audio")
        mock_analyze.return_value = sample_gemini_response

        process.main()

        # Check that enriched_metadata.json was created in versioned output dir
        output_files = list(Path("output").glob("*/enriched_metadata.json"))
        assert len(output_files) == 1

        # Load and verify content
        with open(output_files[0], encoding="utf-8") as f:
            enriched = json.load(f)

        # Verify clips have analysis
        assert "clips" in enriched
        for clip in enriched["clips"]:
            if "analysis" in clip:
                assert "audioType" in clip["analysis"]
                assert "transcript" in clip["analysis"]

    def test_process_tracks_statistics(
        self, sample_zip_file, monkeypatch, mocker, sample_gemini_response, capsys, temp_dir
    ):
        """Test that statistics are tracked and displayed."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file)])
        monkeypatch.chdir(temp_dir)  # Use temp directory to avoid polluting repo

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

    def test_process_dry_run_with_legacy_voice_reference(
        self, create_test_zip, sample_metadata, temp_dir, monkeypatch, capsys
    ):
        """Test dry-run mode with legacy voice reference shows not supported message."""
        # Create ZIP with legacy voice reference inside
        zip_path = create_test_zip(
            sample_metadata, name="test_dry_voice", include_voice_reference=True
        )

        monkeypatch.setattr(sys, "argv", ["process.py", str(zip_path), "--dry-run"])
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()

        # Verify dry run shows legacy voice reference notice
        assert "DRY RUN MODE" in captured.out
        assert "Legacy voice reference found: voice_reference.webm" in captured.out
        assert "Legacy format not supported" in captured.out

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

    def test_build_context_with_story_beat_id(self):
        """Test building context with storyBeatId lookup."""
        clip = {"storyBeatId": "beat_123"}
        travelers: list[dict[str, str]] = []
        story_beats_lookup = {
            "beat_123": {"id": "beat_123", "text": "A story about adventure", "starred": False}
        }

        context = process.build_clip_context(clip, travelers, story_beats_lookup)

        assert context["storyBeatContext"] == "A story about adventure"
        assert "storyBeatStarred" not in context

    def test_build_context_with_starred_story_beat(self):
        """Test building context with starred story beat."""
        clip = {"storyBeatId": "beat_456"}
        travelers: list[dict[str, str]] = []
        story_beats_lookup = {
            "beat_456": {"id": "beat_456", "text": "A favorite story", "starred": True}
        }

        context = process.build_clip_context(clip, travelers, story_beats_lookup)

        assert context["storyBeatContext"] == "A favorite story"
        assert context["storyBeatStarred"] is True

    def test_build_context_story_beat_id_not_found(self):
        """Test building context when storyBeatId doesn't exist in lookup."""
        clip = {"storyBeatId": "nonexistent_beat"}
        travelers: list[dict[str, str]] = []
        story_beats_lookup = {"other_beat": {"id": "other_beat", "text": "Other"}}

        context = process.build_clip_context(clip, travelers, story_beats_lookup)

        assert "storyBeatContext" not in context
        assert "storyBeatStarred" not in context

    def test_build_context_legacy_story_beat_context(self):
        """Test building context with legacy storyBeatContext field."""
        clip = {"storyBeatContext": "Legacy inline story"}
        travelers: list[dict[str, str]] = []
        story_beats_lookup: dict[str, dict[str, str]] = {}

        context = process.build_clip_context(clip, travelers, story_beats_lookup)

        assert context["storyBeatContext"] == "Legacy inline story"

    def test_build_context_story_beat_id_takes_precedence(self):
        """Test that storyBeatId takes precedence over legacy storyBeatContext."""
        clip = {
            "storyBeatId": "beat_new",
            "storyBeatContext": "Legacy story",  # Should be ignored
        }
        travelers: list[dict[str, str]] = []
        story_beats_lookup = {"beat_new": {"id": "beat_new", "text": "New story format"}}

        context = process.build_clip_context(clip, travelers, story_beats_lookup)

        assert context["storyBeatContext"] == "New story format"


class TestBuildStoryBeatsLookup:
    """Tests for build_story_beats_lookup function."""

    def test_empty_metadata(self):
        """Test with no storyBeats in metadata."""
        metadata: dict[str, list[dict[str, str]]] = {}
        lookup = process.build_story_beats_lookup(metadata)
        assert lookup == {}

    def test_empty_story_beats_array(self):
        """Test with empty storyBeats array."""
        metadata: dict[str, list[dict[str, str]]] = {"storyBeats": []}
        lookup = process.build_story_beats_lookup(metadata)
        assert lookup == {}

    def test_single_story_beat(self):
        """Test with single story beat."""
        metadata = {"storyBeats": [{"id": "beat_1", "text": "Story one", "starred": True}]}
        lookup = process.build_story_beats_lookup(metadata)

        assert len(lookup) == 1
        assert lookup["beat_1"]["text"] == "Story one"
        assert lookup["beat_1"]["starred"] is True

    def test_multiple_story_beats(self):
        """Test with multiple story beats."""
        metadata = {
            "storyBeats": [
                {"id": "beat_1", "text": "First", "starred": True},
                {"id": "beat_2", "text": "Second", "starred": False},
                {"id": "beat_3", "text": "Third"},
            ]
        }
        lookup = process.build_story_beats_lookup(metadata)

        assert len(lookup) == 3
        assert "beat_1" in lookup
        assert "beat_2" in lookup
        assert "beat_3" in lookup

    def test_story_beat_without_id_skipped(self):
        """Test that story beats without id are skipped."""
        metadata = {
            "storyBeats": [
                {"id": "beat_1", "text": "Has ID"},
                {"text": "No ID"},  # Should be skipped
            ]
        }
        lookup = process.build_story_beats_lookup(metadata)

        assert len(lookup) == 1
        assert "beat_1" in lookup


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


class TestGenerateOutputDir:
    """Tests for generate_output_dir function."""

    def test_generates_versioned_path(self):
        """Test that output path includes ZIP name and timestamp."""
        result = process.generate_output_dir("/path/to/my_trip.zip")

        # Should start with output directory
        assert "output" in result
        # Should include ZIP name
        assert "my_trip_" in result
        # Should include date pattern (YYYY-MM-DD_HHMMSS)
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2}_\d{6}$", result)

    def test_custom_base_dir(self):
        """Test with custom base directory."""
        result = process.generate_output_dir("/path/to/export.zip", base_dir="/custom/output")

        assert result.startswith("/custom/output/")
        assert "export_" in result

    def test_handles_path_with_spaces(self):
        """Test handling of paths with spaces."""
        result = process.generate_output_dir("/path/to/my trip export.zip")

        assert "my trip export_" in result


class TestDetectVoiceReference:
    """Tests for detect_voice_reference function."""

    def test_detect_voice_reference_found(self, temp_dir):
        """Test detection when voice_reference.webm exists."""
        # Create directory with voice reference
        (temp_dir / "voice_reference.webm").write_bytes(WEBM_STUB)

        result = process.detect_voice_reference(str(temp_dir))

        assert result is not None
        assert result.name == "voice_reference.webm"

    def test_detect_voice_reference_not_found(self, temp_dir):
        """Test detection when voice_reference.webm doesn't exist."""
        result = process.detect_voice_reference(str(temp_dir))

        assert result is None

    def test_detect_voice_reference_wrong_filename(self, temp_dir):
        """Test detection ignores files with wrong names."""
        # Create file with different name
        (temp_dir / "voice.webm").write_bytes(WEBM_STUB)
        (temp_dir / "reference.webm").write_bytes(WEBM_STUB)

        result = process.detect_voice_reference(str(temp_dir))

        assert result is None


class TestLoadVoiceReferences:
    """Tests for load_voice_references function."""

    def test_load_voice_references_from_folder(self, temp_dir):
        """Test loading voice references when folder exists with matching files."""
        # Create voice_references folder
        voice_refs_dir = temp_dir / "voice_references"
        voice_refs_dir.mkdir()

        # Create voice reference files
        (voice_refs_dir / "ellen.webm").write_bytes(WEBM_STUB)
        (voice_refs_dir / "mom.webm").write_bytes(WEBM_STUB)

        # voiceReferenceFile now contains full relative path
        travelers = [
            {"name": "Ellen", "age": 7, "voiceReferenceFile": "voice_references/ellen.webm"},
            {"name": "Mom", "voiceReferenceFile": "voice_references/mom.webm"},
            {"name": "Dad", "age": None, "voiceReferenceFile": None},  # No voice reference
        ]

        result = process.load_voice_references(str(temp_dir), travelers)

        assert len(result) == 2
        assert result[0].traveler["name"] == "Ellen"
        assert result[0].file_path.name == "ellen.webm"
        assert result[1].traveler["name"] == "Mom"

    def test_load_voice_references_no_folder(self, temp_dir):
        """Test returns empty list when voice reference file path doesn't exist."""
        travelers = [{"name": "Ellen", "voiceReferenceFile": "voice_references/ellen.webm"}]

        result = process.load_voice_references(str(temp_dir), travelers)

        assert result == []

    def test_load_voice_references_missing_file(self, temp_dir):
        """Test skips travelers with missing voice reference files."""
        voice_refs_dir = temp_dir / "voice_references"
        voice_refs_dir.mkdir()
        (voice_refs_dir / "ellen.webm").write_bytes(WEBM_STUB)

        travelers = [
            {"name": "Ellen", "voiceReferenceFile": "voice_references/ellen.webm"},
            {"name": "Mom", "voiceReferenceFile": "voice_references/missing.webm"},
        ]

        result = process.load_voice_references(str(temp_dir), travelers)

        assert len(result) == 1
        assert result[0].traveler["name"] == "Ellen"

    def test_load_voice_references_null_voice_reference_file(self, temp_dir):
        """Test skips travelers with voiceReferenceFile: null."""
        voice_refs_dir = temp_dir / "voice_references"
        voice_refs_dir.mkdir()
        (voice_refs_dir / "ellen.webm").write_bytes(WEBM_STUB)

        travelers = [
            {"name": "Ellen", "voiceReferenceFile": None},  # Explicitly null
            {"name": "Mom"},  # Field missing entirely
        ]

        result = process.load_voice_references(str(temp_dir), travelers)

        assert result == []

    def test_load_voice_references_empty_travelers(self, temp_dir):
        """Test returns empty list with no travelers."""
        voice_refs_dir = temp_dir / "voice_references"
        voice_refs_dir.mkdir()
        (voice_refs_dir / "test.webm").write_bytes(WEBM_STUB)

        result = process.load_voice_references(str(temp_dir), [])

        assert result == []


class TestPrintVoiceReferenceSummary:
    """Tests for print_voice_reference_summary function."""

    def test_print_summary_with_all_travelers(self, capsys):
        """Test summary when all travelers have voice references."""
        from pathlib import Path

        travelers = [
            {"name": "Ellen", "age": 7},
            {"name": "Mom"},
        ]
        voice_refs = [
            process.VoiceReference(traveler=travelers[0], file_path=Path("/test/ellen.webm")),
            process.VoiceReference(traveler=travelers[1], file_path=Path("/test/mom.webm")),
        ]

        process.print_voice_reference_summary(travelers, voice_refs)

        captured = capsys.readouterr()
        assert "Voice references found: Ellen (age 7), Mom (2/2 travelers)" in captured.out
        assert "Missing voice reference" not in captured.out

    def test_print_summary_with_missing_traveler(self, capsys):
        """Test summary when some travelers are missing voice references."""
        from pathlib import Path

        travelers = [
            {"name": "Ellen", "age": 7},
            {"name": "Mom"},
            {"name": "Dad"},
        ]
        voice_refs = [
            process.VoiceReference(traveler=travelers[0], file_path=Path("/test/ellen.webm")),
        ]

        process.print_voice_reference_summary(travelers, voice_refs)

        captured = capsys.readouterr()
        assert "Voice references found: Ellen (age 7) (1/3 travelers)" in captured.out
        assert "Missing voice reference: Mom, Dad" in captured.out

    def test_print_summary_no_voice_references(self, capsys):
        """Test summary when no voice references available."""
        travelers = [{"name": "Ellen"}, {"name": "Mom"}]

        process.print_voice_reference_summary(travelers, [])

        captured = capsys.readouterr()
        assert "No voice references (speaker ID may be less accurate)" in captured.out

    def test_print_summary_no_travelers(self, capsys):
        """Test summary with no travelers defined."""
        process.print_voice_reference_summary([], [])

        captured = capsys.readouterr()
        assert "No travelers defined" in captured.out


class TestVoiceReferenceDataclass:
    """Tests for VoiceReference dataclass."""

    def test_voice_reference_creation(self, temp_dir):
        """Test creating a VoiceReference instance."""
        traveler = {"name": "Ellen", "age": 7}
        file_path = temp_dir / "ellen.webm"
        file_path.write_bytes(WEBM_STUB)

        vr = process.VoiceReference(traveler=traveler, file_path=file_path)

        assert vr.traveler == traveler
        assert vr.file_path == file_path


class TestNoVoiceReferenceMessage:
    """Tests for 'No voice references' message."""

    def test_no_voice_reference_message_displayed(
        self, sample_zip_file, monkeypatch, capsys, temp_dir
    ):
        """Test that 'No voice references' message is displayed when not present."""
        monkeypatch.setattr(sys, "argv", ["process.py", str(sample_zip_file), "--dry-run"])
        monkeypatch.chdir(temp_dir)

        process.main()

        captured = capsys.readouterr()
        assert "No voice references (speaker ID may be less accurate)" in captured.out


class TestPrintHeader:
    """Tests for print_header function."""

    def test_header_normal_mode(self, capsys):
        """Test header output in normal mode."""
        process.print_header(dry_run=False)

        captured = capsys.readouterr()
        assert "TRAVEL CHRONICLE PROCESSING PIPELINE" in captured.out
        assert "DRY RUN" not in captured.out

    def test_header_dry_run_mode(self, capsys):
        """Test header output in dry run mode."""
        process.print_header(dry_run=True)

        captured = capsys.readouterr()
        assert "DRY RUN MODE" in captured.out


class TestPrintFinalSummary:
    """Tests for print_final_summary function."""

    def test_summary_dry_run(self, capsys):
        """Test summary output in dry run mode."""
        stats = process.ProcessingStats()

        process.print_final_summary(stats, num_clips=10, story_beats_lookup={}, dry_run=True)

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

        process.print_final_summary(stats, num_clips=10, story_beats_lookup={}, dry_run=False)

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

        process.print_final_summary(stats, num_clips=5, story_beats_lookup={}, dry_run=False)

        captured = capsys.readouterr()
        assert "Done! Processed 5/5 clips successfully" in captured.out
        assert "Errors:" not in captured.out

    def test_summary_with_story_beats(self, capsys):
        """Test summary output with story beats."""
        stats = process.ProcessingStats(
            processed_count=5,
            error_count=0,
            audio_type_counts={"speech": 5},
            total_utterances=25,
            total_audio_events=10,
            clips_with_story_beats=3,
        )
        story_beats_lookup = {
            "beat_1": {"id": "beat_1", "text": "Story 1", "starred": True},
            "beat_2": {"id": "beat_2", "text": "Story 2", "starred": True},
            "beat_3": {"id": "beat_3", "text": "Story 3", "starred": False},
            "beat_4": {"id": "beat_4", "text": "Story 4", "starred": False},
            "beat_5": {"id": "beat_5", "text": "Story 5", "starred": False},
        }

        process.print_final_summary(
            stats, num_clips=5, story_beats_lookup=story_beats_lookup, dry_run=False
        )

        captured = capsys.readouterr()
        assert "Story Beats: 5 (2 starred)" in captured.out
        assert "3 clips are reactions to story beats" in captured.out


class TestPrintTripSummary:
    """Tests for print_trip_summary function."""

    def test_trip_summary_new_format(self, capsys, sample_metadata):
        """Test trip summary with new metadata format."""
        trip_data, clips, travelers, story_beats_lookup = process.print_trip_summary(
            sample_metadata
        )

        captured = capsys.readouterr()
        assert "TRIP SUMMARY" in captured.out
        assert "Test Trip" in captured.out
        assert "Number of Clips: 2" in captured.out
        assert "Alice" in captured.out
        assert "age 9" in captured.out

        assert trip_data["id"] == "trip_test123"
        assert len(clips) == 2
        assert len(travelers) == 4
        assert story_beats_lookup == {}  # No story beats in sample_metadata

    def test_trip_summary_old_format(self, capsys):
        """Test trip summary with old metadata format."""
        old_metadata = {
            "tripName": "Old Trip",
            "travelers": [{"name": "Charlie"}],
            "clips": [{"id": "clip_1"}],
        }

        trip_data, clips, travelers, story_beats_lookup = process.print_trip_summary(old_metadata)

        captured = capsys.readouterr()
        assert "Old Trip" in captured.out
        assert "Charlie" in captured.out

        assert len(clips) == 1
        assert travelers == [{"name": "Charlie"}]
        assert story_beats_lookup == {}

    def test_trip_summary_no_travelers(self, capsys):
        """Test trip summary with no travelers."""
        metadata = {"trip": {"name": "Solo Trip"}, "clips": []}

        _, _, _, story_beats_lookup = process.print_trip_summary(metadata)

        captured = capsys.readouterr()
        assert "Talent/Travelers: None specified" in captured.out
        assert story_beats_lookup == {}

    def test_trip_summary_with_story_beats(self, capsys):
        """Test trip summary with story beats."""
        metadata = {
            "trip": {"name": "Story Trip"},
            "clips": [
                {"id": "clip_1", "storyBeatId": "beat_1"},
                {"id": "clip_2", "storyBeatId": "beat_2"},
                {"id": "clip_3"},  # No story beat
            ],
            "storyBeats": [
                {"id": "beat_1", "text": "First story", "starred": True},
                {"id": "beat_2", "text": "Second story", "starred": False},
                {"id": "beat_3", "text": "Unused story", "starred": True},
            ],
        }

        _, clips, _, story_beats_lookup = process.print_trip_summary(metadata)

        captured = capsys.readouterr()
        assert "Story Beats: 3 (2 starred)" in captured.out
        assert "Clips with Story Beats: 2" in captured.out

        assert len(story_beats_lookup) == 3
        assert story_beats_lookup["beat_1"]["text"] == "First story"
        assert story_beats_lookup["beat_1"]["starred"] is True
