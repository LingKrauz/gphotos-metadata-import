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

    def test_truncated_meta_variant_match(self, tmp_dirs, make_jpeg):
        """Test .supplemental-meta.json (shortest named truncation) matches the media file."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        json_path = os.path.join(str(input_dir), "photo.jpg.supplemental-meta.json")
        import json as _json
        with open(json_path, "w") as f:
            _json.dump({"photoTakenTime": {"timestamp": "1609459200"}}, f)

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo.jpg"

    def test_extremely_truncated_supple_variant_match(self, tmp_dirs, make_jpeg):
        """Test .supple.json (maximum truncation at 51-char limit) matches the media file."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        json_path = os.path.join(str(input_dir), "photo.jpg.supple.json")
        import json as _json
        with open(json_path, "w") as f:
            _json.dump({"photoTakenTime": {"timestamp": "1609459200"}}, f)

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo.jpg"

    def test_duplicate_number_with_truncated_variant(self, tmp_dirs, make_jpeg):
        """Test photo(1).jpg matched by photo.jpg.supplemental-meta(1).json."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo(1).jpg")
        json_path = os.path.join(str(input_dir), "photo.jpg.supplemental-meta(1).json")
        import json as _json
        with open(json_path, "w") as f:
            _json.dump({"photoTakenTime": {"timestamp": "1609459200"}}, f)

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo(1).jpg"

    def test_number_in_media_filename_not_treated_as_duplicate(self, tmp_dirs, make_jpeg):
        """Test that (1) in the media filename itself is not treated as a duplicate number."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo(1).jpg")
        # JSON suffix has no (N) — the (1) is part of the media filename
        json_path = os.path.join(str(input_dir), "photo(1).jpg.supplemental-me.json")
        import json as _json
        with open(json_path, "w") as f:
            _json.dump({"photoTakenTime": {"timestamp": "1609459200"}}, f)

        injector = self._make_injector(input_dir, output_dir)
        result = injector.find_matching_media_file(json_path, str(input_dir))
        assert result is not None
        assert os.path.basename(result) == "photo(1).jpg"


