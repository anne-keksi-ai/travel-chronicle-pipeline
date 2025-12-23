#!/usr/bin/env python3
# Travel Chronicle - Audio Processing Pipeline

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from analyze import analyze_audio
from utils import extract_zip, load_metadata, save_metadata


def main():
    """
    Process a Travel Chronicle export ZIP file.

    Usage: python process.py /path/to/export.zip [--verbose] [--dry-run]
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Process Travel Chronicle export ZIP files with AI audio analysis'
    )
    parser.add_argument('zip_path', help='Path to the export ZIP file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show full transcripts for each clip')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be processed without calling Gemini API')
    parser.add_argument('--voice-reference', type=str, metavar='PATH',
                        help='Path to voice reference file where family members introduce themselves')

    args = parser.parse_args()
    zip_path = args.zip_path
    verbose = args.verbose
    dry_run = args.dry_run
    voice_reference = args.voice_reference

    # Validate ZIP file exists
    if not Path(zip_path).exists():
        print(f"Error: ZIP file not found: {zip_path}")
        sys.exit(1)

    # Validate voice reference file if provided
    if voice_reference and not Path(voice_reference).exists():
        print(f"Error: Voice reference file not found: {voice_reference}")
        sys.exit(1)

    try:
        # Load environment variables and get API key
        load_dotenv()
        api_key = None
        if not dry_run:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("Error: GEMINI_API_KEY not found in .env file", file=sys.stderr)
                sys.exit(1)

        # Create output directory
        output_dir = "./output"
        print("="*60)
        print("TRAVEL CHRONICLE PROCESSING PIPELINE")
        if dry_run:
            print("(DRY RUN MODE - No API calls will be made)")
        if voice_reference:
            print(f"Voice Reference: {Path(voice_reference).name}")
        print("="*60)

        # Extract ZIP
        extracted_folder = extract_zip(zip_path, output_dir)

        # Load metadata.json
        metadata_path = Path(extracted_folder) / "metadata.json"
        metadata = load_metadata(str(metadata_path))

        # Print summary
        print("\n" + "="*60)
        print("TRIP SUMMARY")
        print("="*60)

        # Handle both old and new metadata structures
        trip_data = metadata.get('trip', {})
        trip_name = trip_data.get('name') or metadata.get('tripName', 'Unknown')
        print(f"Trip Name: {trip_name}")

        # Get trip ID and export date if available
        if trip_data.get('id'):
            print(f"Trip ID: {trip_data['id']}")
        if trip_data.get('exportedAt'):
            print(f"Exported At: {trip_data['exportedAt']}")

        clips = metadata.get('clips', [])
        print(f"Number of Clips: {len(clips)}")

        # List travelers (check both 'talent' and 'travelers')
        travelers = trip_data.get('talent') or metadata.get('travelers', [])
        if travelers:
            print("\nTalent/Travelers:")
            for traveler in travelers:
                if 'age' in traveler:
                    print(f"  - {traveler['name']} (age {traveler['age']})")
                else:
                    print(f"  - {traveler['name']}")
        else:
            print("\nTalent/Travelers: None specified")

        print("="*60)

        # Get trip-level context
        trip_data = metadata.get('trip', {})
        travelers = trip_data.get('talent') or metadata.get('travelers', [])
        clips = metadata.get('clips', [])

        # Upload voice reference once if provided
        voice_reference_file = None
        if voice_reference and not dry_run:
            from google import genai
            print("\n" + "="*60)
            print("UPLOADING VOICE REFERENCE")
            print("="*60)

            voice_ref_path = Path(voice_reference)
            print(f"Uploading voice reference: {voice_ref_path.name}")

            client = genai.Client(api_key=api_key)
            with open(voice_ref_path, 'rb') as f:
                voice_reference_file = client.files.upload(file=f, config={'mime_type': 'audio/webm'})

            print(f"Voice reference uploaded. File name: {voice_reference_file.name}")
            print(f"This reference will be used for all {len(clips)} clips")
            print("="*60)

        # Process each clip
        print("\n" + "="*60)
        print("PROCESSING CLIPS")
        print("="*60)

        processed_count = 0
        error_count = 0

        # Statistics tracking
        audio_type_counts = {}
        total_utterances = 0
        total_audio_events = 0

        for idx, clip in enumerate(clips, 1):
            clip_filename = clip.get('filename', 'unknown')
            percentage = int((idx / len(clips)) * 100)
            print(f"\nProcessing clip {idx}/{len(clips)} ({percentage}%): {clip_filename}")

            try:
                # Build clip-specific context
                context = {
                    "travelers": travelers if travelers else []
                }

                # Add location if available (handle None gracefully)
                location = clip.get('location')
                if location and isinstance(location, dict):
                    place_name = location.get('placeName')
                    if place_name:
                        context["location"] = place_name

                # Add story beat context if available (handle None gracefully)
                story_beat = clip.get('storyBeatContext')
                if story_beat:
                    context["storyBeatContext"] = story_beat

                # Add recorded timestamp if available
                recorded_at = clip.get('recordedAt')
                if recorded_at:
                    context["recordedAt"] = recorded_at

                # Build full path to audio file
                audio_path = Path(extracted_folder) / clip_filename
                if not audio_path.exists():
                    raise FileNotFoundError(f"Audio file not found: {audio_path}")

                # Dry run mode - show what would be processed
                if dry_run:
                    print(f"  [DRY RUN] Would analyze: {audio_path}")
                    print(f"  [DRY RUN] Context: {len(travelers)} travelers, location: {context.get('location', 'N/A')}")
                    if voice_reference:
                        print(f"  [DRY RUN] Voice reference: {Path(voice_reference).name}")
                    continue

                # Analyze the audio
                result = analyze_audio(str(audio_path), api_key, context=context, voice_reference_file=voice_reference_file)

                # Check if analysis succeeded
                if 'error' in result:
                    print(f"  ⚠️  Analysis failed: {result['error']}")
                    clip['analysis'] = None
                    clip['analysisError'] = result['error']
                    error_count += 1
                else:
                    # Add results to clip (exclude _meta for cleaner output)
                    clip['analysis'] = {
                        'audioType': result.get('audioType'),
                        'transcript': result.get('transcript'),
                        'audioEvents': result.get('audioEvents'),
                        'sceneDescription': result.get('sceneDescription'),
                        'emotionalTone': result.get('emotionalTone')
                    }

                    # Update statistics
                    utterance_count = len(result.get('transcript', []))
                    event_count = len(result.get('audioEvents', []))
                    audio_type = result.get('audioType', 'unknown')

                    audio_type_counts[audio_type] = audio_type_counts.get(audio_type, 0) + 1
                    total_utterances += utterance_count
                    total_audio_events += event_count

                    # Print brief result
                    print(f"  ✓ {audio_type}, {utterance_count} utterances, {event_count} audio events")

                    # Show verbose output if requested
                    if verbose and result.get('transcript'):
                        print("\n  Transcript:")
                        for utterance in result['transcript']:
                            speaker = utterance.get('speaker', 'Unknown')
                            text = utterance.get('text', '')
                            timestamp = utterance.get('timestamp', '00:00')
                            print(f"    [{timestamp}] {speaker}: {text}")

                    processed_count += 1

            except Exception as e:
                print(f"  ✗ Error: {e}")
                clip['analysis'] = None
                clip['analysisError'] = str(e)
                error_count += 1

        # Save enriched metadata
        if not dry_run:
            print("\n" + "="*60)
            print("SAVING RESULTS")
            print("="*60)

            enriched_output_path = Path(output_dir) / "enriched_metadata.json"
            save_metadata(metadata, str(enriched_output_path))

        # Print final summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        if dry_run:
            print(f"Dry run complete! Would process {len(clips)} clips")
        else:
            print(f"Done! Processed {processed_count}/{len(clips)} clips successfully")
            if error_count > 0:
                print(f"Errors: {error_count} clips failed")

            # Show audio type breakdown
            if audio_type_counts:
                print("\nAudio Type Breakdown:")
                type_summary = ", ".join([f"{count} {atype}" for atype, count in sorted(audio_type_counts.items())])
                print(f"  {type_summary}")

            # Show totals
            print("\nTotals:")
            print(f"  {total_utterances} utterances transcribed")
            print(f"  {total_audio_events} audio events detected")

        print("="*60)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
