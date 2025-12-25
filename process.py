#!/usr/bin/env python3
# Travel Chronicle - Audio Processing Pipeline
#
# Hybrid approach:
# - OpenAI gpt-4o-transcribe-diarize for transcript with speaker identification
# - Gemini 3 Flash for audioType, audioEvents, sceneDescription, emotionalTone

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from analyze import analyze_audio, summarize_story_beat
from transcribe import transcribe_with_diarization, transcribe_without_diarization
from utils import extract_zip, load_metadata, save_metadata

# Constants
DEFAULT_OUTPUT_BASE = "./output"
VOICE_REFERENCE_FILENAME = "voice_reference.webm"
VOICE_REFERENCES_FOLDER = "voice_references"


def generate_output_dir(zip_path: str, base_dir: str = DEFAULT_OUTPUT_BASE) -> str:
    """
    Generate a versioned output directory path based on ZIP filename and timestamp.

    Args:
        zip_path: Path to the input ZIP file
        base_dir: Base output directory

    Returns:
        Path like "./output/day_at_home_v2_2025-12-24_185031"
    """
    # Get ZIP filename without extension
    zip_name = Path(zip_path).stem

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # Combine into output directory path
    output_dir = Path(base_dir) / f"{zip_name}_{timestamp}"

    return str(output_dir)


@dataclass
class ApiKeys:
    """API keys for the pipeline."""

    gemini: str
    openai: str


@dataclass
class VoiceReference:
    """A voice reference file with associated traveler info."""

    traveler: dict[str, Any]
    file_path: Path


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


def summarize_story_beats(
    story_beats_lookup: dict[str, dict[str, Any]], api_key: str
) -> dict[str, str]:
    """
    Summarize all story beats into concise descriptions.

    Args:
        story_beats_lookup: Dictionary mapping story beat IDs to their full data
        api_key: Gemini API key

    Returns:
        Dictionary mapping story beat IDs to their summaries
    """
    if not story_beats_lookup:
        return {}

    print("\n" + "=" * 60)
    print("SUMMARIZING STORY BEATS")
    print("=" * 60)

    summaries: dict[str, str] = {}
    total = len(story_beats_lookup)

    for idx, (beat_id, beat) in enumerate(story_beats_lookup.items(), 1):
        text = beat.get("text", "")
        if not text:
            continue

        print(f"Summarizing story beat {idx}/{total}...")
        summary = summarize_story_beat(text, api_key)
        summaries[beat_id] = summary
        print(f"  → {summary[:80]}{'...' if len(summary) > 80 else ''}")

    print(f"\n{len(summaries)} story beats summarized")
    print("=" * 60)

    return summaries


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


def validate_inputs(zip_path: str, dry_run: bool) -> Optional[ApiKeys]:
    """
    Validate input files and load API keys.

    Args:
        zip_path: Path to the ZIP file
        dry_run: Whether this is a dry run (API keys not required)

    Returns:
        ApiKeys if not dry run, None otherwise

    Raises:
        SystemExit: If validation fails
    """
    # Validate ZIP file exists
    if not Path(zip_path).exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    # Load environment variables and get API keys
    load_dotenv()
    if dry_run:
        return None

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("Error: GEMINI_API_KEY not found in .env file", file=sys.stderr)
        sys.exit(1)

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("Error: OPENAI_API_KEY not found in .env file", file=sys.stderr)
        sys.exit(1)

    return ApiKeys(gemini=gemini_key, openai=openai_key)


def detect_voice_reference(extracted_folder: str) -> Optional[Path]:
    """
    Check if a legacy single voice reference file exists in the extracted folder.

    Args:
        extracted_folder: Path to the extracted ZIP contents

    Returns:
        Path to voice reference file if found, None otherwise
    """
    voice_ref_path = Path(extracted_folder) / VOICE_REFERENCE_FILENAME
    if voice_ref_path.exists():
        return voice_ref_path
    return None


