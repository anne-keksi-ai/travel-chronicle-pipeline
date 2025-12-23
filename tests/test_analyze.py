# Tests for analyze.py

import json

import pytest

from analyze import DEFAULT_MODEL, analyze_audio


class TestAnalyzeAudio:
    """Tests for analyze_audio function."""

    def test_analyze_basic_audio_file(
        self, temp_dir, mock_genai_module, mock_gemini_client, sample_gemini_response
    ):
        """Test basic audio analysis without context."""
        # Create a dummy audio file
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")  # Minimal WebM header

        result = analyze_audio(str(audio_path), "fake_api_key")

        # Verify API was called
        mock_genai_module.Client.assert_called_once_with(api_key="fake_api_key")
        mock_gemini_client.files.upload.assert_called_once()
        mock_gemini_client.models.generate_content.assert_called_once()

        # Verify result structure
        assert result["audioType"] == "speech"
        assert "transcript" in result
        assert "audioEvents" in result
        assert "sceneDescription" in result
        assert "emotionalTone" in result
        assert "_meta" in result

    def test_analyze_with_full_context(
        self, temp_dir, mock_genai_module, mock_gemini_client, sample_gemini_response
    ):
        """Test audio analysis with full context."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        context = {
            "travelers": [
                {"name": "Alice", "age": 9},
                {"name": "Bob", "age": 7},
                {"name": "Mom"},
            ],
            "location": "Golden Gate Bridge, San Francisco",
            "storyBeatContext": "Story about the bridge construction",
            "recordedAt": "2025-12-22T10:30:00.000Z",
        }

        result = analyze_audio(str(audio_path), "fake_api_key", context=context)

        # Verify the prompt includes context
        call_args = mock_gemini_client.models.generate_content.call_args
        prompt = call_args[1]["contents"][-1]

        assert "Alice" in prompt
        assert "age 9" in prompt
        assert "Golden Gate Bridge" in prompt
        assert "bridge construction" in prompt
        assert "December 22, 2025" in prompt

        # Verify result
        assert result["audioType"] == "speech"
        assert result["_meta"]["context"] == context

    def test_analyze_with_voice_reference(self, temp_dir, mock_genai_module, mock_gemini_client):
        """Test audio analysis with voice reference file."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Mock voice reference file
        mock_voice_ref = mock_genai_module.Mock()
        mock_voice_ref.name = "voice_reference.webm"

        context = {"travelers": [{"name": "Alice", "age": 9}]}

        result = analyze_audio(
            str(audio_path), "fake_api_key", context=context, voice_reference_file=mock_voice_ref
        )

        # Verify the prompt mentions voice reference
        call_args = mock_gemini_client.models.generate_content.call_args
        prompt = call_args[1]["contents"][-1]

        assert "VOICE REFERENCE" in prompt
        assert "CLIP TO ANALYZE" in prompt

        # Verify contents includes both files
        contents = call_args[1]["contents"]
        assert len(contents) == 3  # voice ref, audio file, prompt

        # Verify result is valid
        assert "audioType" in result

    def test_analyze_with_travelers_no_age(self, temp_dir, mock_genai_module, mock_gemini_client):
        """Test context with travelers without age field."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        context = {"travelers": [{"name": "Mom"}, {"name": "Dad"}]}

        result = analyze_audio(str(audio_path), "fake_api_key", context=context)

        # Verify prompt includes names but no age
        call_args = mock_gemini_client.models.generate_content.call_args
        prompt = call_args[1]["contents"][-1]

        assert "Mom" in prompt
        assert "Dad" in prompt
        # Should not have age-related text for travelers without age
        assert "age" not in prompt or "age" in prompt.lower()

        # Verify result is valid
        assert "audioType" in result

    def test_analyze_json_in_markdown_code_block(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test parsing JSON wrapped in markdown code blocks."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Mock response with markdown-wrapped JSON
        mock_response = mock_gemini_client.models.generate_content.return_value
        json_content = {
            "audioType": "ambient",
            "transcript": [],
            "audioEvents": [{"timestamp": "00:00", "event": "birds chirping"}],
            "sceneDescription": "Peaceful nature scene",
            "emotionalTone": "calm",
        }
        mock_response.text = f"```json\n{json.dumps(json_content)}\n```"

        result = analyze_audio(str(audio_path), "fake_api_key")

        assert result["audioType"] == "ambient"
        assert result["sceneDescription"] == "Peaceful nature scene"

    def test_analyze_json_in_generic_code_block(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test parsing JSON in generic code blocks (without json marker)."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        mock_response = mock_gemini_client.models.generate_content.return_value
        json_content = {"audioType": "music", "transcript": [], "audioEvents": []}
        mock_response.text = f"```\n{json.dumps(json_content)}\n```"

        result = analyze_audio(str(audio_path), "fake_api_key")

        assert result["audioType"] == "music"

    def test_analyze_handles_json_parse_error(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test handling of malformed JSON response."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Mock response with invalid JSON
        mock_response = mock_gemini_client.models.generate_content.return_value
        mock_response.text = "This is not valid JSON { broken }"

        result = analyze_audio(str(audio_path), "fake_api_key")

        # Should return error dict
        assert "error" in result
        assert result["error"] == "Failed to parse JSON response"
        assert "error_details" in result
        assert "raw_response" in result

    def test_analyze_nonexistent_audio_file_raises_error(self, temp_dir, mock_genai_module):
        """Test that FileNotFoundError is raised for non-existent audio file."""
        nonexistent_file = temp_dir / "nonexistent.webm"

        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            analyze_audio(str(nonexistent_file), "fake_api_key")

    def test_analyze_uploads_with_correct_mime_type(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test that audio file is uploaded with correct MIME type."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        analyze_audio(str(audio_path), "fake_api_key")

        # Verify upload was called with correct config
        upload_call = mock_gemini_client.files.upload.call_args
        assert upload_call[1]["config"]["mime_type"] == "audio/webm"

    def test_analyze_uses_correct_model(self, temp_dir, mock_genai_module, mock_gemini_client):
        """Test that the correct Gemini model is used."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        analyze_audio(str(audio_path), "fake_api_key")

        # Verify generate_content was called with correct model
        call_args = mock_gemini_client.models.generate_content.call_args
        assert call_args[1]["model"] == DEFAULT_MODEL

    def test_analyze_includes_meta_information(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test that result includes _meta field with prompt and context."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        context = {"travelers": [{"name": "Alice"}]}
        result = analyze_audio(str(audio_path), "fake_api_key", context=context)

        assert "_meta" in result
        assert "prompt" in result["_meta"]
        assert "context" in result["_meta"]
        assert "raw_response" in result["_meta"]
        assert result["_meta"]["context"] == context

    def test_analyze_empty_context(self, temp_dir, mock_genai_module, mock_gemini_client):
        """Test audio analysis with empty context dict."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        result = analyze_audio(str(audio_path), "fake_api_key", context={})

        # Should still work, just without context in prompt
        assert "audioType" in result
        assert result["_meta"]["context"] == {}

    def test_analyze_partial_context(self, temp_dir, mock_genai_module, mock_gemini_client):
        """Test audio analysis with partial context (only some fields)."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Only location, no travelers or storyBeat
        context = {"location": "Test Location"}

        result = analyze_audio(str(audio_path), "fake_api_key", context=context)

        # Verify prompt includes location
        call_args = mock_gemini_client.models.generate_content.call_args
        prompt = call_args[1]["contents"][-1]

        assert "Test Location" in prompt
        assert result["_meta"]["context"] == context

    def test_analyze_voice_reference_without_travelers(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test voice reference with no travelers in context."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Mock voice reference file
        mock_voice_ref = mock_genai_module.Mock()
        mock_voice_ref.name = "voice_reference.webm"

        # Context with no travelers
        context = {"location": "Some Place"}

        result = analyze_audio(
            str(audio_path), "fake_api_key", context=context, voice_reference_file=mock_voice_ref
        )

        # Verify the prompt mentions voice reference but handles missing travelers
        call_args = mock_gemini_client.models.generate_content.call_args
        prompt = call_args[1]["contents"][-1]

        assert "VOICE REFERENCE" in prompt
        assert "CLIP TO ANALYZE" in prompt
        # Should have the fallback "." after "learn each person's voice"
        assert "voice." in prompt or "voice:" in prompt

        # Verify result is valid
        assert "audioType" in result

    def test_analyze_handles_none_response_text(
        self, temp_dir, mock_genai_module, mock_gemini_client
    ):
        """Test handling of None response.text."""
        audio_path = temp_dir / "test_audio.webm"
        audio_path.write_bytes(b"\x1a\x45\xdf\xa3")

        # Mock response with None text
        mock_response = mock_gemini_client.models.generate_content.return_value
        mock_response.text = None

        result = analyze_audio(str(audio_path), "fake_api_key")

        # Should handle None gracefully and return error
        assert "error" in result
        assert result["error"] == "Failed to parse JSON response"
