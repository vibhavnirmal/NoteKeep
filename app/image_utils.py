"""Image processing utilities for note images."""

import base64
import io

from PIL import Image


def compress_image(image_data: bytes, max_size_kb: int = 100) -> str:
    """
    Compress image to be under max_size_kb while maintaining quality.
    Returns base64 encoded data URL.
    
    Args:
        image_data: Raw image bytes
        max_size_kb: Maximum size in kilobytes (default 100KB)
    
    Returns:
        Base64 data URL string (e.g., "data:image/jpeg;base64,...")
    """
    try:
        # Open image
        img = Image.open(io.BytesIO(image_data))
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Start with high quality
        quality = 95
        output_format = 'JPEG'
        
        while quality > 20:
            output = io.BytesIO()
            img.save(output, format=output_format, quality=quality, optimize=True)
            size_kb = len(output.getvalue()) / 1024
            
            if size_kb <= max_size_kb:
                break
            
            # Reduce quality for next iteration
            quality -= 5
        
        # If still too large, resize the image
        if size_kb > max_size_kb:
            scale_factor = (max_size_kb / size_kb) ** 0.5
            new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format=output_format, quality=85, optimize=True)
        
        # Encode as base64 data URL
        output.seek(0)
        img_base64 = base64.b64encode(output.read()).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"
    
    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}") from e


def validate_image(image_data: bytes) -> bool:
    """
    Validate that the data is a valid image.
    
    Args:
        image_data: Raw image bytes
    
    Returns:
        True if valid image, False otherwise
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        return True
    except Exception:
        return False