def load_voice_references(
    extracted_folder: str, travelers: list[dict[str, Any]]
) -> list[VoiceReference]:
    """
    Load individual voice reference files for each traveler.

    Matches files to travelers based on the voiceReferenceFile field in traveler
    metadata. The voiceReferenceFile contains the relative path from the export
    root (e.g., "voice_references/ellen.webm").

    Args:
        extracted_folder: Path to the extracted ZIP contents
        travelers: List of traveler information from metadata

    Returns:
        List of VoiceReference objects for travelers with voice reference files
    """
    extracted_path = Path(extracted_folder)
    voice_references: list[VoiceReference] = []

    for traveler in travelers:
        # voiceReferenceFile contains relative path like "voice_references/ellen.webm"
        # Can be None or missing
        voice_ref_relative_path = traveler.get("voiceReferenceFile")
        if not voice_ref_relative_path:
            continue

        voice_ref_path = extracted_path / voice_ref_relative_path
        if voice_ref_path.exists():
            voice_references.append(VoiceReference(traveler=traveler, file_path=voice_ref_path))

    return voice_references


def print_voice_reference_summary(
    travelers: list[dict[str, Any]], voice_references: list[VoiceReference]
) -> None:
    """
    Print summary of voice reference availability.

    Args:
        travelers: List of all travelers
        voice_references: List of loaded voice references
    """
    from analyze import format_traveler

    if not travelers:
        print("\nNo travelers defined")
        return

    voice_ref_names = [format_traveler(vr.traveler) for vr in voice_references]
    missing_travelers = [
        t for t in travelers if not any(vr.traveler == t for vr in voice_references)
    ]
    missing_names = [format_traveler(t) for t in missing_travelers]

    if voice_references:
        names_str = ", ".join(voice_ref_names)
        print(
            f"\nVoice references found: {names_str} ({len(voice_references)}/{len(travelers)} travelers)"
        )
        if missing_names:
            missing_str = ", ".join(missing_names)
            print(f"Missing voice reference: {missing_str}")
    else:
        print("\nNo voice references (speaker ID may be less accurate)")


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


def build_clip_context(
    clip: dict[str, Any],
    travelers: list[dict[str, Any]],
    story_beats_lookup: Optional[dict[str, dict[str, Any]]] = None,
    story_beat_summaries: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Build context dictionary for a clip.

    Args:
        clip: Clip metadata
        travelers: List of traveler information
        story_beats_lookup: Optional dictionary mapping story beat IDs to their data
        story_beat_summaries: Optional dictionary mapping story beat IDs to summaries

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
            # Use summary if available, otherwise use full text
            if story_beat_summaries and story_beat_id in story_beat_summaries:
                context["storyBeatContext"] = story_beat_summaries[story_beat_id]
            elif story_beat.get("text"):
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
    api_keys: ApiKeys,
    voice_references: list[VoiceReference],
    verbose: bool,
    stats: ProcessingStats,
) -> None:
    """
    Process a single audio clip using hybrid approach.

    Uses OpenAI for transcription with speaker diarization,
    and Gemini for audioType, audioEvents, sceneDescription, emotionalTone.

    Args:
        clip: Clip metadata (modified in place)
        audio_path: Path to audio file
        context: Context dictionary
        api_keys: API keys for both services
        voice_references: List of voice references for speaker identification
        verbose: Whether to show verbose output
        stats: Statistics object (modified in place)
    """
    try:
        # Step 1: Transcribe with OpenAI (speaker diarization)
        voice_ref_tuples = [(vr.traveler, vr.file_path) for vr in voice_references]

        if voice_ref_tuples:
            transcription_result = transcribe_with_diarization(
                audio_path,
                voice_ref_tuples,
                api_keys.openai,
            )
        else:
            transcription_result = transcribe_without_diarization(
                audio_path,
                api_keys.openai,
            )

        transcript = transcription_result.get("transcript", [])

        # Step 2: Analyze with Gemini (audioType, audioEvents, sceneDescription, emotionalTone)
        analysis_result = analyze_audio(
            str(audio_path),
            api_keys.gemini,
            context=context,
        )

        # Check if analysis succeeded
        if "error" in analysis_result:
            print(f"  ⚠️  Analysis failed: {analysis_result['error']}")
            clip["analysis"] = None
            clip["analysisError"] = analysis_result["error"]
            stats.error_count += 1
        else:
            # Merge results from both APIs
            clip["analysis"] = {
                "audioType": analysis_result.get("audioType"),
                "transcript": transcript,  # From OpenAI
                "audioEvents": analysis_result.get("audioEvents"),
                "sceneDescription": analysis_result.get("sceneDescription"),
                "emotionalTone": analysis_result.get("emotionalTone"),
            }

            # Update statistics
            utterance_count = len(transcript)
            event_count = len(analysis_result.get("audioEvents", []))
            audio_type = analysis_result.get("audioType", "unknown")

            stats.audio_type_counts[audio_type] = stats.audio_type_counts.get(audio_type, 0) + 1
            stats.total_utterances += utterance_count
            stats.total_audio_events += event_count

            # Print brief result
            print(f"  ✓ {audio_type}, {utterance_count} utterances, {event_count} audio events")

            # Show verbose output if requested
            if verbose and transcript:
                print("\n  Transcript:")
                for utterance in transcript:
                    speaker = utterance.get("speaker", "Unknown")
                    text = utterance.get("text", "")
                    timestamp = utterance.get("timestamp", "00:00")
                    print(f"    [{timestamp}] {speaker}: {text}")

            stats.processed_count += 1

    except Exception as e:
        print(f"  ⚠️  Processing failed: {e}")
        clip["analysis"] = None
        clip["analysisError"] = str(e)
        stats.error_count += 1


