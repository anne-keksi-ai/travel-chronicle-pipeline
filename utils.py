# Travel Chronicle - Utility Functions

import zipfile
import json
from pathlib import Path
from typing import Dict, Any


def extract_zip(zip_path: str, output_dir: str) -> str:
    """
    Extract a ZIP file to the specified directory.

    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory where the ZIP should be extracted

    Returns:
        str: Path to the extracted folder
    """
    zip_file = Path(zip_path)
    if not zip_file.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {zip_file.name} to {output_path}...")

    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(output_path)

    # Find the extracted folder (usually the ZIP creates a folder with the same name)
    extracted_items = list(output_path.iterdir())

    # If there's only one item and it's a directory, that's our extracted folder
    if len(extracted_items) == 1 and extracted_items[0].is_dir():
        extracted_folder = str(extracted_items[0])
    else:
        # Otherwise, the output_dir is the extracted folder
        extracted_folder = str(output_path)

    print(f"Extraction complete: {extracted_folder}")
    return extracted_folder


def load_metadata(metadata_path: str) -> Dict[str, Any]:
    """
    Load and parse metadata.json file.

    Args:
        metadata_path: Path to the metadata.json file

    Returns:
        dict: Parsed metadata
    """
    metadata_file = Path(metadata_path)
    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    print(f"Loading metadata from {metadata_file.name}...")

    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    return metadata


def save_metadata(metadata: Dict[str, Any], output_path: str) -> None:
    """
    Save metadata dictionary as formatted JSON.

    Args:
        metadata: Dictionary to save
        output_path: Path where the JSON file should be saved
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"Saving metadata to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Metadata saved: {output_file}")
