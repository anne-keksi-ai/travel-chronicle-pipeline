#!/usr/bin/env python3
# Travel Chronicle - Audio Utilities

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pydub import AudioSegment


@dataclass
class ConcatenatedAudio:
    """Result of concatenating audio files with timing information."""

    file_path: Path
    voice_reference_segments: list[
        tuple[dict[str, Any], float, float]
    ]  # (traveler, start_ms, end_ms)
    clip_start_ms: float
    clip_end_ms: float
    total_duration_ms: float


def format_timestamp(ms: float) -> str:
    """
    Format milliseconds as MM:SS timestamp.

    Args:
        ms: Time in milliseconds

    Returns:
        Formatted string like "01:23"
    """
    total_seconds = int(ms / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def concatenate_audio_files(
    voice_reference_files: list[tuple[dict[str, Any], Path]],
    clip_path: Path,
    output_dir: Optional[Path] = None,
) -> ConcatenatedAudio:
    """
    Concatenate voice reference files and a clip into a single audio file.

    The resulting file contains:
    1. All voice reference files in sequence
    2. The clip to analyze at the end

    Args:
        voice_reference_files: List of (traveler_dict, file_path) tuples
        clip_path: Path to the audio clip to analyze
        output_dir: Optional directory for output file (uses temp dir if not specified)

    Returns:
        ConcatenatedAudio with the concatenated file path and timing information
    """
    # Start with an empty audio segment
    combined = AudioSegment.empty()

    # Track timing information for voice references
    voice_segments: list[tuple[dict[str, Any], float, float]] = []

    # Add each voice reference file
    for traveler, ref_path in voice_reference_files:
        start_ms = len(combined)
        segment = AudioSegment.from_file(str(ref_path))
        combined += segment
        end_ms = len(combined)
        voice_segments.append((traveler, start_ms, end_ms))

    # Record where the clip starts
    clip_start_ms = len(combined)

    # Add the clip to analyze
    clip_segment = AudioSegment.from_file(str(clip_path))
    combined += clip_segment

    clip_end_ms = len(combined)

    # Determine output path
    if output_dir:
        output_path = output_dir / "concatenated_audio.webm"
    else:
        # Use a temp file
        temp_file = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        output_path = Path(temp_file.name)
        temp_file.close()

    # Export the concatenated audio
    # Use webm format with opus codec to match input format
    combined.export(str(output_path), format="webm", codec="libopus")

    return ConcatenatedAudio(
        file_path=output_path,
        voice_reference_segments=voice_segments,
        clip_start_ms=clip_start_ms,
        clip_end_ms=clip_end_ms,
        total_duration_ms=len(combined),
    )


def cleanup_concatenated_audio(concatenated: ConcatenatedAudio) -> None:
    """
    Clean up temporary concatenated audio file.

    Args:
        concatenated: The ConcatenatedAudio object to clean up
    """
    if concatenated.file_path.exists():
        concatenated.file_path.unlink()
