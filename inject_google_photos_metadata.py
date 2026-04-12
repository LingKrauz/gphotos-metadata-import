#!/usr/bin/env python3
import argparse
import os
import json
import shutil
import logging
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, List

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    import piexif
except ImportError:
    print("WARNING: piexif not installed. Installing basic Pillow EXIF support.")
    print("For better EXIF compatibility: pip install piexif")
    piexif = None

try:
    import subprocess
    # Check for ffmpeg in common locations
    FFMPEG_PATHS = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "ffmpeg.exe",
        "ffmpeg"
    ]
    HAS_FFMPEG = False
    FFMPEG_CMD = None
    for path in FFMPEG_PATHS:
        try:
            result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                HAS_FFMPEG = True
                FFMPEG_CMD = path
                break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
except Exception:
    HAS_FFMPEG = False
    FFMPEG_CMD = None

# Try to import additional libraries for extended format support
try:
    import pyheif
    HAS_PYHEIF = True
except ImportError:
    HAS_PYHEIF = False

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HAS_HEIF_SUPPORT = True
except ImportError:
    HAS_HEIF_SUPPORT = False


# Setup logging
def setup_logging(log_file: str) -> logging.Logger:
    """Configure logging to both file and console."""
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(__name__)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    
    # File handler
    fh = logging.FileHandler(log_file, mode='w')
    fh.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject Google Photos supplemental metadata into actual media files."
    )
    parser.add_argument(
        '-i', '--input-root',
        default=os.getenv('GPHOTOS_INPUT_ROOT', '.'),
        help='Directory containing exported Google Photos media and supplemental metadata JSON files. Defaults to current directory.'
    )
    parser.add_argument(
        '-o', '--output-root',
        default=os.getenv('GPHOTOS_OUTPUT_ROOT'),
        help='Directory to save processed media files. Defaults to <input-root>_updated.'
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Path to the log file. Defaults to <output-root>/metadata_injection.log.'
    )
    return parser.parse_args()


logger = logging.getLogger(__name__)


