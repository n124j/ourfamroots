"""Crops a single person's photo out of a family-tree screenshot using a
normalized [x, y, width, height] bounding box from vision_extraction."""
from __future__ import annotations

import io

from PIL import Image


def crop_person_photo(image_bytes: bytes, bbox: list[float]) -> bytes:
    """Return JPEG bytes of the region *bbox* (normalized 0-1 [x,y,w,h])
    cropped out of *image_bytes*, clamped to the image's actual dimensions."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    x, y, w, h = bbox

    left = max(0, min(width, round(x * width)))
    top = max(0, min(height, round(y * height)))
    right = max(left, min(width, round((x + w) * width)))
    bottom = max(top, min(height, round((y + h) * height)))

    cropped = image.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
