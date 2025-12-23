#!/usr/bin/env python3
# Travel Chronicle - Audio Analysis

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai


def analyze_audio(
    audio_path: str,
    api_key: str,
    context: Optional[dict[str, Any]] = None,
    voice_reference_file=None,
) -> dict[str, Any]:
    """
    Analyze an audio clip using Gemini.

    Args:
        audio_path: Path to the audio file
        api_key: Gemini API key
        context: Optional dictionary with:
            - travelers: list of {"name": "Ellen", "age": 7}, {"name": "Mom"}, etc.
            - location: "La Mina Falls, El Yunque"
            - storyBeatContext: "Story about Princess Louise-Hippolyte..."
            - recordedAt: "2024-12-28T14:34:22Z"
        voice_reference_file: Optional already-uploaded voice reference file object

    Returns:
        dict with: audioType, transcript, audioEvents, sceneDescription, emotionalTone
    """
    # Create Gemini client
    client = genai.Client(api_key=api_key)

    # Check if file exists
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Uploading audio file: {audio_file.name}")

    # Upload the audio file with explicit mime type
    with open(audio_file, "rb") as f:
        uploaded_file = client.files.upload(file=f, config={"mime_type": "audio/webm"})
    print(f"Upload complete. File name: {uploaded_file.name}")

    # Build prompt dynamically based on context
    prompt = ""

    # Add voice reference instructions if provided
    if voice_reference_file:
        prompt += "I'm providing two audio files:\n"
        prompt += "1. VOICE REFERENCE: A recording where each family member introduces themselves by name\n"
        prompt += "2. CLIP TO ANALYZE: The actual audio clip to transcribe\n\n"

        prompt += "First, listen to the VOICE REFERENCE to learn each person's voice"
        if context and context.get("travelers"):
            prompt += ":\n"
            for traveler in context["travelers"]:
                name = traveler["name"]
                age_str = f" (age {traveler['age']})" if "age" in traveler else ""
                prompt += f"- How {name}{age_str} sounds\n"
        else:
            prompt += ".\n"

        prompt += "\nThen analyze the CLIP TO ANALYZE and identify speakers by matching their voices to the reference.\n\n"
    else:
        prompt += "Analyze this audio clip recorded during a family trip.\n\n"

    if context:
        prompt += "CONTEXT:\n"

        # Add traveler information
        if context.get("travelers"):
            travelers_str = ", ".join(
                [
                    f"{t['name']} (age {t['age']})" if "age" in t else t["name"]
                    for t in context["travelers"]
                ]
            )
            prompt += f"- Travelers: {travelers_str}\n"

        # Add location
        if context.get("location"):
            prompt += f"- Location: {context['location']}\n"

        # Add story beat context
        if context.get("storyBeatContext"):
            prompt += f"- This was recorded as a reaction to a story about: \"{context['storyBeatContext']}\"\n"

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

    # Send prompt with the audio file(s)
    print("Analyzing audio...")

    # Build contents list - include voice reference first if provided
    contents = []
    if voice_reference_file:
        contents.append(voice_reference_file)
    contents.append(uploaded_file)
    contents.append(prompt)

    response = client.models.generate_content(model="gemini-3-flash-preview", contents=contents)

    # Parse the JSON response
    try:
        # Extract the response text
        response_text = response.text
        if response_text is None:
            response_text = ""
        response_text = response_text.strip()

        # Try to find JSON in the response (sometimes LLMs wrap it in markdown)
        if "```json" in response_text:
            # Extract JSON from markdown code block
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            # Extract from generic code block
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        # Parse the JSON
        result: dict[str, Any] = json.loads(response_text)

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
