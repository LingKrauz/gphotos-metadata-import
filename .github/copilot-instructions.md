# Copilot Instructions for Google Photos Metadata Injector

## Overview

This is a Python utility that injects Google Photos supplemental metadata (specifically photo taken timestamps) into actual media files. It's a non-destructive batch processor that reads supplemental metadata JSON files exported from Google Photos and updates EXIF/metadata tags in corresponding photos and videos.

## Build & Run

### Setup
```bash
pip install -r requirements.txt
```

### Run
```bash
python inject_google_photos_metadata.py
```

The script automatically:
1. Scans the input directory (`INPUT_ROOT`) recursively for `.supplemental-metadata.json` files
2. Matches each JSON file to its corresponding media file
3. Extracts the `photoTakenTime` timestamp from JSON
4. Updates the media file's metadata based on file type
5. Outputs processed files to `OUTPUT_ROOT` with folder structure preserved
6. Generates a detailed log at `{OUTPUT_ROOT}/metadata_injection.log`

## Architecture

### Key Components

**MetadataInjector class** (`inject_google_photos_metadata.py:118+`)
- Core orchestrator for the entire pipeline
- Tracks statistics (processed count, errors, format-specific success counts)
- Methods correspond to the processing steps

**Metadata Matching** (`find_matching_media_file`)
- Handles two filename patterns:
  - Standard: `photo.jpg` + `photo.jpg.supplemental-metadata.json`
  - Duplicates: `photo(20).jpg` + `photo.jpg.supplemental-metadata(20).json`
- Also tolerates JSON typo variant: `.supplemental-metada.json`

**Format-Specific Handlers**
- JPEG/TIFF: Standard EXIF tags via `piexif` library (primary) or Pillow fallback
- PNG: Text chunks (DateTimeOriginal, CreationTime, GooglePhotosTaken)
- HEIC: EXIF via `pillow-heif` (if available; auto-detects)
- GIF: Comment metadata
- Videos: Container metadata via `ffmpeg` (if available; auto-detects)

**External Tool Detection**
- FFmpeg paths hardcoded in common locations (lines 44-49) for Windows compatibility
- Auto-detects availability at startup; gracefully degrades if missing
- HEIF/HEIC support similarly optional via `pillow-heif`

### Input/Output

- **Input**: `INPUT_ROOT` directory containing photo subdirectories (year-based) with both media files and `.supplemental-metadata.json` files
- **Output**: Identical folder structure in `OUTPUT_ROOT` with updated media files
- **No in-place modification**: Original files are never touched

## Key Conventions & Patterns

### Configuration
Paths hardcoded in script (lines 81-83):
```python
INPUT_ROOT = r"c:\Users\Mitchell\Downloads\Google Photos"
OUTPUT_ROOT = r"c:\Users\Mitchell\Downloads\Google Photos Updated"
```
These should be customized per environment—there is no config file.

### Logging
- Dual output: file + console (see `setup_logging`)
- File logging at DEBUG level; console at INFO
- Each operation logged with timestamp and severity
- **All errors now logged at WARNING level** in the log file with full details
- Statistics summary including all errors printed at end

### Statistics Tracking
The `stats` dict in `MetadataInjector.__init__` breaks down successes by format and tracks errors separately. Useful for understanding processing results.

### Timestamp Conversion
- Source: Google Photos JSON format (Unix timestamp in `photoTakenTime.timestamp`)
- Target: EXIF format `YYYY:MM:DD HH:MM:SS` (see `get_photo_taken_time`)
- Uses UTC to avoid timezone ambiguity

### Graceful Degradation
- If `piexif` missing: falls back to Pillow's basic EXIF support
- If `ffmpeg` missing: videos copied without metadata
- If `pillow-heif` missing: HEIC files copied without metadata
- No hard failures; all handled via try/except with logging

### Error Handling
- Individual file errors don't stop processing
- **Metadata update failures are now logged at WARNING level** with file type context
- All errors collected in `self.errors` list and printed in full in the summary
- Failed metadata updates include the type of file (JPEG/TIFF, PNG, HEIC, GIF, video)

## When to Modify

**Update format handlers** when:
- Adding support for new media formats
- Changing EXIF tag IDs or PNG text chunk names
- Improving format-specific encoding

**Update error logging** when:
- Error messages become confusing or vague
- New error conditions are discovered
- Log level changes are needed (currently WARNING for metadata failures)

**Update path detection** when:
- Adding support for new ffmpeg locations
- Changing config file structure

**Update timestamp conversion** when:
- Source JSON format changes
- EXIF target format changes