def process_clips(
    clips: list[dict[str, Any]],
    extracted_folder: str,
    travelers: list[dict[str, Any]],
    story_beats_lookup: dict[str, dict[str, Any]],
    story_beat_summaries: dict[str, str],
    api_keys: Optional[ApiKeys],
    voice_references: list[VoiceReference],
    verbose: bool,
    dry_run: bool,
) -> ProcessingStats:
    """
    Process all clips using hybrid approach (OpenAI + Gemini).

    Args:
        clips: List of clip metadata
        extracted_folder: Path to extracted ZIP contents
        travelers: List of traveler information
        story_beats_lookup: Dictionary mapping story beat IDs to their data
        story_beat_summaries: Dictionary mapping story beat IDs to summaries
        api_keys: API keys for OpenAI and Gemini (None for dry run)
        voice_references: List of voice references for speaker identification
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
            context = build_clip_context(clip, travelers, story_beats_lookup, story_beat_summaries)

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
                from analyze import format_traveler

                print(f"  [DRY RUN] Would analyze: {audio_path}")
                print(
                    f"  [DRY RUN] Context: {len(travelers)} travelers, "
                    f"location: {context.get('location', 'N/A')}"
                )
                if context.get("storyBeatContext"):
                    starred = " (starred)" if context.get("storyBeatStarred") else ""
                    print(f"  [DRY RUN] Story beat: {context['storyBeatContext'][:50]}...{starred}")
                if voice_references:
                    voice_ref_names = [format_traveler(vr.traveler) for vr in voice_references]
                    print(f"  [DRY RUN] Voice references: {', '.join(voice_ref_names)}")
                    print("  [DRY RUN] Would use OpenAI for transcription + Gemini for analysis")
                continue

            # Analyze the audio
            if api_keys is None:
                raise ValueError("API keys are required for audio analysis")

            process_single_clip(
                clip,
                audio_path,
                context,
                api_keys,
                voice_references,
                verbose,
                stats,
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

    api_keys = validate_inputs(zip_path, dry_run)

    try:
        output_dir = generate_output_dir(zip_path)
        print_header(dry_run)

        # Extract ZIP and load metadata
        extracted_folder = extract_zip(zip_path, output_dir)
        metadata_path = Path(extracted_folder) / "metadata.json"
        metadata = load_metadata(metadata_path)

        # Print trip summary and extract data
        _, clips, travelers, story_beats_lookup = print_trip_summary(metadata)

        # Load individual voice references (new format)
        voice_references = load_voice_references(extracted_folder, travelers)

        # Auto-detect legacy single voice reference
        voice_reference_path = detect_voice_reference(extracted_folder)

        # Print voice reference summary
        if voice_references:
            # Individual voice references (new format)
            print_voice_reference_summary(travelers, voice_references)
        elif voice_reference_path:
            # Legacy single voice reference - not currently supported
            print(f"\nLegacy voice reference found: {VOICE_REFERENCE_FILENAME}")
            print("Note: Legacy format not supported. Please use individual voice references.")
        else:
            print("\nNo voice references (speaker ID may be less accurate)")

        # Summarize story beats (skip in dry run mode)
        story_beat_summaries: dict[str, str] = {}
        if not dry_run and api_keys and story_beats_lookup:
            story_beat_summaries = summarize_story_beats(story_beats_lookup, api_keys.gemini)

        # Process all clips using hybrid approach (OpenAI + Gemini)
        stats = process_clips(
            clips,
            extracted_folder,
            travelers,
            story_beats_lookup,
            story_beat_summaries,
            api_keys,
            voice_references,
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