class TestFindAllMetadataFiles:
    """Tests for MetadataInjector.find_all_metadata_files."""

    def _make_injector(self, input_dir, output_dir):
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def _write_json(self, path):
        import json as _json
        with open(path, "w") as f:
            _json.dump({"photoTakenTime": {"timestamp": "1609459200"}}, f)

    def test_finds_standard_json(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        p = os.path.join(str(input_dir), "photo.jpg.supplemental-metadata.json")
        self._write_json(p)
        injector = self._make_injector(input_dir, output_dir)
        found = injector.find_all_metadata_files()
        assert any(os.path.basename(f) == "photo.jpg.supplemental-metadata.json" for f in found)

    def test_finds_numbered_duplicate_json(self, tmp_dirs):
        """supplemental-metadata(1).json must be discovered by the scanner."""
        input_dir, output_dir = tmp_dirs
        p = os.path.join(str(input_dir), "photo.jpg.supplemental-metadata(1).json")
        self._write_json(p)
        injector = self._make_injector(input_dir, output_dir)
        found = injector.find_all_metadata_files()
        assert any("supplemental-metadata(1).json" in f for f in found)

    def test_finds_truncated_meta_variants(self, tmp_dirs):
        """All supplemental-meta* truncation variants (down to .supple) must be discovered."""
        input_dir, output_dir = tmp_dirs
        variants = [
            "a.jpg.supplemental-metadat.json",
            "b.jpg.supplemental-metada.json",
            "c.jpg.supplemental-metad.json",
            "d.jpg.supplemental-meta.json",
            "e.jpg.supplemental-met.json",
            "f.jpg.supplemental-me.json",
            "g.jpg.supplement.json",
            "h.jpg.supple.json",
        ]
        for name in variants:
            self._write_json(os.path.join(str(input_dir), name))
        injector = self._make_injector(input_dir, output_dir)
        found = {os.path.basename(f) for f in injector.find_all_metadata_files()}
        for name in variants:
            assert name in found, f"Expected {name} to be found"

    def test_finds_numbered_truncated_variant(self, tmp_dirs):
        """supplemental-meta(2).json must be discovered."""
        input_dir, output_dir = tmp_dirs
        p = os.path.join(str(input_dir), "photo.jpg.supplemental-meta(2).json")
        self._write_json(p)
        injector = self._make_injector(input_dir, output_dir)
        found = injector.find_all_metadata_files()
        assert any("supplemental-meta(2).json" in f for f in found)


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

    def test_no_files_completes_successfully(self, tmp_dirs):
        """Empty input directory completes successfully with nothing processed."""
        input_dir, output_dir = tmp_dirs
        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()
        assert success is True
        assert injector.stats['processed'] == 0
        assert injector.stats['copied_no_json'] == 0

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

    def test_media_without_json_gets_copied(self, tmp_dirs, make_jpeg):
        """Media files with no supplemental JSON are copied to output."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "orphan.jpg")

        injector = self._make_injector(input_dir, output_dir)
        success = injector.run()

        assert success is True
        assert injector.stats['copied_no_json'] == 1
        assert os.path.exists(os.path.join(str(output_dir), "orphan.jpg"))

    def test_media_without_json_preserves_structure(self, tmp_dirs, make_jpeg):
        """Directory structure is preserved when copying files without JSON."""
        input_dir, output_dir = tmp_dirs
        subdir = input_dir / "Photos from 2020"
        subdir.mkdir()
        make_jpeg(subdir, "vacation.jpg")

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        expected = os.path.join(str(output_dir), "Photos from 2020", "vacation.jpg")
        assert os.path.exists(expected)

    def test_no_metadata_report_written(self, tmp_dirs, make_jpeg):
        """Report lists files that have no JSON and no embedded timestamp."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "orphan.jpg")

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        report_path = os.path.join(str(output_dir), "no_metadata_files.txt")
        assert os.path.exists(report_path)
        content = open(report_path, encoding="utf-8").read()
        assert "orphan.jpg" in content

    def test_already_dated_file_excluded_from_report(
        self, tmp_dirs, make_jpeg_with_exif
    ):
        """Files with an embedded EXIF timestamp are copied but not listed in the report."""
        input_dir, output_dir = tmp_dirs
        make_jpeg_with_exif(input_dir, "already_dated.jpg")

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        assert injector.stats['copied_no_json'] == 1
        assert os.path.exists(os.path.join(str(output_dir), "already_dated.jpg"))
        report_path = os.path.join(str(output_dir), "no_metadata_files.txt")
        assert not os.path.exists(report_path)

    def test_mixed_dated_and_undated_without_json(
        self, tmp_dirs, make_jpeg, make_jpeg_with_exif
    ):
        """Only truly undated orphan files appear in the report."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "undated.jpg")
        make_jpeg_with_exif(input_dir, "dated.jpg")

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        assert injector.stats['copied_no_json'] == 2
        report_path = os.path.join(str(output_dir), "no_metadata_files.txt")
        assert os.path.exists(report_path)
        content = open(report_path, encoding="utf-8").read()
        assert os.sep + "undated.jpg" in content
        assert os.sep + "dated.jpg" not in content

    def test_no_metadata_report_not_written_when_all_have_json(
        self, tmp_dirs, make_jpeg, make_metadata_json
    ):
        """Report is not written when all media files have a matching JSON."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json(input_dir, "photo.jpg", timestamp=1609459200)

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        report_path = os.path.join(str(output_dir), "no_metadata_files.txt")
        assert not os.path.exists(report_path)

    def test_mixed_json_and_no_json(self, tmp_dirs, make_jpeg, make_png, make_metadata_json):
        """Files with JSON get metadata; files without JSON are still copied."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "dated.jpg")
        make_metadata_json(input_dir, "dated.jpg", timestamp=1609459200)
        make_png(input_dir, "orphan.png")

        injector = self._make_injector(input_dir, output_dir)
        injector.run()

        assert injector.stats['processed'] == 1
        assert injector.stats['photos_exif'] == 1
        assert injector.stats['copied_no_json'] == 1
        assert os.path.exists(os.path.join(str(output_dir), "dated.jpg"))
        assert os.path.exists(os.path.join(str(output_dir), "orphan.png"))
        report_path = os.path.join(str(output_dir), "no_metadata_files.txt")
        assert os.path.exists(report_path)


# ---------------------------------------------------------------------------
# GPS tests
# ---------------------------------------------------------------------------

class TestGetGpsData:
    """Tests for MetadataInjector.get_gps_data."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_prefers_geo_data_exif(self, tmp_dirs):
        """get_gps_data returns geoDataExif values when non-zero."""
        injector = self._make_injector(tmp_dirs)
        metadata = {
            "geoData": {"latitude": 1.0, "longitude": 2.0, "altitude": 3.0},
            "geoDataExif": {"latitude": 39.5023, "longitude": -104.7447, "altitude": 1609.0},
        }
        result = injector.get_gps_data(metadata)
        assert result is not None
        assert result['lat'] == pytest.approx(39.5023)
        assert result['lon'] == pytest.approx(-104.7447)
        assert result['alt'] == pytest.approx(1609.0)

    def test_falls_back_to_geo_data(self, tmp_dirs):
        """get_gps_data falls back to geoData when geoDataExif is all zeros."""
        injector = self._make_injector(tmp_dirs)
        metadata = {
            "geoData": {"latitude": 39.5023, "longitude": -104.7447, "altitude": 1609.0},
            "geoDataExif": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
        }
        result = injector.get_gps_data(metadata)
        assert result is not None
        assert result['lat'] == pytest.approx(39.5023)
        assert result['lon'] == pytest.approx(-104.7447)

    def test_returns_none_when_both_zero(self, tmp_dirs):
        """get_gps_data returns None when both fields have zero coordinates."""
        injector = self._make_injector(tmp_dirs)
        metadata = {
            "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
            "geoDataExif": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
        }
        result = injector.get_gps_data(metadata)
        assert result is None

    def test_returns_none_when_fields_missing(self, tmp_dirs):
        """get_gps_data returns None when geoData/geoDataExif fields are absent."""
        injector = self._make_injector(tmp_dirs)
        metadata = {"photoTakenTime": {"timestamp": "1609459200"}}
        result = injector.get_gps_data(metadata)
        assert result is None


class TestJpegGpsInjection:
    """Tests for GPS coordinate injection into JPEG files."""

    def _make_injector(self, tmp_dirs):
        input_dir, output_dir = tmp_dirs
        log_file = os.path.join(str(output_dir), "test.log")
        setup_logging(log_file)
        return MetadataInjector(str(input_dir), str(output_dir), log_file)

    def test_jpeg_gps_written_and_readable(self, tmp_dirs, make_jpeg):
        """GPS IFD tags are written to JPEG and can be read back via piexif."""
        pytest.importorskip("piexif")
        import piexif

        input_dir, output_dir = tmp_dirs
        photo_path = make_jpeg(output_dir, "gps_test.jpg")
        injector = self._make_injector(tmp_dirs)

        gps_data = {"lat": 39.5023, "lon": -104.7447, "alt": 1609.0}
        result = injector.update_photo_exif(photo_path, "2021:01:01 00:00:00", gps_data)
        assert result is True

        exif_dict = piexif.load(photo_path)
        gps = exif_dict.get("GPS", {})
        assert piexif.GPSIFD.GPSLatitudeRef in gps
        assert piexif.GPSIFD.GPSLongitudeRef in gps
        assert gps[piexif.GPSIFD.GPSLatitudeRef] == b'N'
        assert gps[piexif.GPSIFD.GPSLongitudeRef] == b'W'

        # Verify latitude reconstructed from DMS is approximately correct
        lat_dms = gps[piexif.GPSIFD.GPSLatitude]
        lat = lat_dms[0][0]/lat_dms[0][1] + lat_dms[1][0]/lat_dms[1][1]/60 + lat_dms[2][0]/lat_dms[2][1]/3600
        assert lat == pytest.approx(39.5023, abs=0.0001)

    def test_jpeg_southern_hemisphere_ref(self, tmp_dirs, make_jpeg):
        """Negative latitude correctly written as 'S' ref."""
        pytest.importorskip("piexif")
        import piexif

        input_dir, output_dir = tmp_dirs
        photo_path = make_jpeg(output_dir, "south.jpg")
        injector = self._make_injector(tmp_dirs)

        gps_data = {"lat": -33.8688, "lon": 151.2093, "alt": 10.0}
        injector.update_photo_exif(photo_path, "2021:01:01 00:00:00", gps_data)

        exif_dict = piexif.load(photo_path)
        gps = exif_dict.get("GPS", {})
        assert gps[piexif.GPSIFD.GPSLatitudeRef] == b'S'
        assert gps[piexif.GPSIFD.GPSLongitudeRef] == b'E'

    def test_jpeg_gps_stat_incremented(self, tmp_dirs, make_jpeg, make_metadata_json_with_gps):
        """End-to-end: gps_injected stat is incremented when GPS is written."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json_with_gps(input_dir, "photo.jpg")

        injector = self._make_injector(tmp_dirs)
        injector.run()

        assert injector.stats['gps_injected'] == 1

    def test_zero_gps_not_injected(self, tmp_dirs, make_jpeg, make_metadata_json):
        """GPS is not injected and stat stays 0 when JSON has no GPS coordinates."""
        input_dir, output_dir = tmp_dirs
        make_jpeg(input_dir, "photo.jpg")
        make_metadata_json(input_dir, "photo.jpg")

        injector = self._make_injector(tmp_dirs)
        injector.run()

        assert injector.stats['gps_injected'] == 0
