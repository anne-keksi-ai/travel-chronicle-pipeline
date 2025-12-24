# Tests for audio_utils.py - Audio concatenation and utilities

from pathlib import Path

import pytest
from pydub import AudioSegment

from audio_utils import (
    ConcatenatedAudio,
    cleanup_concatenated_audio,
    concatenate_audio_files,
    format_timestamp,
)


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_format_timestamp_zero(self):
        """Zero milliseconds should format as 00:00."""
        assert format_timestamp(0) == "00:00"

    def test_format_timestamp_seconds(self):
        """5000ms should format as 00:05."""
        assert format_timestamp(5000) == "00:05"

    def test_format_timestamp_minutes(self):
        """65000ms (1 min 5 sec) should format as 01:05."""
        assert format_timestamp(65000) == "01:05"

    def test_format_timestamp_large(self):
        """605000ms (10 min 5 sec) should format as 10:05."""
        assert format_timestamp(605000) == "10:05"

    def test_format_timestamp_fractional(self):
        """Fractional milliseconds should be truncated."""
        assert format_timestamp(5500) == "00:05"
        assert format_timestamp(5999) == "00:05"

    def test_format_timestamp_exact_minute(self):
        """Exact minute boundary."""
        assert format_timestamp(60000) == "01:00"
        assert format_timestamp(120000) == "02:00"


class TestConcatenateAudioFiles:
    """Tests for concatenate_audio_files function."""

    def test_concatenate_single_voice_ref_and_clip(self, create_synthetic_audio, temp_dir):
        """Basic concatenation with one voice reference and one clip."""
        voice_ref = create_synthetic_audio(duration_ms=1000, frequency=440)
        clip = create_synthetic_audio(duration_ms=2000, frequency=880)

        travelers = [{"name": "Alice", "age": 9}]
        voice_ref_files = [(travelers[0], voice_ref)]

        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        assert result.file_path.exists()
        assert result.total_duration_ms == 3000
        assert result.clip_start_ms == 1000
        assert result.clip_end_ms == 3000
        assert len(result.voice_reference_segments) == 1
        assert result.voice_reference_segments[0][0] == travelers[0]
        assert result.voice_reference_segments[0][1] == 0  # start
        assert result.voice_reference_segments[0][2] == 1000  # end

    def test_concatenate_multiple_voice_refs(self, create_synthetic_audio, temp_dir):
        """Concatenation with multiple voice references."""
        voice_ref1 = create_synthetic_audio(duration_ms=1000, frequency=440)
        voice_ref2 = create_synthetic_audio(duration_ms=1500, frequency=523)
        voice_ref3 = create_synthetic_audio(duration_ms=2000, frequency=659)
        clip = create_synthetic_audio(duration_ms=3000, frequency=784)

        travelers = [
            {"name": "Alice", "age": 9},
            {"name": "Bob", "age": 7},
            {"name": "Mom"},
        ]
        voice_ref_files = [
            (travelers[0], voice_ref1),
            (travelers[1], voice_ref2),
            (travelers[2], voice_ref3),
        ]

        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        # Total: 1000 + 1500 + 2000 + 3000 = 7500
        assert result.total_duration_ms == 7500
        assert result.clip_start_ms == 4500  # After all voice refs
        assert result.clip_end_ms == 7500
        assert len(result.voice_reference_segments) == 3

        # Check each segment
        assert result.voice_reference_segments[0] == (travelers[0], 0, 1000)
        assert result.voice_reference_segments[1] == (travelers[1], 1000, 2500)
        assert result.voice_reference_segments[2] == (travelers[2], 2500, 4500)

    def test_concatenate_preserves_total_duration(self, create_synthetic_audio, temp_dir):
        """Duration of concatenated file equals sum of inputs."""
        durations = [500, 750, 1000, 1250]
        files = [create_synthetic_audio(duration_ms=d) for d in durations]

        travelers = [{"name": f"Person{i}"} for i in range(3)]
        voice_ref_files = list(zip(travelers, files[:3]))
        clip = files[3]

        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        expected_total = sum(durations)
        assert result.total_duration_ms == expected_total

        # Verify by reloading the file
        reloaded = AudioSegment.from_file(str(result.file_path))
        assert abs(len(reloaded) - expected_total) < 10  # Allow small encoding variance

    def test_concatenate_timing_segments_correct(self, create_synthetic_audio, temp_dir):
        """Timing segments are accurately calculated."""
        voice_ref1 = create_synthetic_audio(duration_ms=1000)
        voice_ref2 = create_synthetic_audio(duration_ms=2000)
        clip = create_synthetic_audio(duration_ms=1500)

        travelers = [{"name": "A"}, {"name": "B"}]
        voice_ref_files = [(travelers[0], voice_ref1), (travelers[1], voice_ref2)]

        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        # Voice ref 1: 0-1000ms
        # Voice ref 2: 1000-3000ms
        # Clip: 3000-4500ms
        assert result.voice_reference_segments[0][1] == 0
        assert result.voice_reference_segments[0][2] == 1000
        assert result.voice_reference_segments[1][1] == 1000
        assert result.voice_reference_segments[1][2] == 3000
        assert result.clip_start_ms == 3000
        assert result.clip_end_ms == 4500

    def test_concatenate_with_output_dir(self, create_synthetic_audio, temp_dir):
        """Output file is created in specified directory."""
        voice_ref = create_synthetic_audio(duration_ms=500)
        clip = create_synthetic_audio(duration_ms=500)

        voice_ref_files = [({"name": "Test"}, voice_ref)]
        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        assert result.file_path.parent == temp_dir
        assert result.file_path.name == "concatenated_audio.webm"

    def test_concatenate_without_output_dir(self, create_synthetic_audio):
        """Uses temp file when no output directory specified."""
        voice_ref = create_synthetic_audio(duration_ms=500)
        clip = create_synthetic_audio(duration_ms=500)

        voice_ref_files = [({"name": "Test"}, voice_ref)]
        result = concatenate_audio_files(voice_ref_files, clip, output_dir=None)

        try:
            assert result.file_path.exists()
            # Should be in system temp directory
            assert "tmp" in str(result.file_path).lower() or "temp" in str(result.file_path).lower()
        finally:
            cleanup_concatenated_audio(result)

    def test_concatenate_empty_voice_refs(self, create_synthetic_audio, temp_dir):
        """Concatenation with no voice references (only clip)."""
        clip = create_synthetic_audio(duration_ms=2000)

        result = concatenate_audio_files([], clip, temp_dir)

        assert result.total_duration_ms == 2000
        assert result.clip_start_ms == 0
        assert result.clip_end_ms == 2000
        assert result.voice_reference_segments == []

    def test_concatenate_creates_valid_webm(self, create_synthetic_audio, temp_dir):
        """Output file can be loaded and has correct format."""
        voice_ref = create_synthetic_audio(duration_ms=1000)
        clip = create_synthetic_audio(duration_ms=1000)

        voice_ref_files = [({"name": "Test"}, voice_ref)]
        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        # Should be loadable by pydub
        reloaded = AudioSegment.from_file(str(result.file_path))
        assert len(reloaded) == 2000


