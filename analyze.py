#!/usr/bin/env python3
# Travel Chronicle - Audio Analysis

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from dotenv import load_dotenv
from google import genai

if TYPE_CHECKING:
    from audio_utils import ConcatenatedAudio

# Constants
DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_AUDIO_MIME_TYPE = "audio/webm"

# Regex pattern to extract JSON from markdown code blocks
# Matches ```json ... ``` or ``` ... ``` with optional language specifier
_JSON_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.MULTILINE)


def extract_json_from_text(text: str) -> str:
    """
    Extract JSON content from text that may be wrapped in markdown code blocks.

    Handles various formats:
    - Plain JSON
    - ```json ... ```
    - ``` ... ```

    Args:
        text: Text that may contain JSON

    Returns:
        Extracted JSON string (or original text if no code block found)
    """
    if not text:
        return ""

    text = text.strip()

    # Try to find a code block with JSON
    match = _JSON_CODE_BLOCK_PATTERN.search(text)
    if match:
        return match.group(1).strip()

    # No code block found, return as-is (might already be plain JSON)
    return text


def format_traveler(traveler: dict[str, Any]) -> str:
    """
    Format a traveler dict as a display string.

    Args:
        traveler: Dict with 'name' and optional 'age' keys

    Returns:
        Formatted string like "Alice (age 9)" or "Mom"
    """
    name = str(traveler["name"])
    # age can be missing, None, or a valid number
    age = traveler.get("age")
    if age is not None:
        return f"{name} (age {age})"
    return name


def summarize_story_beat(story_text: str, api_key: str) -> str:
    """
    Summarize a story beat text into a concise 1-2 sentence summary.

    Args:
        story_text: The full story beat text to summarize
        api_key: Gemini API key

    Returns:
        A brief summary capturing the main point of the story
    """
    # Skip summarization for already-short texts
    if len(story_text) < 200:
        return story_text

    client = genai.Client(api_key=api_key)

    prompt = f"""Summarize this story in ONE sentence (max 30 words).
Capture the main historical fact or interesting point being shared.

Story:
{story_text}

Summary:"""

    response = client.models.generate_content(model=DEFAULT_MODEL, contents=[prompt])

    summary = response.text.strip() if response.text else story_text
    # Remove any quotes that might wrap the summary
    summary = summary.strip("\"'")
    return summary


