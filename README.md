# Google Photos Metadata Injector

A Python script that reads EXIF date taken information from Google Photos supplemental metadata JSON files and writes it to the actual photo/video files.

## Features

✅ **Handles duplicate filenames**: Matches `image(20).jpeg` with `image.jpeg.supplemental-metadata(20).json`  
✅ **Flexible JSON naming**: Handles both `supplemental-metadata.json` and typo variant `supplemental-metada.json`  
✅ **Photo support**: Updates EXIF DateTimeOriginal for JPEG/TIFF files  
✅ **PNG support**: Adds date/time metadata in PNG text chunks  
✅ **HEIC support**: Updates EXIF metadata in HEIC files (with pillow-heif)  
✅ **GIF support**: Adds date/time in GIF comment metadata  
✅ **Video support**: Updates creation time metadata using ffmpeg  
✅ **Non-destructive**: Outputs to separate directory, preserves originals  
✅ **Comprehensive logging**: Detailed logs of successes and errors  
✅ **Recursive processing**: Handles nested folder structures  

## Installation

### Prerequisites
- Python 3.7+
- ffmpeg (optional, but recommended for video support)

### Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Install ffmpeg for video metadata support:
   - **Windows**: Download from https://ffmpeg.org/download.html or use: `choco install ffmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`

## Usage

Run the script with explicit paths:
```bash
python inject_google_photos_metadata.py \
  --input-root "C:\Users\Mitchell\Downloads\Google Photos" \
  --output-root "C:\Users\Mitchell\Downloads\Google Photos Updated"
```

You can also use environment variables instead of CLI arguments:
```bash
set GPHOTOS_INPUT_ROOT=C:\Users\Mitchell\Downloads\Google Photos
set GPHOTOS_OUTPUT_ROOT=C:\Users\Mitchell\Downloads\Google Photos Updated
python inject_google_photos_metadata.py
```

If you omit `--output-root`, the script defaults to a sibling directory named `<input-root>_updated`.
If you omit both `--output-root` and `GPHOTOS_OUTPUT_ROOT`, the default log file is created at `output-root/metadata_injection.log`.

The script will:
1. Find all `.supplemental-metadata.json` files in the input directory
2. Match each JSON file to its corresponding photo/video
3. Extract the "photo taken" timestamp from the JSON
4. Update the media file's metadata with this timestamp
5. Save the updated files to the output directory (preserving folder structure)
6. Generate a detailed log file

## Configuration

No hard-coded paths are required anymore. Use the `--input-root` and `--output-root` arguments, or set these environment variables:
- `GPHOTOS_INPUT_ROOT`
- `GPHOTOS_OUTPUT_ROOT`

## Output

- **Output directory**: Contains your photos/videos with updated metadata organized in the same folder structure
- **Log file**: `Google Photos Updated/metadata_injection.log` - detailed processing report

## Example

```
Input structure:
Photos from 2014/
  image(20).jpeg
  image.jpeg.supplemental-metadata(20).json

After processing, output will contain:
Photos from 2014/
  image(20).jpeg  <-- with DateTimeOriginal updated from JSON
```

## Troubleshooting

### Issue: "ffmpeg not found"
**Solution**: Install ffmpeg (see Installation section). Videos will still be copied, but metadata won't be updated.

### Issue: "Pillow not installed"
**Solution**: Run `pip install -r requirements.txt`

### Issue: Some files are skipped
**Solution**: Check the log file at `{OUTPUT_ROOT}/metadata_injection.log` for details on why files were skipped.

### Issue: File matching failures
**Solution**: The script handles standard and duplicate naming patterns. If a media file has no JSON, it will be skipped with a warning in the log.

## Metadata Fields Updated

### Photos (JPEG/TIFF)
- **EXIF DateTimeOriginal** (0x9003): Primary field - when the photo was taken
- **EXIF DateTime** (0x0132): Secondary field for compatibility

### Photos (PNG)
- **PNG text chunks**: DateTimeOriginal, CreationTime, GooglePhotosTaken
- View with: `pngcheck -t <file>` or image viewers that support PNG metadata

### Photos (HEIC)
- **EXIF DateTimeOriginal**: When pillow-heif library is available
- Falls back to copying without metadata if library not installed

### Photos (GIF)
- **GIF comment**: DateTimeOriginal and GooglePhotosTaken in comment field
- View with: `gifsicle --info <file>` or image viewers

### Videos
- **creation_time**: Video container metadata (when ffmpeg is available)
- Falls back to copying without metadata if ffmpeg not installed

## Performance

Processing time depends on:
- Number of files (metadata reading is fast, media copying/processing is slower)
- Video file sizes (re-encoding not done, just metadata copy)
- Disk speed

For reference: ~60 photos/videos ~ 5-10 minutes depending on sizes and disk speed.

## Safety

✅ **Non-destructive**: Original files are never modified
✅ **Safe to run multiple times**: Output directory structure is created fresh each time
✅ **Comprehensive error handling**: Errors don't stop processing, logged for review

## Log File Format

The log file contains:
- Timestamp and severity level for each operation
- Detailed progress (e.g., "Successfully processed: Photos from 2014/image(20).jpeg")
- Any errors encountered with context
- Summary statistics at the end

Check the log file to verify all files were processed correctly and to diagnose any issues.
