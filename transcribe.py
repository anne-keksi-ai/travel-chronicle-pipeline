#!/usr/bin/env python3
# Travel Chronicle - OpenAI Transcription with Speaker Diarization

import base64
from pathlib import Path
from typing import Any

from openai import OpenAI


def encode_audio_as_data_url(path: Path) -> str:
    """
    Encode an audio file as a base64 data URL.

    Args:
        path: Path to the audio file

    Returns:
        Data URL string like "data:audio/webm;base64,..."
    """
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    # Determine mime type from extension
    suffix = path.suffix.lower()
    mime_types = {
        ".webm": "audio/webm",
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
    }
    mime_type = mime_types.get(suffix, "audio/webm")

    return f"data:{mime_type};base64,{data}"


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "01:23"
    """
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def transcribe_with_diarization(
    clip_path: Path,
    voice_references: list[tuple[dict[str, Any], Path]],
    api_key: str,
) -> dict[str, Any]:
    """
    Transcribe an audio clip with speaker diarization using OpenAI.

    Args:
        clip_path: Path to the audio clip to transcribe
        voice_references: List of (traveler_dict, voice_ref_path) tuples
            Each traveler_dict should have at least {"name": "..."}
        api_key: OpenAI API key

    Returns:
        dict with:
            - transcript: list of {timestamp, speaker, text} entries
            - _meta: metadata about the transcription
    """
    client = OpenAI(api_key=api_key)

    # Prepare known speaker names and references
    known_speaker_names = []
    known_speaker_references = []

    for traveler, ref_path in voice_references:
        if ref_path.exists():
            known_speaker_names.append(traveler["name"])
            known_speaker_references.append(encode_audio_as_data_url(ref_path))

    print(f"Transcribing with {len(known_speaker_names)} voice references: {known_speaker_names}")

    # Call OpenAI API
    with open(clip_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe-diarize",
            file=audio_file,
            response_format="json",
            extra_body={
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
                "known_speaker_names": known_speaker_names,
                "known_speaker_references": known_speaker_references,
            },
        )

    # Convert response to dict
    response_dict = response.model_dump() if hasattr(response, "model_dump") else dict(response)

    # Transform segments into our transcript format
    transcript = []
    segments = response_dict.get("segments", [])

    for segment in segments:
        text = segment.get("text", "").strip()
        if not text:
            continue

        transcript.append(
            {
                "timestamp": format_timestamp(segment.get("start", 0)),
                "speaker": segment.get("speaker", "Unknown"),
                "text": text,
            }
        )

    return {
        "transcript": transcript,
        "_meta": {
            "model": "gpt-4o-transcribe-diarize",
            "voice_references": known_speaker_names,
            "raw_response": response_dict,
        },
    }


def transcribe_without_diarization(
    clip_path: Path,
    api_key: str,
) -> dict[str, Any]:
    """
    Transcribe an audio clip without speaker diarization.

    Use this when no voice references are available.

    Args:
        clip_path: Path to the audio clip to transcribe
        api_key: OpenAI API key

    Returns:
        dict with transcript (speakers labeled A, B, C, etc.)
    """
    client = OpenAI(api_key=api_key)

    print("Transcribing without voice references (speakers will be labeled A, B, C...)")

    with open(clip_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe-diarize",
            file=audio_file,
            response_format="json",
            extra_body={
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
            },
        )

    response_dict = response.model_dump() if hasattr(response, "model_dump") else dict(response)

    transcript = []
    for segment in response_dict.get("segments", []):
        text = segment.get("text", "").strip()
        if not text:
            continue

        transcript.append(
            {
                "timestamp": format_timestamp(segment.get("start", 0)),
                "speaker": segment.get("speaker", "Unknown"),
                "text": text,
            }
        )

    return {
        "transcript": transcript,
        "_meta": {
            "model": "gpt-4o-transcribe-diarize",
            "voice_references": [],
            "raw_response": response_dict,
        },
    }
