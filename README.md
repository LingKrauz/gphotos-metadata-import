# Google Photos Metadata Injector

A Python utility that injects metadata from Google Photos supplemental JSON files into exported media files. It processes photos and videos in batch, writing timestamps, GPS coordinates, and file dates back into the actual files — without modifying the originals.

## Features

- **Non-destructive**: All output goes to a separate directory; originals are never touched
- **Timestamps**: Sets EXIF `DateTimeOriginal`, container metadata, and OS file timestamps from `photoTakenTime`
- **GPS coordinates**: Writes GPS EXIF data from `geoDataExif` (preferred) or `geoData`
- **Broad format support**: JPEG, TIFF, WebP, PNG, HEIC, GIF, BMP, and common video containers
- **Duplicate filename handling**: Correctly matches `image(20).jpeg` to `image.jpeg.supplemental-metadata(20).json`
- **Truncated JSON filename handling**: Google Takeout truncates JSON filenames at 51 characters; the script matches them regardless
- **Unknown timestamps**: Files with no `photoTakenTime` are copied to an `Unknown Timestamp` subfolder
- **Media without JSON**: Media files with no corresponding JSON are still copied, preserving folder structure
- **Dry-run mode**: Preview what would be processed without writing any files
- **Resume support**: Skip already-processed files with `--skip-existing`
- **Graceful degradation**: Continues processing if optional tools (ffmpeg, pillow-heif) are unavailable

## Requirements

- Python 3.7+
- ffmpeg (optional — required for video metadata)
- pillow-heif (optional — required for HEIC/HEIF support)

## Installation

```bash
pip install -r requirements.txt
```

For video metadata support, install ffmpeg separately:

- **Windows**: Download from https://ffmpeg.org/download.html or `choco install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`

## Usage

Run against the current directory, outputting to `./_updated`:

```bash
python inject_google_photos_metadata.py
```

Specify input and output directories:

```bash
python inject_google_photos_metadata.py \
  --input-root "/path/to/Google Photos" \
  --output-root "/path/to/Google Photos Updated"
```

Input and output can also be set via environment variables:

```bash
export GPHOTOS_INPUT_ROOT="/path/to/Google Photos"
export GPHOTOS_OUTPUT_ROOT="/path/to/Google Photos Updated"
python inject_google_photos_metadata.py
```

### Options

| Flag | Description |
|---|---|
| `-i`, `--input-root` | Input directory (default: current directory or `GPHOTOS_INPUT_ROOT`) |
| `-o`, `--output-root` | Output directory (default: `<input>_updated` or `GPHOTOS_OUTPUT_ROOT`) |
| `--log-file` | Log file path (default: `<output>/metadata_injection.log`) |
| `--dry-run` | Preview what would be processed without writing any files |
| `--skip-existing` | Skip files that already exist in the output directory |
| `-v`, `--verbose` | Show DEBUG-level output on the console |

## How It Works

1. Scans the input directory recursively for supplemental metadata JSON files
2. Matches each JSON to its corresponding media file (handling duplicates and truncated filenames)
3. Extracts `photoTakenTime` and GPS data from the JSON
4. Copies the media file to the output directory and injects metadata based on file type
5. Sets the output file's OS modification and creation timestamps to the photo taken time
6. Media files with no matching JSON are copied as-is, preserving folder structure
7. Writes a detailed log to `<output>/metadata_injection.log`

## Format Support

### JPEG / TIFF / WebP
- EXIF `DateTimeOriginal` (tag 0x9003) and `DateTime` (tag 0x0132)
- GPS IFD with latitude, longitude, and altitude
- JPEG files are updated without re-encoding (uses `piexif.insert`)

### PNG
- Text chunks: `DateTimeOriginal`, `CreationTime`, `GooglePhotosTaken`

### HEIC / HEIF
- EXIF `DateTimeOriginal`, `DateTimeDigitized`, `DateTime`, and GPS (requires `pillow-heif`)
- Copied without metadata if `pillow-heif` is not installed

### GIF
- Comment field containing `DateTimeOriginal` and `GooglePhotosTaken`

### BMP / Google Pixel Motion Photos (.mp)
- Copied without metadata (no standard metadata container)

### Videos (MP4, MOV, AVI, MKV, etc.)
- Container `creation_time` updated via ffmpeg (no re-encoding)
- Copied without metadata if ffmpeg is not installed

## Output Structure

```
Input:
  Photos from 2014/
    image.jpeg
    image.jpeg.supplemental-metadata.json
    image(1).jpeg
    image.jpeg.supplemental-metadata(1).json

Output:
  Photos from 2014/
    image.jpeg               <- metadata updated
    image(1).jpeg            <- metadata updated
  Unknown Timestamp/         <- files with no photoTakenTime
  metadata_injection.log
```

## Logging

- **Console**: INFO level by default; DEBUG with `-v`
- **Log file**: Always DEBUG level — full detail on every file processed

Each run ends with a summary showing counts by format (JPEG/TIFF, PNG, HEIC, GIF, video), files copied without metadata, unknown timestamps, GPS injections, and any errors.

## Testing

```bash
python -m pytest tests/ -v
```

Tests cover metadata parsing, format handlers (JPEG, PNG, GIF, WebP), GPS injection, file timestamp setting, extension constants, and end-to-end scenarios including dry-run and skip-existing modes.
