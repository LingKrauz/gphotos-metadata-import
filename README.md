# Google Photos Metadata Injector

A Python utility that injects photo taken timestamps from Google Photos supplemental metadata JSON files into actual media files (photos and videos). It's a non-destructive batch processor that reads the exported JSON metadata and updates EXIF/container tags in corresponding media files.

## Features

✅ **Non-destructive**: Outputs to a separate directory, preserves originals  
✅ **Handles duplicate filenames**: Matches `image(20).jpeg` with `image.jpeg.supplemental-metadata(20).json`  
✅ **Flexible JSON naming**: Handles both `.supplemental-metadata.json` and typo variant `.supplemental-metada.json`  
✅ **Photo formats**:
- JPEG/TIFF: EXIF DateTimeOriginal and DateTime tags
- PNG: Text chunks (DateTimeOriginal, CreationTime, GooglePhotosTaken)
- WebP: EXIF DateTimeOriginal and DateTime tags
- HEIC: EXIF metadata (with pillow-heif)
- GIF: Comment field with date/time
- BMP: Copied without metadata (no standard support)
✅ **Video support**: Updates container creation_time metadata using ffmpeg  
✅ **Graceful degradation**: Continues processing if optional tools (ffmpeg, pillow-heif) are unavailable  
✅ **Unknown timestamps**: Separates files with missing timestamps into an "Unknown Timestamp" folder  
✅ **Comprehensive logging**: Detailed logs with success/error breakdown by format  
✅ **Recursive processing**: Handles nested folder structures  
✅ **Dry-run mode**: Preview what would be processed without modifying anything  
✅ **Resume support**: `--skip-existing` to skip already-processed files  
✅ **Progress reporting**: Periodic progress updates during processing  

## Installation

### Prerequisites
- Python 3.7+
- ffmpeg (optional, for video metadata support)
- pillow-heif (optional, for HEIC/HEIF support)

### Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Install ffmpeg for video metadata support:
   - **Windows**: Download from https://ffmpeg.org/download.html or use `choco install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`

## Usage

### Basic usage (current directory as input)
```bash
python inject_google_photos_metadata.py
```
Output will go to `./_updated`

### Specify input and output directories
```bash
python inject_google_photos_metadata.py \
  --input-root "/path/to/Google Photos" \
  --output-root "/path/to/Google Photos Updated"
```

### Using environment variables
```bash
export GPHOTOS_INPUT_ROOT="/path/to/Google Photos"
export GPHOTOS_OUTPUT_ROOT="/path/to/Google Photos Updated"
python inject_google_photos_metadata.py
```

### Custom log file location
```bash
python inject_google_photos_metadata.py \
  --input-root "/path/to/input" \
  --output-root "/path/to/output" \
  --log-file "/path/to/logfile.log"
```

### Dry run (preview without changes)
```bash
python inject_google_photos_metadata.py --dry-run
```

### Resume an interrupted run
```bash
python inject_google_photos_metadata.py --skip-existing
```

### Verbose output (DEBUG level on console)
```bash
python inject_google_photos_metadata.py -v
```

### Help
```bash
python inject_google_photos_metadata.py --help
```

## How it works

1. Scans the input directory recursively for `.supplemental-metadata.json` files
2. Matches each JSON file to its corresponding media file (photo or video)
3. Extracts the `photoTakenTime` timestamp from JSON
4. Updates the media file's metadata based on file type
5. Outputs processed files to output directory with folder structure preserved
6. Generates a detailed log at `{output_root}/metadata_injection.log`

Files with missing timestamps are copied to an `Unknown Timestamp` subfolder without metadata updates.

## Input/Output

- **Input**: Directory containing photo subdirectories with both media files and `.supplemental-metadata.json` files
- **Output**: Identical folder structure in output directory with updated media files
- **Log**: `{output_root}/metadata_injection.log` - detailed processing report

### Example

```
Input structure:
  Photos from 2014/
    ├── image(20).jpeg
    └── image.jpeg.supplemental-metadata(20).json

Output structure:
  Photos from 2014/
    └── image(20).jpeg  (with DateTimeOriginal updated from JSON)
  metadata_injection.log
  Unknown Timestamp/  (if any files had missing timestamps)
```

## Metadata Fields Updated

### JPEG/TIFF/WebP Photos
- **EXIF DateTimeOriginal** (tag 0x9003): When the photo was taken
- **EXIF DateTime** (tag 0x0132): Secondary timestamp for compatibility

### PNG Photos
- **Text chunks**: DateTimeOriginal, CreationTime, GooglePhotosTaken
- View with: image viewers supporting PNG metadata or `pngcheck -t <file>`

### HEIC Photos
- **EXIF DateTimeOriginal, DateTimeDigitized, DateTime**: When pillow-heif is available
- Files are copied without metadata if pillow-heif is not installed

### GIF Photos
- **Comment field**: Contains DateTimeOriginal and GooglePhotosTaken
- View with: `gifsicle --info <file>` or image viewers

### Videos
- **creation_time**: Container-level metadata timestamp (when ffmpeg is available)
- Files are copied without metadata if ffmpeg is not installed

## Logging

### Log Output
- **Console**: INFO level and above (progress, warnings, errors)
- **Log file**: DEBUG level and above (detailed processing info)

### Summary
Each run produces a summary showing:
- Total processed files
- Skipped files
- Errors encountered
- Success counts by format (JPEG/TIFF, PNG, HEIC, GIF, videos)
- Files copied without metadata
- Files with unknown timestamps

### Troubleshooting
Check the log file for:
- Why specific files were skipped
- Detailed error messages with file paths
- Format-specific metadata update failures

## Performance

Processing time depends on:
- Number of files (metadata reading is fast)
- File sizes (especially videos - no re-encoding, just metadata copy)
- Disk I/O speed

Reference: ~60 photos/videos typically processes in 5-10 minutes.

## Safety

✅ **Non-destructive**: Original files are never modified
✅ **Safe to run multiple times**: Output directory is created fresh each time
✅ **Comprehensive error handling**: Errors on individual files don't stop processing

## Optional Dependencies

The script gracefully handles missing optional dependencies:

- **piexif**: Better EXIF support. If missing, falls back to Pillow's basic EXIF
- **ffmpeg**: Required for video metadata. If missing, videos are copied without metadata
- **pillow-heif**: Required for HEIC support. If missing, HEIC files are copied without metadata

Install these dependencies for full functionality:
```bash
pip install piexif pillow-heif
```

## Testing

Run the test suite with pytest:
```bash
pip install pytest
python -m pytest tests/ -v
```

Tests cover metadata parsing, format-specific handlers (JPEG, PNG, GIF, WebP), extension constants, and end-to-end integration scenarios including dry-run and skip-existing modes.
