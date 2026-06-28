import os
import rawpy
from PIL import Image
from io import BytesIO

def extract_thumbnail(dng_path, output_dir, max_size=(640, 640)):
    """
    Extracts the embedded JPEG thumbnail from a DNG file and saves it.
    If the thumbnail is large, resizes it to a smaller dimension to save space
    and API overhead.
    Returns the path to the saved thumbnail.
    """
    basename = os.path.basename(dng_path)
    filename_without_ext = os.path.splitext(basename)[0]
    output_filename = f"{filename_without_ext}.jpg"
    output_path = os.path.join(output_dir, output_filename)
    
    # If it already exists, skip extraction
    if os.path.exists(output_path):
        return output_path
        
    try:
        with rawpy.imread(dng_path) as raw:
            try:
                thumb = raw.extract_thumb()
            except rawpy.LibRawNoThumbnailError:
                print(f"No thumbnail found in {dng_path}")
                return None
            
            if thumb.format == rawpy.ThumbFormat.JPEG:
                # Inspect dimensions without decoding the whole image to save CPU
                with Image.open(BytesIO(thumb.data)) as image:
                    width, height = image.size
                    if width <= max_size[0] and height <= max_size[1]:
                        # Save raw bytes directly (instant extraction)
                        with open(output_path, "wb") as f:
                            f.write(thumb.data)
                        return output_path
                    else:
                        # Resize using BICUBIC (faster than LANCZOS)
                        image.thumbnail(max_size, Image.Resampling.BICUBIC)
                        image.save(output_path, "JPEG", quality=80)
                return output_path
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                # Less common for DNGs but possible
                with Image.fromarray(thumb.data) as image:
                    image.thumbnail(max_size, Image.Resampling.BICUBIC)
                    image.save(output_path, "JPEG", quality=80)
                return output_path
    except Exception as e:
        print(f"Error extracting thumbnail from {dng_path}: {e}")
        return None

def process_directory(source_dir, cache_dir):
    """
    Processes a directory of DNGs, extracting thumbnails to cache_dir.
    Returns a list of dictionaries with original dng path and extracted thumb path.
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        
    results = []
    
    for filename in os.listdir(source_dir):
        if filename.lower().endswith('.dng'):
            dng_path = os.path.join(source_dir, filename)
            results.append(dng_path)
            
    return results
