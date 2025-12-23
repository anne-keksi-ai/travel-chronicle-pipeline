#!/usr/bin/env python3
# Travel Chronicle - Audio Processing Pipeline

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from analyze import DEFAULT_AUDIO_MIME_TYPE, analyze_audio
from utils import extract_zip, load_metadata, save_metadata

# Constants
DEFAULT_OUTPUT_DIR = "./output"
VOICE_REFERENCE_FILENAME = "voice_reference.webm"


@dataclass
class ProcessingStats:
    """Statistics collected during clip processing."""

    processed_count: int = 0
    error_count: int = 0
    audio_type_counts: dict[str, int] = field(default_factory=dict)
    total_utterances: int = 0
    total_audio_events: int = 0
    clips_with_story_beats: int = 0


def build_story_beats_lookup(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Build a lookup dictionary for story beats by ID.

    Args:
        metadata: The metadata dictionary containing storyBeats array

    Returns:
        Dictionary mapping story beat IDs to their full data
    """
    story_beats = metadata.get("storyBeats", [])
    return {beat["id"]: beat for beat in story_beats if "id" in beat}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process Travel Chronicle export ZIP files with AI audio analysis"
    )
    parser.add_argument("zip_path", help="Path to the export ZIP file")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full transcripts for each clip"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without calling Gemini API",
    )
    return parser.parse_args()


def validate_inputs(zip_path: str, dry_run: bool) -> Optional[str]:
    """
    Validate input files and load API key.

    Args:
        zip_path: Path to the ZIP file
        dry_run: Whether this is a dry run (API key not required)

    Returns:
        API key if not dry run, None otherwise

    Raises:
        SystemExit: If validation fails
    """
    # Validate ZIP file exists
    if not Path(zip_path).exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    # Load environment variables and get API key
    load_dotenv()
    api_key = None
    if not dry_run:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY not found in .env file", file=sys.stderr)
            sys.exit(1)

    return api_key


def detect_voice_reference(extracted_folder: str) -> Optional[Path]:
    """
    Check if a voice reference file exists in the extracted folder.

    Args:
        extracted_folder: Path to the extracted ZIP contents

    Returns:
        Path to voice reference file if found, None otherwise
    """
    voice_ref_path = Path(extracted_folder) / VOICE_REFERENCE_FILENAME
    if voice_ref_path.exists():
        return voice_ref_path
    return None


def print_header(dry_run: bool) -> None:
    """Print the pipeline header."""
    print("=" * 60)
    print("TRAVEL CHRONICLE PROCESSING PIPELINE")
    if dry_run:
        print("(DRY RUN MODE - No API calls will be made)")
    print("=" * 60)


def print_trip_summary(
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Print trip summary and return extracted data.

    Returns:
        Tuple of (trip_data, clips, travelers, story_beats_lookup)
    """
    print("\n" + "=" * 60)
    print("TRIP SUMMARY")
    print("=" * 60)

    # Handle both old and new metadata structures
    trip_data = metadata.get("trip", {})
    trip_name = trip_data.get("name") or metadata.get("tripName", "Unknown")
    print(f"Trip Name: {trip_name}")

    # Get trip ID and export date if available
    if trip_data.get("id"):
        print(f"Trip ID: {trip_data['id']}")
    if trip_data.get("exportedAt"):
        print(f"Exported At: {trip_data['exportedAt']}")

    clips = metadata.get("clips", [])
    print(f"Number of Clips: {len(clips)}")

    # Build story beats lookup and print summary
    story_beats_lookup = build_story_beats_lookup(metadata)
    if story_beats_lookup:
        story_beats = list(story_beats_lookup.values())
        starred_count = sum(1 for beat in story_beats if beat.get("starred"))
        clips_with_beats = sum(1 for clip in clips if clip.get("storyBeatId"))
        print(f"Story Beats: {len(story_beats)} ({starred_count} starred)")
        print(f"Clips with Story Beats: {clips_with_beats}")

    # List travelers (check both 'talent' and 'travelers')
    travelers = trip_data.get("talent") or metadata.get("travelers", [])
    if travelers:
        print("\nTalent/Travelers:")
        for traveler in travelers:
            if "age" in traveler:
                print(f"  - {traveler['name']} (age {traveler['age']})")
            else:
                print(f"  - {traveler['name']}")
    else:
        print("\nTalent/Travelers: None specified")

    print("=" * 60)

    return trip_data, clips, travelers, story_beats_lookup


def upload_voice_reference(voice_reference: str, api_key: str, num_clips: int) -> Any:
    """
    Upload voice reference file to Gemini.

    Args:
        voice_reference: Path to voice reference file
        api_key: Gemini API key
        num_clips: Number of clips (for display)

    Returns:
        Uploaded file object
    """
    from google import genai

    print("\n" + "=" * 60)
    print("UPLOADING VOICE REFERENCE")
    print("=" * 60)

    voice_ref_path = Path(voice_reference)
    print(f"Uploading voice reference: {voice_ref_path.name}")

    client = genai.Client(api_key=api_key)
    with open(voice_ref_path, "rb") as f:
        voice_reference_file = client.files.upload(
            file=f, config={"mime_type": DEFAULT_AUDIO_MIME_TYPE}
        )

    print(f"Voice reference uploaded. File name: {voice_reference_file.name}")
    print(f"This reference will be used for all {num_clips} clips")
    print("=" * 60)

    return voice_reference_file


def build_clip_context(
    clip: dict[str, Any],
    travelers: list[dict[str, Any]],
    story_beats_lookup: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Build context dictionary for a clip.

    Args:
        clip: Clip metadata
        travelers: List of traveler information
        story_beats_lookup: Optional dictionary mapping story beat IDs to their data

    Returns:
        Context dictionary for audio analysis
    """
    context: dict[str, Any] = {"travelers": travelers if travelers else []}

    # Add location if available (handle None gracefully)
    location = clip.get("location")
    if location and isinstance(location, dict):
        place_name = location.get("placeName")
        if place_name:
            context["location"] = place_name

    # Add story beat context - check new format (storyBeatId) first, then legacy (storyBeatContext)
    story_beat_id = clip.get("storyBeatId")
    if story_beat_id and story_beats_lookup:
        story_beat = story_beats_lookup.get(story_beat_id)
        if story_beat:
            # Include text from the story beat
            if story_beat.get("text"):
                context["storyBeatContext"] = story_beat["text"]
            # Include starred status
            if story_beat.get("starred"):
                context["storyBeatStarred"] = True
    elif clip.get("storyBeatContext"):
        # Legacy format: inline storyBeatContext
        context["storyBeatContext"] = clip["storyBeatContext"]

    # Add recorded timestamp if available
    recorded_at = clip.get("recordedAt")
    if recorded_at:
        context["recordedAt"] = recorded_at

    return context


def process_single_clip(
    clip: dict[str, Any],
    audio_path: Path,
    context: dict[str, Any],
    api_key: str,
    voice_reference_file: Any,
    verbose: bool,
    stats: ProcessingStats,
) -> None:
    """
    Process a single audio clip.

    Args:
        clip: Clip metadata (modified in place)
        audio_path: Path to audio file
        context: Context dictionary
        api_key: Gemini API key
        voice_reference_file: Optional uploaded voice reference
        verbose: Whether to show verbose output
        stats: Statistics object (modified in place)
    """
    result = analyze_audio(
        str(audio_path),
        api_key,
        context=context,
        voice_reference_file=voice_reference_file,
    )

    # Check if analysis succeeded
    if "error" in result:
        print(f"  ⚠️  Analysis failed: {result['error']}")
        clip["analysis"] = None
        clip["analysisError"] = result["error"]
        stats.error_count += 1
    else:
        # Add results to clip (exclude _meta for cleaner output)
        clip["analysis"] = {
            "audioType": result.get("audioType"),
            "transcript": result.get("transcript"),
            "audioEvents": result.get("audioEvents"),
            "sceneDescription": result.get("sceneDescription"),
            "emotionalTone": result.get("emotionalTone"),
        }

        # Update statistics
        utterance_count = len(result.get("transcript", []))
        event_count = len(result.get("audioEvents", []))
        audio_type = result.get("audioType", "unknown")

        stats.audio_type_counts[audio_type] = stats.audio_type_counts.get(audio_type, 0) + 1
        stats.total_utterances += utterance_count
        stats.total_audio_events += event_count

        # Print brief result
        print(f"  ✓ {audio_type}, {utterance_count} utterances, {event_count} audio events")

        # Show verbose output if requested
        if verbose and result.get("transcript"):
            print("\n  Transcript:")
            for utterance in result["transcript"]:
                speaker = utterance.get("speaker", "Unknown")
                text = utterance.get("text", "")
                timestamp = utterance.get("timestamp", "00:00")
                print(f"    [{timestamp}] {speaker}: {text}")

        stats.processed_count += 1


def process_clips(
    clips: list[dict[str, Any]],
    extracted_folder: str,
    travelers: list[dict[str, Any]],
    story_beats_lookup: dict[str, dict[str, Any]],
    api_key: Optional[str],
    voice_reference_file: Any,
    has_voice_reference: bool,
    verbose: bool,
    dry_run: bool,
) -> ProcessingStats:
    """
    Process all clips.

    Args:
        clips: List of clip metadata
        extracted_folder: Path to extracted ZIP contents
        travelers: List of traveler information
        story_beats_lookup: Dictionary mapping story beat IDs to their data
        api_key: Gemini API key (None for dry run)
        voice_reference_file: Optional uploaded voice reference
        has_voice_reference: Whether voice reference is available
        verbose: Whether to show verbose output
        dry_run: Whether this is a dry run

    Returns:
        Processing statistics
    """
    print("\n" + "=" * 60)
    print("PROCESSING CLIPS")
    print("=" * 60)

    stats = ProcessingStats()

    for idx, clip in enumerate(clips, 1):
        clip_filename = clip.get("filename", "unknown")
        percentage = int((idx / len(clips)) * 100)
        print(f"\nProcessing clip {idx}/{len(clips)} ({percentage}%): {clip_filename}")

        try:
            # Build clip-specific context
            context = build_clip_context(clip, travelers, story_beats_lookup)

            # Track clips with story beats
            if context.get("storyBeatContext"):
                stats.clips_with_story_beats += 1

            # Resolve story beat for enriched output
            story_beat_id = clip.get("storyBeatId")
            if story_beat_id and story_beats_lookup:
                story_beat = story_beats_lookup.get(story_beat_id)
                if story_beat:
                    clip["storyBeat"] = {
                        "id": story_beat_id,
                        "text": story_beat.get("text"),
                        "starred": story_beat.get("starred", False),
                    }

            # Build full path to audio file
            audio_path = Path(extracted_folder) / clip_filename
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Dry run mode - show what would be processed
            if dry_run:
                print(f"  [DRY RUN] Would analyze: {audio_path}")
                print(
                    f"  [DRY RUN] Context: {len(travelers)} travelers, "
                    f"location: {context.get('location', 'N/A')}"
                )
                if context.get("storyBeatContext"):
                    starred = " (starred)" if context.get("storyBeatStarred") else ""
                    print(f"  [DRY RUN] Story beat: {context['storyBeatContext'][:50]}...{starred}")
                if has_voice_reference:
                    print(f"  [DRY RUN] Voice reference: {VOICE_REFERENCE_FILENAME}")
                continue

            # Analyze the audio
            if api_key is None:
                raise ValueError("API key is required for audio analysis")

            process_single_clip(
                clip, audio_path, context, api_key, voice_reference_file, verbose, stats
            )

        except Exception as e:
            print(f"  ✗ Error: {e}")
            clip["analysis"] = None
            clip["analysisError"] = str(e)
            stats.error_count += 1

    return stats


def print_final_summary(
    stats: ProcessingStats,
    num_clips: int,
    story_beats_lookup: dict[str, dict[str, Any]],
    dry_run: bool,
) -> None:
    """Print the final processing summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if dry_run:
        print(f"Dry run complete! Would process {num_clips} clips")
    else:
        print(f"Done! Processed {stats.processed_count}/{num_clips} clips successfully")
        if stats.error_count > 0:
            print(f"Errors: {stats.error_count} clips failed")

        # Show audio type breakdown
        if stats.audio_type_counts:
            print("\nAudio Type Breakdown:")
            type_summary = ", ".join(
                [f"{count} {atype}" for atype, count in sorted(stats.audio_type_counts.items())]
            )
            print(f"  {type_summary}")

        # Show story beat stats
        if story_beats_lookup:
            story_beats = list(story_beats_lookup.values())
            starred_count = sum(1 for beat in story_beats if beat.get("starred"))
            print(f"\nStory Beats: {len(story_beats)} ({starred_count} starred)")
            print(f"  {stats.clips_with_story_beats} clips are reactions to story beats")

        # Show totals
        print("\nTotals:")
        print(f"  {stats.total_utterances} utterances transcribed")
        print(f"  {stats.total_audio_events} audio events detected")

    print("=" * 60)


def main() -> None:
    """
    Process a Travel Chronicle export ZIP file.

    Usage: python process.py /path/to/export.zip [--verbose] [--dry-run]
    """
    args = parse_args()
    zip_path = args.zip_path
    verbose = args.verbose
    dry_run = args.dry_run

    api_key = validate_inputs(zip_path, dry_run)

    try:
        output_dir = DEFAULT_OUTPUT_DIR
        print_header(dry_run)

        # Extract ZIP and load metadata
        extracted_folder = extract_zip(zip_path, output_dir)
        metadata_path = Path(extracted_folder) / "metadata.json"
        metadata = load_metadata(metadata_path)

        # Auto-detect voice reference in extracted folder
        voice_reference_path = detect_voice_reference(extracted_folder)
        if voice_reference_path:
            print(f"\nVoice reference found: {VOICE_REFERENCE_FILENAME} ✓")
        else:
            print("\nNo voice reference (speaker ID may be less accurate)")

        # Print trip summary and extract data
        _, clips, travelers, story_beats_lookup = print_trip_summary(metadata)

        # Upload voice reference once if found
        voice_reference_file = None
        if voice_reference_path and not dry_run and api_key:
            voice_reference_file = upload_voice_reference(
                str(voice_reference_path), api_key, len(clips)
            )

        # Process all clips
        stats = process_clips(
            clips,
            extracted_folder,
            travelers,
            story_beats_lookup,
            api_key,
            voice_reference_file,
            voice_reference_path is not None,
            verbose,
            dry_run,
        )

        # Save enriched metadata
        if not dry_run:
            print("\n" + "=" * 60)
            print("SAVING RESULTS")
            print("=" * 60)
            enriched_output_path = Path(output_dir) / "enriched_metadata.json"
            save_metadata(metadata, enriched_output_path)

        # Print final summary
        print_final_summary(stats, len(clips), story_beats_lookup, dry_run)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