class MetadataInjector:
    """Handles injection of Google Photos metadata into actual media files."""
    
    def __init__(self, input_root: str, output_root: str, log_file: str):
        self.input_root = input_root
        self.output_root = output_root
        self.log_file = log_file
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'photos_exif': 0,      # JPEG/TIFF with EXIF updated
            'photos_png': 0,       # PNG with text metadata
            'photos_heic': 0,      # HEIC with EXIF (if supported)
            'photos_gif': 0,       # GIF with comment metadata
            'videos': 0,           # Videos with metadata updated
            'copied_no_metadata': 0,  # Files copied but no metadata update possible
            'unknown_timestamp': 0    # Files copied to Unknown Timestamp folder
        }
        self.errors: List[str] = []
    
    def find_all_metadata_files(self) -> List[str]:
        """Recursively find all supplemental metadata JSON files."""
        metadata_files = []
        
        for root, dirs, files in os.walk(self.input_root):
            for file in files:
                # Match both correct and typo variants
                if file.endswith('.supplemental-metadata.json') or \
                   file.endswith('.supplemental-metada.json'):
                    metadata_files.append(os.path.join(root, file))
        
        logger.info(f"Found {len(metadata_files)} metadata files")
        return metadata_files
    
    def find_matching_media_file(self, metadata_file: str, metadata_dir: str) -> Optional[str]:
        """
        Find the actual photo/video file that corresponds to a metadata file.
        
        Handles patterns:
        - Standard: photo.jpg + photo.jpg.supplemental-metadata.json
        - Duplicate: photo(20).jpg + photo.jpg.supplemental-metadata(20).json
        """
        metadata_filename = os.path.basename(metadata_file)
        
        # Extract base name and any duplicate number
        # Pattern: BASENAME.supplemental-metadata(NUMBER).json or BASENAME.supplemental-metada(NUMBER).json
        match = re.match(r'(.+?)\.(supplemental-metada|supplemental-metadata)(?:\((\d+)\))?\.json$', metadata_filename)
        
        if not match:
            logger.warning(f"Could not parse metadata filename: {metadata_filename}")
            return None
        
        base_name = match.group(1)  # e.g., "photo.jpg" or "image.jpeg"
        duplicate_number = match.group(3)  # e.g., "20" or None
        
        # Try standard match first: base_name directly
        direct_match = os.path.join(metadata_dir, base_name)
        if os.path.exists(direct_match) and os.path.isfile(direct_match):
            return direct_match
        
        # If we have a duplicate number, try matching with the number in the filename
        if duplicate_number:
            # Insert the number before the extension
            # e.g., "photo.jpg" becomes "photo(20).jpg"
            parts = base_name.rsplit('.', 1)
            if len(parts) == 2:
                name_part, ext = parts
                numbered_name = f"{name_part}({duplicate_number}).{ext}"
                numbered_match = os.path.join(metadata_dir, numbered_name)
                if os.path.exists(numbered_match) and os.path.isfile(numbered_match):
                    return numbered_match
        
        return None
    
    def read_metadata_json(self, json_file: str) -> Optional[Dict]:
        """Read and parse supplemental metadata JSON file."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            error_msg = f"Failed to read JSON {json_file}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None
    
    def get_photo_taken_time(self, metadata: Dict) -> Optional[str]:
        """Extract photo taken time from metadata and convert to EXIF format."""
        try:
            if 'photoTakenTime' not in metadata:
                return None
            
            photo_taken = metadata['photoTakenTime']
            timestamp = int(photo_taken.get('timestamp', 0))
            
            if timestamp == 0:
                return None
            
            # Convert Unix timestamp to datetime
            dt = datetime.fromtimestamp(timestamp, timezone.utc)
            # Format as EXIF datetime: YYYY:MM:DD HH:MM:SS
            return dt.strftime('%Y:%m:%d %H:%M:%S')
        
        except Exception as e:
            logger.debug(f"Failed to extract photo taken time: {e}")
            return None
    
    def update_photo_exif(self, photo_path: str, datetime_str: str) -> bool:
        """Update EXIF DateTimeOriginal in a photo file."""
        ext = os.path.splitext(photo_path)[1].lower()
        
        # Handle different image formats
        if ext in ['.jpg', '.jpeg', '.tiff', '.tif']:
            # Standard EXIF-supporting formats
            return self._update_photo_exif_standard(photo_path, datetime_str)
        elif ext == '.heic':
            # HEIC format - try HEIF support if available
            return self._update_photo_exif_heic(photo_path, datetime_str)
        elif ext == '.png':
            # PNG format - use text chunks for metadata
            return self._update_photo_exif_png(photo_path, datetime_str)
        elif ext == '.gif':
            # GIF format - limited metadata support
            return self._update_photo_exif_gif(photo_path, datetime_str)
        else:
            # Unknown format
            logger.debug(f"Unknown image format {ext}, skipping metadata update: {photo_path}")
            return True
    
    def _update_photo_exif_piexif(self, photo_path: str, datetime_str: str) -> bool:
        """Update EXIF using piexif library and save via Pillow to a temp file."""
        try:
            exif_dict = piexif.load(photo_path)

            # Ensure Exif and 0th exist
            if "Exif" not in exif_dict:
                exif_dict["Exif"] = {}
            if "0th" not in exif_dict:
                exif_dict["0th"] = {}

            # Update DateTimeOriginal (EXIF tag 0x9003 / 36867)
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime_str.encode('utf-8')
            # Update DateTime (tag 0x0132 / 306)
            exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime_str.encode('utf-8')

            exif_bytes = piexif.dump(exif_dict)

            # Save via Pillow to a temp file with exif bytes
            image = Image.open(photo_path)
            temp_path = photo_path + '.tmp'
            image.save(temp_path, format=image.format, exif=exif_bytes)
            shutil.move(temp_path, photo_path)
            logger.debug(f"Updated EXIF (piexif) for {photo_path}: {datetime_str}")
            return True
        except Exception as e:
            logger.debug(f"piexif update failed for {photo_path}, trying Pillow: {str(e)}")
            return False

    def _update_photo_exif_pillow(self, photo_path: str, datetime_str: str) -> bool:
        """Fallback EXIF update using Pillow's getexif()/tobytes() when piexif is not available."""
        try:
            image = Image.open(photo_path)
            exif = image.getexif()
            # Exif tag numbers: 36867 = DateTimeOriginal, 306 = DateTime
            exif[36867] = datetime_str
            exif[306] = datetime_str
            temp_path = photo_path + '.tmp'
            image.save(temp_path, format=image.format, exif=exif.tobytes())
            shutil.move(temp_path, photo_path)
            logger.debug(f"Updated EXIF (Pillow) for {photo_path}: {datetime_str}")
            return True
        except Exception as e:
            logger.debug(f"Pillow EXIF update failed for {photo_path}: {e}")
            return False

    def _update_photo_exif_standard(self, photo_path: str, datetime_str: str) -> bool:
        """Update EXIF for JPEG/TIFF files using piexif when available, falling back to Pillow."""
        try:
            # Try piexif first (more reliable for EXIF)
            if piexif:
                success = self._update_photo_exif_piexif(photo_path, datetime_str)
                if success:
                    return True
                # fall through to Pillow fallback if piexif approach failed

            # Try Pillow fallback
            return self._update_photo_exif_pillow(photo_path, datetime_str)
        except Exception as e:
            error_msg = f"Failed to update EXIF for {photo_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def _update_photo_exif_png(self, photo_path: str, datetime_str: str) -> bool:
        """Update PNG file with date/time in text chunks."""
        try:
            # Open the PNG image
            image = Image.open(photo_path)
            
            # PNG doesn't support EXIF, but we can add text metadata
            # Create metadata dictionary
            metadata = {
                'DateTimeOriginal': datetime_str,
                'CreationTime': datetime_str,
                'GooglePhotosTaken': datetime_str
            }
            
            # Save with metadata in text chunks
            temp_path = photo_path + '.tmp'
            image.save(temp_path, 'PNG', 
                      pnginfo=self._create_png_metadata(metadata))
            
            # Replace original
            shutil.move(temp_path, photo_path)
            
            logger.debug(f"Updated PNG metadata for {photo_path}: {datetime_str}")
            return True
            
        except Exception as e:
            logger.debug(f"PNG metadata update failed for {photo_path}: {e}")
            return False
    
    def _create_png_metadata(self, metadata_dict: Dict[str, str]):
        """Create PNG text chunks from metadata dictionary."""
        from PIL import PngImagePlugin
        png_info = PngImagePlugin.PngInfo()
        
        for key, value in metadata_dict.items():
            png_info.add_text(key, value)
        
        return png_info
    
    def _update_photo_exif_heic(self, photo_path: str, datetime_str: str) -> bool:
        """Update HEIC file metadata."""
        try:
            if not HAS_HEIF_SUPPORT:
                logger.debug(f"HEIC support not available for {photo_path}, copying without metadata update")
                return True  # Not an error, just unsupported

            # Use Pillow (via pillow-heif) to open and save HEIC with EXIF if piexif is available
            image = Image.open(photo_path)

            if piexif:
                # Build minimal EXIF structure
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime_str.encode('utf-8')
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = datetime_str.encode('utf-8')
                exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime_str.encode('utf-8')
                exif_bytes = piexif.dump(exif_dict)

                temp_path = photo_path + '.tmp.heic'
                image.save(temp_path, format='HEIC', exif=exif_bytes)
                shutil.move(temp_path, photo_path)
                logger.debug(f"Updated HEIC EXIF for {photo_path}: {datetime_str}")
                return True
            else:
                logger.debug(f"piexif not available; cannot write EXIF to HEIC for {photo_path}")
                return True

        except Exception as e:
            logger.debug(f"HEIC metadata update failed for {photo_path}: {e}")
            return False
    
    def _update_photo_exif_gif(self, photo_path: str, datetime_str: str) -> bool:
        """Update GIF file with comment metadata."""
        try:
            image = Image.open(photo_path)
            
            # GIF has limited metadata support, but we can add a comment
            comment_text = f"DateTimeOriginal: {datetime_str}\nGooglePhotosTaken: {datetime_str}"
            
            # Save with comment
            temp_path = photo_path + '.tmp'
            image.save(temp_path, 'GIF', comment=comment_text.encode('utf-8'))
            
            shutil.move(temp_path, photo_path)
            logger.debug(f"Updated GIF comment for {photo_path}: {datetime_str}")
            return True
            
        except Exception as e:
            logger.debug(f"GIF metadata update failed for {photo_path}: {e}")
            return False
    
    def update_video_metadata(self, video_path: str, datetime_str: str) -> bool:
        """Update creation time metadata in a video file."""
        if not HAS_FFMPEG or not FFMPEG_CMD:
            logger.warning(f"ffmpeg not found, skipping video metadata for {video_path}")
            self.stats['skipped'] += 1
            return False
        
        try:
            # Convert EXIF datetime to ISO 8601 format for ffmpeg
            # EXIF: YYYY:MM:DD HH:MM:SS -> ISO: YYYY-MM-DDTHH:MM:SSZ
            dt_obj = datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
            iso_datetime = dt_obj.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Create temporary output file
            temp_output = video_path + '.tmp.mp4'
            
            # Use ffmpeg to update metadata
            cmd = [
                FFMPEG_CMD,
                '-i', video_path,
                '-c', 'copy',  # Copy without re-encoding
                '-metadata', f'creation_time={iso_datetime}',
                '-y',  # Overwrite without asking
                temp_output
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                shutil.move(temp_output, video_path)
                logger.debug(f"Updated video metadata for {video_path}: {datetime_str}")
                return True
            else:
                error_msg = f"ffmpeg failed for {video_path}: {result.stderr}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return False
        
        except subprocess.TimeoutExpired:
            error_msg = f"ffmpeg timeout for {video_path}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to update video metadata for {video_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def process_media_file(self, media_path: str, datetime_str: str, output_path: str) -> bool:
        """Process a media file: copy it and update its metadata based on type."""
        try:
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Copy file to output location
            shutil.copy2(media_path, output_path)
            
            # Determine file type and update metadata
            ext = os.path.splitext(output_path)[1].lower()
            is_video = ext in ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm']
            is_image = ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic', '.webp']
            
            if is_video:
                success = self.update_video_metadata(output_path, datetime_str)
                if success:
                    self.stats['videos'] += 1
                else:
                    error_msg = f"Failed to update video metadata for {output_path}"
                    logger.warning(f"Metadata update failed: {output_path} (video)")
                    self.errors.append(error_msg)
            elif is_image:
                ext = os.path.splitext(output_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.tiff', '.tif']:
                    success = self.update_photo_exif(output_path, datetime_str)
                    if success:
                        self.stats['photos_exif'] += 1
                    else:
                        error_msg = f"Failed to update EXIF metadata for {output_path}"
                        logger.warning(f"Metadata update failed: {output_path} (JPEG/TIFF)")
                        self.errors.append(error_msg)
                elif ext == '.png':
                    success = self._update_photo_exif_png(output_path, datetime_str)
                    if success:
                        self.stats['photos_png'] += 1
                    else:
                        error_msg = f"Failed to update PNG metadata for {output_path}"
                        logger.warning(f"Metadata update failed: {output_path} (PNG)")
                        self.errors.append(error_msg)
                elif ext == '.heic':
                    success = self._update_photo_exif_heic(output_path, datetime_str)
                    if success:
                        self.stats['photos_heic'] += 1
                    else:
                        error_msg = f"Failed to update HEIC metadata for {output_path}"
                        logger.warning(f"Metadata update failed: {output_path} (HEIC)")
                        self.errors.append(error_msg)
                elif ext == '.gif':
                    success = self._update_photo_exif_gif(output_path, datetime_str)
                    if success:
                        self.stats['photos_gif'] += 1
                    else:
                        error_msg = f"Failed to update GIF metadata for {output_path}"
                        logger.warning(f"Metadata update failed: {output_path} (GIF)")
                        self.errors.append(error_msg)
                else:
                    # Unknown image format
                    logger.debug(f"Unknown image format {ext}, copying without metadata update: {output_path}")
                    success = True
                    self.stats['copied_no_metadata'] += 1
            else:
                logger.warning(f"Unknown file type for {output_path}, copied without metadata update")
                success = True
            
            return success
        
        except Exception as e:
            error_msg = f"Failed to process media file {media_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def process_metadata_file(self, metadata_file: str) -> bool:
        """Process a single metadata JSON file and update the corresponding media file."""
        metadata_dir = os.path.dirname(metadata_file)
        
        # Find matching media file
        media_file = self.find_matching_media_file(metadata_file, metadata_dir)
        if not media_file:
            logger.warning(f"No matching media file found for {metadata_file}")
            self.stats['skipped'] += 1
            return False
        
        # Read metadata
        metadata = self.read_metadata_json(metadata_file)
        if not metadata:
            self.stats['skipped'] += 1
            return False
        
        # Extract photo taken time
        datetime_str = self.get_photo_taken_time(metadata)
        if not datetime_str:
            # Copy file to Unknown Timestamp subdirectory
            rel_path = os.path.relpath(media_file, self.input_root)
            unknown_dir = os.path.join(self.output_root, "Unknown Timestamp")
            output_path = os.path.join(unknown_dir, rel_path)
            
            try:
                # Create output directory if needed
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                # Copy file to unknown timestamp folder
                shutil.copy2(media_file, output_path)
                self.stats['unknown_timestamp'] += 1
                logger.info(f"Copied to Unknown Timestamp: {rel_path}")
                return True
            except Exception as e:
                error_msg = f"Failed to copy {media_file} to Unknown Timestamp folder: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                self.stats['errors'] += 1
                return False
        
        # Calculate output path (preserve directory structure relative to input root)
        rel_path = os.path.relpath(media_file, self.input_root)
        output_path = os.path.join(self.output_root, rel_path)
        
        # Process the media file
        if self.process_media_file(media_file, datetime_str, output_path):
            self.stats['processed'] += 1
            logger.info(f"Successfully processed: {rel_path}")
            return True
        else:
            self.stats['errors'] += 1
            return False
    
    def run(self) -> bool:
        """Run the metadata injection process on all metadata files."""
        logger.info(f"Starting metadata injection from {self.input_root}")
        logger.info(f"Output will be saved to {self.output_root}")
        
        if not os.path.exists(self.input_root):
            logger.error(f"Input directory not found: {self.input_root}")
            return False
        
        # Check for ffmpeg
        if HAS_FFMPEG and FFMPEG_CMD:
            logger.info(f"ffmpeg found at: {FFMPEG_CMD}")
            logger.info("Video metadata will be updated")
        else:
            logger.warning("ffmpeg not found - video files will be copied without metadata updates")
            logger.info("To enable video support, install ffmpeg from https://ffmpeg.org/download.html")
        
        logger.info("Supported image formats:")
        logger.info("  JPEG/TIFF: EXIF metadata (DateTimeOriginal)")
        logger.info("  PNG: Text chunks with date/time metadata")
        logger.info("  HEIC: EXIF metadata (with pillow-heif)")
        logger.info("  GIF: Comment field with date/time metadata")
        
        # Find all metadata files
        metadata_files = self.find_all_metadata_files()
        if not metadata_files:
            logger.warning("No metadata files found!")
            return False
        
        # Process each metadata file
        for i, metadata_file in enumerate(metadata_files, 1):
            logger.debug(f"Processing {i}/{len(metadata_files)}: {metadata_file}")
            self.process_metadata_file(metadata_file)
        
        # Print summary
        self.print_summary()
        return True
    
    def print_summary(self):
        """Print processing summary."""
        logger.info("\n" + "="*60)
        logger.info("PROCESSING COMPLETE")
        logger.info("="*60)
        logger.info(f"Processed:     {self.stats['processed']}")
        logger.info(f"Skipped:       {self.stats['skipped']}")
        logger.info(f"Errors:        {self.stats['errors']}")
        logger.info(f"Photos (EXIF): {self.stats['photos_exif']}")
        logger.info(f"Photos (PNG):  {self.stats['photos_png']}")
        logger.info(f"Photos (HEIC): {self.stats['photos_heic']}")
        logger.info(f"Photos (GIF):  {self.stats['photos_gif']}")
        logger.info(f"Videos:        {self.stats['videos']}")
        logger.info(f"Copied (no metadata): {self.stats['copied_no_metadata']}")
        logger.info(f"Unknown Timestamp: {self.stats['unknown_timestamp']}")
        logger.info(f"Log file: {self.log_file}")
        
        if self.errors:
            logger.info(f"\nAll errors ({len(self.errors)} total):")
            for error in self.errors:
                logger.warning(f"  - {error}")
        
        logger.info("="*60 + "\n")


def main():
    """Main entry point."""
    global logger
    try:
        args = parse_args()
        input_root = os.path.abspath(args.input_root)
        output_root = os.path.abspath(
            args.output_root if args.output_root else f"{input_root.rstrip(os.sep)}_updated"
        )
        log_file = args.log_file if args.log_file else os.path.join(output_root, 'metadata_injection.log')

        logger = setup_logging(log_file)
        injector = MetadataInjector(input_root, output_root, log_file)
        success = injector.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