class TestCleanupConcatenatedAudio:
    """Tests for cleanup_concatenated_audio function."""

    def test_cleanup_removes_file(self, create_synthetic_audio, temp_dir):
        """Cleanup should delete the concatenated file."""
        voice_ref = create_synthetic_audio(duration_ms=500)
        clip = create_synthetic_audio(duration_ms=500)

        voice_ref_files = [({"name": "Test"}, voice_ref)]
        result = concatenate_audio_files(voice_ref_files, clip, temp_dir)

        assert result.file_path.exists()
        cleanup_concatenated_audio(result)
        assert not result.file_path.exists()

    def test_cleanup_nonexistent_file(self, temp_dir):
        """Cleanup should not error if file already gone."""
        nonexistent = ConcatenatedAudio(
            file_path=temp_dir / "nonexistent.webm",
            voice_reference_segments=[],
            clip_start_ms=0,
            clip_end_ms=1000,
            total_duration_ms=1000,
        )

        # Should not raise
        cleanup_concatenated_audio(nonexistent)


class TestConcatenatedAudioDataclass:
    """Tests for ConcatenatedAudio dataclass."""

    def test_dataclass_fields(self, temp_dir):
        """All fields should be accessible."""
        traveler = {"name": "Alice", "age": 9}
        result = ConcatenatedAudio(
            file_path=temp_dir / "test.webm",
            voice_reference_segments=[(traveler, 0.0, 1000.0)],
            clip_start_ms=1000.0,
            clip_end_ms=3000.0,
            total_duration_ms=3000.0,
        )

        assert result.file_path == temp_dir / "test.webm"
        assert result.voice_reference_segments == [(traveler, 0.0, 1000.0)]
        assert result.clip_start_ms == 1000.0
        assert result.clip_end_ms == 3000.0
        assert result.total_duration_ms == 3000.0

    def test_dataclass_with_multiple_segments(self, temp_dir):
        """Voice reference segments list handles multiple entries."""
        travelers = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
        segments = [
            (travelers[0], 0.0, 1000.0),
            (travelers[1], 1000.0, 2500.0),
            (travelers[2], 2500.0, 4000.0),
        ]

        result = ConcatenatedAudio(
            file_path=temp_dir / "test.webm",
            voice_reference_segments=segments,
            clip_start_ms=4000.0,
            clip_end_ms=6000.0,
            total_duration_ms=6000.0,
        )

        assert len(result.voice_reference_segments) == 3
        assert result.voice_reference_segments[1][0]["name"] == "B"
        assert result.voice_reference_segments[1][1] == 1000.0
        assert result.voice_reference_segments[1][2] == 2500.0


class TestConcatenationIntegration:
    """Integration tests for audio concatenation with real files."""

    @pytest.mark.integration
    def test_concatenate_real_voice_references(self, temp_dir):
        """Integration test using actual voice reference files if available."""
        voice_ref_dir = Path("/Users/anneaula/Downloads/day_at_home_2025-12-22/voice_references")

        if not voice_ref_dir.exists():
            pytest.skip("Voice reference directory not available")

        webm_files = sorted(voice_ref_dir.glob("*.webm"))
        if len(webm_files) < 2:
            pytest.skip("Not enough voice reference files")

        # Use first 3 files as voice refs and last as clip
        travelers = [
            {"name": "Alina", "age": 9},
            {"name": "Anne"},
            {"name": "Ellen", "age": 7},
        ]

        voice_ref_files = list(zip(travelers[: len(webm_files) - 1], webm_files[:-1]))
        clip_path = webm_files[-1]

        # Get expected durations
        expected_voice_ref_total = sum(
            len(AudioSegment.from_file(str(p))) for _, p in voice_ref_files
        )
        expected_clip_duration = len(AudioSegment.from_file(str(clip_path)))
        expected_total = expected_voice_ref_total + expected_clip_duration

        result = concatenate_audio_files(voice_ref_files, clip_path, temp_dir)

        try:
            # Verify total duration
            assert abs(result.total_duration_ms - expected_total) < 10

            # Verify clip starts after voice refs
            assert abs(result.clip_start_ms - expected_voice_ref_total) < 10

            # Verify file is loadable
            reloaded = AudioSegment.from_file(str(result.file_path))
            assert abs(len(reloaded) - expected_total) < 10

        finally:
            cleanup_concatenated_audio(result)
