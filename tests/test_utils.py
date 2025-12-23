# Tests for utils.py

import json
import zipfile
from pathlib import Path

import pytest

from utils import extract_zip, load_metadata, save_metadata


class TestExtractZip:
    """Tests for extract_zip function."""

    def test_extract_valid_zip(self, sample_zip_file, temp_dir):
        """Test successful extraction of a valid ZIP file."""
        output_dir = temp_dir / "output"
        result = extract_zip(str(sample_zip_file), str(output_dir))

        # Check that extraction succeeded
        assert result is not None
        assert Path(result).exists()
        assert Path(result).is_dir()

        # Check that metadata.json exists in extracted folder
        metadata_path = Path(result) / "metadata.json"
        assert metadata_path.exists()

    def test_extract_creates_output_directory(self, sample_zip_file, temp_dir):
        """Test that extract_zip creates output directory if it doesn't exist."""
        output_dir = temp_dir / "nonexistent" / "nested" / "output"
        assert not output_dir.exists()

        result = extract_zip(str(sample_zip_file), str(output_dir))

        assert output_dir.exists()
        assert Path(result).exists()

    def test_extract_with_single_directory(self, temp_dir):
        """Test extraction when ZIP contains a single root directory."""
        # Create a ZIP with a single directory structure
        zip_path = temp_dir / "single_dir.zip"
        extract_source = temp_dir / "source"
        extract_source.mkdir()
        (extract_source / "test.txt").write_text("test")

        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(extract_source / "test.txt", "source/test.txt")

        output_dir = temp_dir / "output"
        result = extract_zip(str(zip_path), str(output_dir))

        # Should return the single directory path
        assert "source" in result
        assert (Path(result) / "test.txt").exists()

    def test_extract_with_multiple_root_items(self, temp_dir):
        """Test extraction when ZIP contains multiple items at root level."""
        zip_path = temp_dir / "multi_root.zip"

        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("file1.txt", "content1")
            zipf.writestr("file2.txt", "content2")

        output_dir = temp_dir / "output"
        result = extract_zip(str(zip_path), str(output_dir))

        # Should return the output directory itself
        assert result == str(output_dir)
        assert (Path(result) / "file1.txt").exists()
        assert (Path(result) / "file2.txt").exists()

    def test_extract_nonexistent_zip_raises_error(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent ZIP file."""
        nonexistent_zip = temp_dir / "nonexistent.zip"
        output_dir = temp_dir / "output"

        with pytest.raises(FileNotFoundError, match="ZIP file not found"):
            extract_zip(str(nonexistent_zip), str(output_dir))


class TestLoadMetadata:
    """Tests for load_metadata function."""

    def test_load_valid_metadata(self, sample_metadata_file, sample_metadata):
        """Test successful loading of valid metadata.json."""
        result = load_metadata(str(sample_metadata_file))

        assert result == sample_metadata
        assert "trip" in result
        assert "clips" in result
        assert result["trip"]["name"] == "Test Trip"

    def test_load_metadata_with_utf8(self, temp_dir):
        """Test that UTF-8 encoded content is handled correctly."""
        metadata = {
            "trip": {"name": "東京旅行 🗼", "talent": [{"name": "Élise"}, {"name": "José"}]}
        }

        metadata_path = temp_dir / "metadata_utf8.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False)

        result = load_metadata(str(metadata_path))

        assert result["trip"]["name"] == "東京旅行 🗼"
        assert result["trip"]["talent"][0]["name"] == "Élise"
        assert result["trip"]["talent"][1]["name"] == "José"

    def test_load_nonexistent_file_raises_error(self, temp_dir):
        """Test that FileNotFoundError is raised for non-existent file."""
        nonexistent_file = temp_dir / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Metadata file not found"):
            load_metadata(str(nonexistent_file))

    def test_load_malformed_json_raises_error(self, temp_dir):
        """Test that JSONDecodeError is raised for malformed JSON."""
        malformed_file = temp_dir / "malformed.json"
        malformed_file.write_text("{ invalid json content }")

        with pytest.raises(json.JSONDecodeError):
            load_metadata(str(malformed_file))

    def test_load_empty_json_object(self, temp_dir):
        """Test loading an empty but valid JSON object."""
        empty_file = temp_dir / "empty.json"
        empty_file.write_text("{}")

        result = load_metadata(str(empty_file))
        assert result == {}


class TestSaveMetadata:
    """Tests for save_metadata function."""

    def test_save_valid_metadata(self, temp_dir, sample_metadata):
        """Test successful saving of metadata as JSON."""
        output_path = temp_dir / "output.json"
        save_metadata(sample_metadata, str(output_path))

        assert output_path.exists()

        # Load and verify content
        with open(output_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data == sample_metadata

    def test_save_creates_parent_directories(self, temp_dir, sample_metadata):
        """Test that parent directories are created if they don't exist."""
        output_path = temp_dir / "nested" / "path" / "output.json"
        assert not output_path.parent.exists()

        save_metadata(sample_metadata, str(output_path))

        assert output_path.parent.exists()
        assert output_path.exists()

    def test_save_preserves_utf8_characters(self, temp_dir):
        """Test that UTF-8 characters are preserved correctly."""
        metadata = {
            "trip": {"name": "パリ旅行 🗼", "talent": [{"name": "François"}, {"name": "Müller"}]}
        }

        output_path = temp_dir / "utf8_output.json"
        save_metadata(metadata, str(output_path))

        # Load and verify UTF-8 characters are preserved
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            saved_data = json.loads(content)

        assert saved_data["trip"]["name"] == "パリ旅行 🗼"
        assert "François" in content  # Should not be escaped
        assert "Müller" in content

    def test_save_formats_with_indentation(self, temp_dir, sample_metadata):
        """Test that JSON is formatted with proper indentation."""
        output_path = temp_dir / "formatted.json"
        save_metadata(sample_metadata, str(output_path))

        content = output_path.read_text()

        # Check for indentation (should have 2 spaces)
        assert "  " in content
        assert content.count("\n") > 5  # Should be multi-line

    def test_save_overwrites_existing_file(self, temp_dir):
        """Test that existing files are overwritten correctly."""
        output_path = temp_dir / "overwrite.json"

        # Write initial content
        initial_data = {"test": "initial"}
        save_metadata(initial_data, str(output_path))

        # Overwrite with new content
        new_data = {"test": "updated", "new_field": "value"}
        save_metadata(new_data, str(output_path))

        # Verify new content
        with open(output_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data == new_data
        assert saved_data["test"] == "updated"
        assert "new_field" in saved_data


class TestPathLikeSupport:
    """Tests verifying that utility functions accept Path objects."""

    def test_extract_zip_accepts_path_objects(self, sample_zip_file, temp_dir):
        """Test that extract_zip accepts Path objects, not just strings."""
        # Both arguments are Path objects
        output_dir = temp_dir / "path_output"
        result = extract_zip(sample_zip_file, output_dir)

        assert result is not None
        assert Path(result).exists()

    def test_load_metadata_accepts_path_object(self, sample_metadata_file):
        """Test that load_metadata accepts Path objects."""
        # sample_metadata_file is already a Path object
        result = load_metadata(sample_metadata_file)

        assert "trip" in result

    def test_save_metadata_accepts_path_object(self, temp_dir, sample_metadata):
        """Test that save_metadata accepts Path objects."""
        output_path = temp_dir / "path_output.json"
        save_metadata(sample_metadata, output_path)

        assert output_path.exists()

        # Verify content
        with open(output_path, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == sample_metadata
