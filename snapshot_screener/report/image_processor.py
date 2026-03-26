"""Image processing for report generation.

Decodes base64 images, resizes with Pillow, and re-encodes as JPEG.
Click dot overlay is NOT done here -- it's handled by CSS in the template.
"""
from __future__ import annotations

import base64
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


def process_image_for_report(
    image_b64: str,
    max_width: int = 640,
    max_height: int = 360,
    quality: int = 80,
) -> str:
    """Decode a base64 image, resize, compress to JPEG, return base64 string.

    Parameters
    ----------
    image_b64:
        Base64-encoded image data (no ``data:`` prefix).
    max_width:
        Maximum width after resize.
    max_height:
        Maximum height after resize.
    quality:
        JPEG quality (1-95).

    Returns
    -------
    str
        Base64-encoded JPEG string (no ``data:`` prefix -- template handles that).
    """
    raw = base64.b64decode(image_b64)
    img = Image.open(io.BytesIO(raw))

    # Resize maintaining aspect ratio
    img.thumbnail((max_width, max_height), Image.LANCZOS)

    # Convert to RGB if necessary (e.g. RGBA PNGs)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Encode as JPEG
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode("ascii")
