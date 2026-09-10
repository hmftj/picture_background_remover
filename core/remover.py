"""Core background removal and image processing engine.

Provides unified session management, EXIF normalization, background removal,
compositing, preview generation, and safe image export.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from rembg import new_session, remove

# Global cache for sessions to avoid re-initializing models repeatedly
_SESSION_CACHE: Dict[str, Any] = {}


def get_session(model_name: str = "u2net", force_cpu: bool = True) -> Any:
    """Retrieve or create a cached rembg ONNX session.

    Args:
        model_name: The rembg model identifier (e.g., 'u2net', 'u2netp', 'isnet-general-use').
        force_cpu: If True, forces CPU execution provider to prevent missing CUDA DLL errors.

    Returns:
        A cached rembg session object.
    """
    cache_key = f"{model_name}_{'cpu' if force_cpu else 'default'}"
    if cache_key in _SESSION_CACHE:
        return _SESSION_CACHE[cache_key]

    providers = ["CPUExecutionProvider"] if force_cpu else None
    try:
        if providers:
            session = new_session(model_name=model_name, providers=providers)
        else:
            session = new_session(model_name=model_name)
    except Exception:
        # Fallback to default session creation if custom providers failed
        session = new_session(model_name=model_name)

    _SESSION_CACHE[cache_key] = session
    return session


def parse_color(color: Union[str, Tuple[int, int, int], Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    """Parse color into an RGBA 4-tuple.

    Accepts hex strings ('#FFF', '#FFFFFF', '#RRGGBBAA') or RGB/RGBA tuples.
    """
    if isinstance(color, (tuple, list)):
        if len(color) == 3:
            return (int(color[0]), int(color[1]), int(color[2]), 255)
        elif len(color) == 4:
            return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))
        raise ValueError(f"Invalid color tuple length: {len(color)}")

    if isinstance(color, str):
        c = color.strip().lstrip("#")
        if len(c) == 3:  # e.g. 'fff'
            r, g, b = [int(ch * 2, 16) for ch in c]
            return (r, g, b, 255)
        elif len(c) == 6:  # e.g. 'ffffff'
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            return (r, g, b, 255)
        elif len(c) == 8:  # e.g. 'ffffffff'
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            a = int(c[6:8], 16)
            return (r, g, b, a)

    raise ValueError(f"Unsupported color format: {color}")


def load_and_normalize_image(image_input: Union[str, Path, bytes, io.BytesIO, Image.Image]) -> Image.Image:
    """Load an image and normalize orientation (EXIF) and color mode.

    Args:
        image_input: File path, bytes, file-like object, or PIL Image.

    Returns:
        Normalized PIL Image in RGB or RGBA mode.
    """
    if isinstance(image_input, Image.Image):
        img = image_input.copy()
    elif isinstance(image_input, (str, Path)):
        img = Image.open(str(image_input))
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input))
    elif hasattr(image_input, "read"):
        img = Image.open(image_input)
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    # Correct phone/camera orientation using EXIF tags
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Normalize color mode: convert CMYK, P (palette), 1-bit, LA to RGB or RGBA
    if img.mode in ("RGBA", "RGB"):
        return img
    elif img.mode == "CMYK":
        return img.convert("RGB")
    elif "transparency" in img.info or img.mode in ("LA", "PA"):
        return img.convert("RGBA")
    else:
        return img.convert("RGB")


def composite_background(
    image: Image.Image,
    bgcolor: Union[str, Tuple[int, int, int], Tuple[int, int, int, int]],
) -> Image.Image:
    """Composite a transparent RGBA image over a solid background color.

    Args:
        image: Cutout image with alpha channel.
        bgcolor: Background color (hex string or RGB/RGBA tuple).

    Returns:
        Composited PIL Image.
    """
    rgba_image = image.convert("RGBA")
    rgba_color = parse_color(bgcolor)

    background = Image.new("RGBA", rgba_image.size, rgba_color)
    composited = Image.alpha_composite(background, rgba_image)

    # If alpha is fully opaque, return RGB
    if rgba_color[3] == 255:
        return composited.convert("RGB")
    return composited


def remove_background(
    image: Union[str, Path, bytes, io.BytesIO, Image.Image],
    session: Optional[Any] = None,
    alpha_matting: bool = False,
    alpha_matting_foreground_threshold: int = 240,
    alpha_matting_background_threshold: int = 10,
    alpha_matting_erode_size: int = 10,
    bgcolor: Optional[Union[str, Tuple[int, int, int], Tuple[int, int, int, int]]] = None,
) -> Image.Image:
    """Remove background from an image with optional edge refinement and background replacement.

    Args:
        image: Input image path, bytes, or PIL Image.
        session: Pre-loaded rembg session. If None, default cached session is used.
        alpha_matting: Refine edges (useful for hair, fur, complex borders).
        alpha_matting_foreground_threshold: Foreground threshold for alpha matting (0-255).
        alpha_matting_background_threshold: Background threshold for alpha matting (0-255).
        alpha_matting_erode_size: Erode size for alpha matting.
        bgcolor: Optional background color to composite behind the cutout.

    Returns:
        Processed PIL Image (RGBA if transparent, RGB/RGBA if bgcolor supplied).
    """
    norm_img = load_and_normalize_image(image)

    if session is None:
        session = get_session()

    result = remove(
        norm_img,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
        alpha_matting_background_threshold=alpha_matting_background_threshold,
        alpha_matting_erode_size=alpha_matting_erode_size,
    )

    if not isinstance(result, Image.Image):
        result = Image.open(io.BytesIO(result))

    if bgcolor is not None:
        result = composite_background(result, bgcolor)

    return result


def create_checkerboard(width: int, height: int, tile_size: int = 12, light="#333333", dark="#222222") -> Image.Image:
    """Create a checkerboard background pattern image of specified dimensions."""
    bg = Image.new("RGBA", (width, height), light)
    draw = ImageDraw.Draw(bg)

    dark_rgba = parse_color(dark)
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            if ((x // tile_size) + (y // tile_size)) % 2 == 1:
                draw.rectangle([x, y, x + tile_size - 1, y + tile_size - 1], fill=dark_rgba)

    return bg


def render_checkerboard_preview(
    image: Image.Image,
    max_size: Tuple[int, int] = (260, 260),
    tile_size: int = 12,
    light: str = "#2D2D2D",
    dark: str = "#1E1E1E",
) -> Image.Image:
    """Create a scaled preview image with a checkerboard backdrop for transparent regions.

    Args:
        image: PIL Image to preview.
        max_size: Maximum (width, height) bounding box for the preview.
        tile_size: Size of checkerboard tiles in pixels.
        light: Hex color for light checker squares.
        dark: Hex color for dark checker squares.

    Returns:
        Preview PIL Image ready for UI display.
    """
    preview = image.copy()
    preview.thumbnail(max_size, Image.Resampling.LANCZOS)

    if preview.mode == "RGBA":
        checker = create_checkerboard(preview.width, preview.height, tile_size, light=light, dark=dark)
        return Image.alpha_composite(checker, preview)

    return preview


def export_image_bytes(
    image: Image.Image,
    format: str = "PNG",
    quality: int = 95,
    bg_fill: Union[str, Tuple[int, int, int]] = (255, 255, 255),
) -> Tuple[bytes, str, str]:
    """Safely convert PIL Image to bytes in requested format.

    Automatically handles converting RGBA transparent images to solid background
    when exporting to formats without alpha support (such as JPEG).

    Args:
        image: PIL Image to export.
        format: 'PNG', 'JPEG'/'JPG', or 'WEBP'.
        quality: Compression quality for lossy formats (1-100).
        bg_fill: Solid fill color to use when converting RGBA to JPEG.

    Returns:
        Tuple of (bytes_data, mime_type, file_extension).
    """
    fmt = format.upper()
    if fmt == "JPG":
        fmt = "JPEG"

    buffer = io.BytesIO()

    if fmt == "JPEG":
        if image.mode in ("RGBA", "LA") or ("transparency" in image.info):
            # Composite transparent image over background fill
            export_img = composite_background(image, bg_fill).convert("RGB")
        else:
            export_img = image.convert("RGB")
        export_img.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue(), "image/jpeg", ".jpg"

    elif fmt == "WEBP":
        export_img = image.convert("RGBA") if image.mode == "RGBA" else image.convert("RGB")
        export_img.save(buffer, format="WEBP", quality=quality)
        return buffer.getvalue(), "image/webp", ".webp"

    else:  # Default PNG
        export_img = image.convert("RGBA") if image.mode in ("RGBA", "LA") else image
        export_img.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png", ".png"
