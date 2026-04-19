"""Tests for inject_google_photos_metadata.py."""
import json
import os
import shutil

import pytest
from PIL import Image

# Import the module under test
sys_path_added = False
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inject_google_photos_metadata import (
    MetadataInjector,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    EXIF_IMAGE_EXTENSIONS,
    setup_logging,
)


# ---------------------------------------------------------------------------
# Metadata parsing tests
# ---------------------------------------------------------------------------

class TestFindMatchingMediaFile:
    """Tests for MetadataInjector.find_matching_media_file."""

    def _make_injector(self, input_dir, output_dir):
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_standard_match(self, tmp_dirs, make_jpeg, make_metadata_json):
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        json_path = make_metadata_json(input_dir, "photo.jpg")

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo.jpg"

    def test_duplicate_number_match(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Test matching photo(20).jpg with photo.jpg.supplemental-metadata(20).json."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo(20).jpg")
        # Create the numbered metadata file manually
        json_name = "photo.jpg.supplemental-metadata(20).json"
        json_path = os.path.join(str(input_dir), json_name)
        data = {"photoTakenTime": {"timestamp": "1609459200"}}
        with open(json_path, "w") as f:
            json.dump(data, f)

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo(20).jpg"

    def test_typo_variant_match(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Test the .supplemental-metada.json typo variant."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        json_path = make_metadata_json(input_dir, "photo.jpg", variant="typo")

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo.jpg"

    def test_no_match_returns_none(self, tmp_dirs, make_metadata_json):
        input_dir, output_dir = tmp_dirs
        json_path = make_metadata_json(input_dir, "missing_photo.jpg")

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is None


class TestGetPhotoTakenTime:
    """Tests for MetadataInjector.get_photo_taken_time."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_valid_timestamp(self, tmp_dirs):
        injector = self._make_injector(tmp_dirs)
        metadata = {"photoTakenTime": {"timestamp": "1609459200"}}
        result = injector.get_photo_taken_time(metadata)
        assert result == "2021:01:01 00:00:00"

    def test_zero_timestamp_returns_none(self, tmp_dirs):
        injector = self._make_injector(tmp_dirs)
        metadata = {"photoTakenTime": {"timestamp": "0"}}
        result = injector.get_photo_taken_time(metadata)
        assert result is None

    def test_missing_photo_taken_time_returns_none(self, tmp_dirs):
        injector = self._make_injector(tmp_dirs)
        metadata = {"description": "no timestamp here"}
        result = injector.get_photo_taken_time(metadata)
        assert result is None

    def test_missing_timestamp_field_returns_none(self, tmp_dirs):
        injector = self._make_injector(tmp_dirs)
        metadata = {"photoTakenTime": {}}
        result = injector.get_photo_taken_time(metadata)
        assert result is None


class TestReadMetadataJson:
    """Tests for MetadataInjector.read_metadata_json."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_valid_json(self, tmp_dirs, make_metadata_json):
        input_dir, output_dir = tmp_dirs
        json_path = make_metadata_json(input_dir, "test.jpg")
        injector = self._make_injector(tmp_dirs)
        result = injector.read_metadata_json(json_path)
        assert result is not None
        assert "photoTakenTime" in result

    def test_corrupt_json(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        bad_json = os.path.join(str(input_dir), "bad.json")
        with open(bad_json, "w") as f:
            f.write("{invalid json content")
        injector = self._make_injector(tmp_dirs)
        result = injector.read_metadata_json(bad_json)
        assert result is None
        assert len(injector.errors) == 1

    def test_nonexistent_file(self, tmp_dirs):
        injector = self._make_injector(tmp_dirs)
        result = injector.read_metadata_json("/nonexistent/path.json")
        assert result is None


# ---------------------------------------------------------------------------
# Format handler tests
# ---------------------------------------------------------------------------

class TestJpegExifUpdate:
    """Tests for JPEG EXIF metadata writing."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_jpeg_exif_update(self, tmp_dirs, make_jpeg):
        input_dir, output_dir = tmp_dirs
        photo_path = make_jpeg(output_dir, "test.jpg")
        injector = self._make_injector(tmp_dirs)
        result = injector.update_photo_exif(photo_path, "2021:01:01 00:00:00")
        assert result is True

    def test_jpeg_exif_verify_tags(self, tmp_dirs, make_jpeg):
        """Verify EXIF tags are actually written."""
        input_dir, output_dir = tmp_dirs
        photo_path = make_jpeg(output_dir, "test.jpg")
        injector = self._make_injector(tmp_dirs)
        injector.update_photo_exif(photo_path, "2021:06:15 14:30:00")

        # Read back and verify
        try:
            import piexif
            exif_dict = piexif.load(photo_path)
            dto = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal, b"").decode()
            assert dto == "2021:06:15 14:30:00"
        except ImportError:
            # Without piexif, verify via Pillow
            img = Image.open(photo_path)
            exif = img.getexif()
            assert exif.get(36867) == "2021:06:15 14:30:00"


class TestPngMetadataUpdate:
    """Tests for PNG text chunk metadata writing."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_png_metadata_update(self, tmp_dirs, make_png):
        input_dir, output_dir = tmp_dirs
        photo_path = make_png(output_dir, "test.png")
        injector = self._make_injector(tmp_dirs)
        result = injector.update_photo_exif(photo_path, "2021:01:01 00:00:00")
        assert result is True

    def test_png_metadata_verify_chunks(self, tmp_dirs, make_png):
        """Verify PNG text chunks are actually written."""
        input_dir, output_dir = tmp_dirs
        photo_path = make_png(output_dir, "test.png")
        injector = self._make_injector(tmp_dirs)
        injector.update_photo_exif(photo_path, "2021:06:15 14:30:00")

        img = Image.open(photo_path)
        assert img.info.get("DateTimeOriginal") == "2021:06:15 14:30:00"
        assert img.info.get("CreationTime") == "2021:06:15 14:30:00"
        assert img.info.get("GooglePhotosTaken") == "2021:06:15 14:30:00"


class TestGifMetadataUpdate:
    """Tests for GIF comment metadata writing."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_gif_metadata_update(self, tmp_dirs, make_gif):
        input_dir, output_dir = tmp_dirs
        photo_path = make_gif(output_dir, "test.gif")
        injector = self._make_injector(tmp_dirs)
        result = injector.update_photo_exif(photo_path, "2021:01:01 00:00:00")
        assert result is True


class TestWebpExifUpdate:
    """Tests for WebP EXIF metadata writing."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_webp_exif_update(self, tmp_dirs, make_webp):
        input_dir, output_dir = tmp_dirs
        photo_path = make_webp(output_dir, "test.webp")
        injector = self._make_injector(tmp_dirs)
        result = injector.update_photo_exif(photo_path, "2021:01:01 00:00:00")
        assert result is True


class TestExtensionConstants:
    """Tests for extension set consistency."""

    def test_all_image_extensions_covered(self):
        """Every extension in IMAGE_EXTENSIONS should have a handler or be copy-only."""
        from inject_google_photos_metadata import (
            EXIF_IMAGE_EXTENSIONS, PNG_EXTENSIONS, HEIC_EXTENSIONS,
            GIF_EXTENSIONS, COPY_ONLY_IMAGE_EXTENSIONS, IMAGE_EXTENSIONS,
        )
        covered = EXIF_IMAGE_EXTENSIONS | PNG_EXTENSIONS | HEIC_EXTENSIONS | GIF_EXTENSIONS | COPY_ONLY_IMAGE_EXTENSIONS
        assert covered == IMAGE_EXTENSIONS

    def test_no_overlap_image_video(self):
        assert IMAGE_EXTENSIONS.isdisjoint(VIDEO_EXTENSIONS)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """End-to-end integration tests."""

    def _make_injector(self, input_dir, output_dir, **kwargs):
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file, **kwargs)

    def test_full_pipeline_jpeg(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Process a JPEG file end-to-end."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json(input_dir, "photo.jpg", timestamp=1609459200)

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        assert injector.stats['processed'] == 1
        assert injector.stats['photos_exif'] == 1
        assert injector.stats['errors'] == 0
        assert os.path.exists(os.path.join(str(output_dir), "photo.jpg"))

    def test_full_pipeline_png(self, tmp_dirs, make_png, make_metadata_json):
        """Process a PNG file end-to-end."""
        input_dir, output_dir = tmp_dirs
        make_png(input_dir, "photo.png")
        make_metadata_json(input_dir, "photo.png", timestamp=1609459200)

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        assert injector.stats['processed'] == 1
        assert injector.stats['photos_png'] == 1

    def test_unknown_timestamp_folder(self, tmp_dirs, make_jpeg, make_metadata_json_no_timestamp):
        """Files with no timestamp go to Unknown Timestamp folder."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json_no_timestamp(input_dir, "photo.jpg")

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        assert injector.stats['unknown_timestamp'] == 1
        unknown_path = os.path.join(str(output_dir), "Unknown Timestamp", "photo.jpg")
        assert os.path.exists(unknown_path)

    def test_no_metadata_files_returns_false(self, tmp_dirs):
        """Return False when no metadata files are found."""
        input_dir, output_dir = tmp_dirs
        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()
        assert success is False

    def test_nested_directory_structure(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Preserve nested directory structure in output."""
        input_dir, output_dir = tmp_dirs
        subdir = input_dir / "Photos from 2014"
        subdir.mkdir()
        make_jpeg(subdir, "vacation.jpg")
        make_metadata_json(subdir, "vacation.jpg", timestamp=1609459200)

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        expected = os.path.join(str(output_dir), "Photos from 2014", "vacation.jpg")
        assert os.path.exists(expected)

    def test_dry_run_no_files_created(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Dry run should not create any output files."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json(input_dir, "photo.jpg", timestamp=1609459200)

        injector = self._make_injector(input_dir, output_dir, dry_run=True)
        success = injector.run()

        assert success is True
        assert injector.stats['processed'] == 1
        # No actual file should be created in output (only the log file)
        output_files = [f for f in os.listdir(str(output_dir)) if f != "test.log"]
        assert len(output_files) == 0

    def test_skip_existing(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Skip-existing should not overwrite files already in output."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json(input_dir, "photo.jpg", timestamp=1609459200)

        # First run
        injector1 = self._make_injector(input_dir, output_dir)
        injector1.run()
        assert injector1.stats['processed'] == 1

        # Second run with skip-existing
        injector2 = self._make_injector(input_dir, output_dir, skip_existing=True)
        injector2.run()
        assert injector2.stats['skipped_existing'] == 1
        assert injector2.stats['processed'] == 0

    def test_multiple_files_progress(self, tmp_dirs, make_jpeg, make_metadata_json):
        """Multiple files should all be processed with correct stats."""
        input_dir, output_dir = tmp_dirs
        for i in range(5):
            name = f"photo{i}.jpg"
            make_jpeg(input_dir, name)
            make_metadata_json(input_dir, name, timestamp=1609459200 + i * 86400)

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        assert injector.stats['processed'] == 5
        assert injector.stats['photos_exif'] == 5
        assert injector.stats['errors'] == 0