def analyze_audio(
    audio_path: str,
    api_key: str,
    context: Optional[dict[str, Any]] = None,
    concatenated_audio: Optional["ConcatenatedAudio"] = None,
) -> dict[str, Any]:
    """
    Analyze an audio clip using Gemini.

    Args:
        audio_path: Path to the audio file (or concatenated file if concatenated_audio provided)
        api_key: Gemini API key
        context: Optional dictionary with:
            - travelers: list of {"name": "Ellen", "age": 7}, {"name": "Mom"}, etc.
            - location: "La Mina Falls, El Yunque"
            - storyBeatContext: "Story about Princess Louise-Hippolyte..."
            - recordedAt: "2024-12-28T14:34:22Z"
        concatenated_audio: Optional ConcatenatedAudio object with timing information
            for voice references and clip location in a single concatenated file

    Returns:
        dict with: audioType, transcript, audioEvents, sceneDescription, emotionalTone
    """
    from audio_utils import format_timestamp

    # Create Gemini client
    client = genai.Client(api_key=api_key)

    # Check if file exists
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Uploading audio file: {audio_file.name}")

    # Upload the audio file with explicit mime type
    with open(audio_file, "rb") as f:
        uploaded_file = client.files.upload(file=f, config={"mime_type": DEFAULT_AUDIO_MIME_TYPE})
    print(f"Upload complete. File name: {uploaded_file.name}")

    # Build prompt dynamically based on context
    prompt = ""

    # Add voice reference instructions for concatenated audio
    if concatenated_audio and concatenated_audio.voice_reference_segments:
        clip_start_ts = format_timestamp(concatenated_audio.clip_start_ms)

        prompt += "This audio file contains VOICE REFERENCES followed by a CLIP TO ANALYZE.\n\n"
        prompt += "VOICE REFERENCES (learn each person's voice):\n"

        for traveler, start_ms, end_ms in concatenated_audio.voice_reference_segments:
            start_ts = format_timestamp(start_ms)
            end_ts = format_timestamp(end_ms)
            prompt += f"- {format_traveler(traveler)}: {start_ts} to {end_ts}\n"

        # Note travelers without voice references
        if context and context.get("travelers"):
            voice_ref_names = {t["name"] for t, _, _ in concatenated_audio.voice_reference_segments}
            missing_travelers = [
                t for t in context["travelers"] if t["name"] not in voice_ref_names
            ]
            if missing_travelers:
                missing_names = ", ".join(format_traveler(t) for t in missing_travelers)
                prompt += f"\nNote: {missing_names} did not record a voice reference.\n"

        prompt += f"\nCLIP TO ANALYZE: starts at {clip_start_ts}\n\n"
        prompt += "First, listen to each voice reference segment to learn how each person sounds. "
        prompt += f"Then analyze the clip starting at {clip_start_ts} and identify speakers by matching their voices.\n\n"

    else:
        prompt += "Analyze this audio clip recorded during a family trip.\n\n"

    if context:
        prompt += "CONTEXT:\n"

        # Add traveler information
        if context.get("travelers"):
            travelers_str = ", ".join(format_traveler(t) for t in context["travelers"])
            prompt += f"- Travelers: {travelers_str}\n"

        # Add location
        if context.get("location"):
            prompt += f"- Location: {context['location']}\n"

        # Add story beat context
        if context.get("storyBeatContext"):
            prompt += f'- This was recorded as a reaction to a story about: "{context["storyBeatContext"]}"\n'
            if context.get("storyBeatStarred"):
                prompt += "- This story beat was starred as a favorite by the family.\n"

        # Add timestamp
        if context.get("recordedAt"):
            # Parse ISO timestamp and format it nicely
            dt = datetime.fromisoformat(context["recordedAt"].replace("Z", "+00:00"))
            formatted_time = dt.strftime("%B %d, %Y, %I:%M %p")
            prompt += f"- Recorded at: {formatted_time}\n"

        prompt += "\nGiven this context, analyze the audio.\n\n"

    # Add analysis instructions
    prompt += """Analyze the audio and respond with JSON in this exact format:

{
  "audioType": "speech|ambient|mixed|music|silent",
  "transcript": [
    {
      "timestamp": "00:00",
      "speaker": "Dad",
      "text": "How is it, girls?"
    }
  ],
  "audioEvents": [
    {
      "timestamp": "00:01",
      "event": "rushing water from waterfall"
    }
  ],
  "sceneDescription": "Brief description of the overall scene",
  "emotionalTone": "excited|happy|calm|curious|frustrated|etc."
}

IMPORTANT:
- audioType: Choose one of: speech, ambient, mixed, music, silent
- transcript: Array of dialogue with timestamps. """

    if context and context.get("travelers"):
        prompt += "Use actual traveler names if you can identify them (e.g., 'Ellen' instead of 'Child'). "

    prompt += """If unsure, use 'Child', 'Adult Female', or 'Adult Male'.
- audioEvents: Non-speech sounds (background noise, ambient sounds, etc.)
- sceneDescription: 1-2 sentences describing what's happening
- emotionalTone: Overall mood/feeling of the clip

Respond ONLY with valid JSON, no additional text."""

    # Send prompt with the audio file
    print("Analyzing audio...")

    # Build contents list - single audio file and prompt
    contents: list[Any] = [uploaded_file, prompt]

    response = client.models.generate_content(model=DEFAULT_MODEL, contents=contents)

    # Parse the JSON response
    try:
        # Extract the response text
        response_text = response.text if response.text else ""

        # Extract JSON from potential markdown code blocks
        json_text = extract_json_from_text(response_text)

        # Parse the JSON
        result: dict[str, Any] = json.loads(json_text)

        # Add metadata
        result["_meta"] = {"prompt": prompt, "context": context, "raw_response": response.text}

        return result

    except json.JSONDecodeError as e:
        # If JSON parsing fails, return error with raw text
        print(f"Warning: Failed to parse JSON response: {e}")
        return {
            "error": "Failed to parse JSON response",
            "error_details": str(e),
            "raw_response": response.text,
            "_meta": {"prompt": prompt, "context": context},
        }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze.py /path/to/audio.webm")
        sys.exit(1)

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]

    try:
        # Sample context for testing
        test_context = {
            "travelers": [
                {"name": "Ellen", "age": 7},
                {"name": "Alina", "age": 8},
                {"name": "Mom"},
                {"name": "Dad"},
            ],
            "location": "La Mina Falls, El Yunque",
            "recordedAt": "2024-12-28T14:34:22Z",
            "storyBeatContext": "Princess Louise-Hippolyte who ruled Monaco",
        }

        # Analyze the audio with context
        result = analyze_audio(audio_path, api_key, context=test_context)

        # Print results
        print("\n" + "=" * 60)
        print("ANALYSIS RESULT:")
        print("=" * 60)

        if "error" in result:
            print(f"Error: {result['error']}")
            print(f"Details: {result['error_details']}")
            print(f"\nRaw response:\n{result['raw_response']}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

        print("=" * 60)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
