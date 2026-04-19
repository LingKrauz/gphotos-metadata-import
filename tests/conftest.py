"""Shared fixtures for gphotos-metadata-import tests."""
import json
import os
import shutil
import tempfile

import pytest
from PIL import Image


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create input and output directories for testing."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    return input_dir, output_dir


@pytest.fixture
def make_jpeg(tmp_path):
    """Factory fixture to create a minimal JPEG file."""
    def _make(directory, name="photo.jpg"):
        path = os.path.join(str(directory), name)
        img = Image.new("RGB", (10, 10), color="red")
        img.save(path, "JPEG")
        return path
    return _make


@pytest.fixture
def make_png(tmp_path):
    """Factory fixture to create a minimal PNG file."""
    def _make(directory, name="photo.png"):
        path = os.path.join(str(directory), name)
        img = Image.new("RGB", (10, 10), color="blue")
        img.save(path, "PNG")
        return path
    return _make


@pytest.fixture
def make_gif(tmp_path):
    """Factory fixture to create a minimal GIF file."""
    def _make(directory, name="photo.gif"):
        path = os.path.join(str(directory), name)
        img = Image.new("P", (10, 10))
        img.save(path, "GIF")
        return path
    return _make


@pytest.fixture
def make_webp(tmp_path):
    """Factory fixture to create a minimal WebP file."""
    def _make(directory, name="photo.webp"):
        path = os.path.join(str(directory), name)
        img = Image.new("RGB", (10, 10), color="green")
        img.save(path, "WEBP")
        return path
    return _make


@pytest.fixture
def make_metadata_json():
    """Factory fixture to create a supplemental metadata JSON file."""
    def _make(directory, media_filename, timestamp=1609459200, variant="standard"):
        """
        variant: "standard" or "typo"
        timestamp: Unix timestamp (default: 2021-01-01 00:00:00 UTC)
        """
        suffix = ".supplemental-metadata.json" if variant == "standard" else ".supplemental-metada.json"
        json_path = os.path.join(str(directory), media_filename + suffix)
        data = {
            "photoTakenTime": {
                "timestamp": str(timestamp),
                "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
            }
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return json_path
    return _make


@pytest.fixture
def make_metadata_json_no_timestamp():
    """Factory fixture to create a metadata JSON with no timestamp."""
    def _make(directory, media_filename):
        json_path = os.path.join(str(directory), media_filename + ".supplemental-metadata.json")
        data = {"description": "test photo"}
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return json_path
    return _make
