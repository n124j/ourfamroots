"""Unit tests for crop_person_photo."""
from __future__ import annotations

import io

from PIL import Image

from src.infrastructure.ai_import.photo_cropping import crop_person_photo


def _make_test_image(width: int, height: int) -> bytes:
    im = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def test_crop_person_photo_returns_expected_dimensions() -> None:
    source = _make_test_image(1000, 800)
    # bbox = 10%-30% of width, 20%-50% of height
    cropped_bytes = crop_person_photo(source, [0.1, 0.2, 0.2, 0.3])

    cropped = Image.open(io.BytesIO(cropped_bytes))
    assert cropped.format == "JPEG"
    assert cropped.width == 200   # 0.2 * 1000
    assert cropped.height == 240  # 0.3 * 800


def test_crop_person_photo_clamps_out_of_bounds_bbox() -> None:
    source = _make_test_image(500, 500)
    # bbox extends past the right/bottom edge
    cropped_bytes = crop_person_photo(source, [0.9, 0.9, 0.5, 0.5])

    cropped = Image.open(io.BytesIO(cropped_bytes))
    assert cropped.width == 50    # clamped to 500 - 450
    assert cropped.height == 50
