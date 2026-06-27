"""Image and document processing — thumbnails, compression, EXIF, PDF."""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from PIL import Image, ExifTags, UnidentifiedImageError
from PIL.ExifTags import TAGS, GPSTAGS

from src.domain.media.entities import (
    ExifData,
    GpsCoordinate,
    ImageDimensions,
    ThumbnailSize,
)

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

WEBP_QUALITY = 85          # lossy WebP quality for compressed variant
THUMB_SQUARE  = ThumbnailSize.SMALL   # 200 — square crop
THUMB_PREVIEW = ThumbnailSize.MEDIUM  # 600 — longest-edge fit

# EXIF orientation → Pillow transpose operation
_ORIENTATION_TRANSPOSE = {
    2: Image.FLIP_LEFT_RIGHT,
    3: Image.ROTATE_180,
    4: Image.FLIP_TOP_BOTTOM,
    5: Image.TRANSPOSE,
    6: Image.ROTATE_270,
    7: Image.TRANSVERSE,
    8: Image.ROTATE_90,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _auto_orient(img: Image.Image) -> Image.Image:
    """Apply EXIF orientation so the returned image is visually upright."""
    try:
        exif = img._getexif()  # type: ignore[attr-defined]
        if not exif:
            return img
        for tag_id, value in exif.items():
            if TAGS.get(tag_id) == "Orientation":
                op = _ORIENTATION_TRANSPOSE.get(value)
                if op:
                    img = img.transpose(op)
                break
    except Exception:
        pass
    return img


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert to RGB (drops alpha / palette), required before JPEG/WebP encode."""
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


# ── Thumbnail generation ───────────────────────────────────────────────────────

def generate_thumb_square(image_bytes: bytes, size: int = THUMB_SQUARE) -> bytes:
    """
    Return a square-cropped WebP thumbnail (centre crop).
    Output: WebP bytes at *size* × *size*.
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = _auto_orient(img)
    img = _to_rgb(img)

    # Resize so that the shortest side == size, then centre-crop
    w, h = img.size
    scale = size / min(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left   = (new_w - size) // 2
    top    = (new_h - size) // 2
    img    = img.crop((left, top, left + size, top + size))

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=4)
    return buf.getvalue()


def generate_thumb_preview(image_bytes: bytes, max_side: int = THUMB_PREVIEW) -> bytes:
    """
    Return a WebP thumbnail constrained to *max_side* on the longest edge.
    Aspect ratio is preserved.
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = _auto_orient(img)
    img = _to_rgb(img)
    img.thumbnail((max_side, max_side), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=4)
    return buf.getvalue()


# ── Compression ────────────────────────────────────────────────────────────────

def compress_image(image_bytes: bytes, quality: int = WEBP_QUALITY) -> bytes:
    """
    Re-encode as WebP at *quality*.
    Handles HEIC/HEIF if pyheif is available (falls back gracefully).
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = _auto_orient(img)
    img = _to_rgb(img)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


def convert_heic(heic_bytes: bytes) -> bytes:
    """
    Convert HEIC/HEIF → JPEG bytes using pyheif + Pillow.
    Raises ImportError if pyheif is not installed.
    """
    try:
        import pyheif  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pyheif is required for HEIC/HEIF conversion. "
            "Install with: pip install pyheif"
        ) from exc

    heif_file = pyheif.read(heic_bytes)
    img = Image.frombytes(
        heif_file.mode,
        heif_file.size,
        heif_file.data,
        "raw",
        heif_file.mode,
        heif_file.stride,
    )
    img = _to_rgb(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Dimensions ────────────────────────────────────────────────────────────────

def get_image_dimensions(image_bytes: bytes) -> ImageDimensions:
    img = Image.open(io.BytesIO(image_bytes))
    img = _auto_orient(img)
    return ImageDimensions(width=img.width, height=img.height)


# ── EXIF extraction ────────────────────────────────────────────────────────────

def _rational_to_float(rational) -> Optional[float]:
    """Convert an IFDRational or (num, den) tuple to float."""
    try:
        if hasattr(rational, "numerator"):
            return rational.numerator / rational.denominator if rational.denominator else None
        num, den = rational
        return num / den if den else None
    except Exception:
        return None


def _parse_gps(gps_info: dict) -> Optional[GpsCoordinate]:
    try:
        lat_dms  = gps_info.get(2)   # GPSLatitude
        lat_ref  = gps_info.get(1)   # GPSLatitudeRef  ('N'/'S')
        lon_dms  = gps_info.get(4)   # GPSLongitude
        lon_ref  = gps_info.get(3)   # GPSLongitudeRef ('E'/'W')

        if not (lat_dms and lon_dms):
            return None

        def dms_to_decimal(dms) -> float:
            d = _rational_to_float(dms[0]) or 0
            m = _rational_to_float(dms[1]) or 0
            s = _rational_to_float(dms[2]) or 0
            return d + m / 60 + s / 3600

        lat = dms_to_decimal(lat_dms)
        lon = dms_to_decimal(lon_dms)
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon
        return GpsCoordinate(latitude=lat, longitude=lon)
    except Exception:
        return None


def _parse_exif_datetime(value: str) -> Optional[datetime]:
    """Parse EXIF DateTimeOriginal 'YYYY:MM:DD HH:MM:SS' → datetime."""
    try:
        return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return None


def extract_exif(image_bytes: bytes) -> ExifData:
    """
    Extract EXIF metadata from JPEG/TIFF/WebP/HEIC image bytes.
    Always returns an ExifData instance (fields are None if unavailable).
    """
    exif_data = ExifData()

    try:
        img = Image.open(io.BytesIO(image_bytes))
        raw_exif = img._getexif()  # type: ignore[attr-defined]
        if not raw_exif:
            return exif_data

        # Build tag_name → value map
        named: dict = {}
        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            named[tag_name] = value

        exif_data.date_taken    = _parse_exif_datetime(named.get("DateTimeOriginal") or named.get("DateTime"))
        exif_data.camera_make   = named.get("Make")
        exif_data.camera_model  = named.get("Model")
        exif_data.lens_model    = named.get("LensModel")
        exif_data.iso           = named.get("ISOSpeedRatings") or named.get("PhotographicSensitivity")
        exif_data.flash_fired   = bool(named["Flash"] & 0x1) if "Flash" in named else None
        exif_data.orientation   = int(named.get("Orientation", 1))

        if "FocalLength" in named:
            exif_data.focal_length_mm = _rational_to_float(named["FocalLength"])
        if "FNumber" in named:
            exif_data.aperture = _rational_to_float(named["FNumber"])
        if "ExposureTime" in named:
            et = _rational_to_float(named["ExposureTime"])
            if et:
                exif_data.shutter_speed = (
                    f"1/{int(round(1 / et))}" if et < 1 else f"{et:.1f}s"
                )

        # GPS
        gps_info_raw = named.get("GPSInfo")
        if gps_info_raw:
            gps_named = {GPSTAGS.get(k, k): v for k, v in gps_info_raw.items()}
            # Re-map numeric keys to GPSTAGS numeric for _parse_gps
            exif_data.gps = _parse_gps(gps_info_raw)

        exif_data.raw = {k: str(v) for k, v in named.items() if k != "GPSInfo"}

    except (UnidentifiedImageError, AttributeError, Exception) as exc:
        log.debug("EXIF extraction failed: %s", exc)

    return exif_data


# ── PDF processing ─────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 100_000) -> str:
    """
    Extract plain text from a PDF using pypdf.
    Returns at most *max_chars* characters (prevents storage of enormous texts).
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise ImportError("pypdf is required. Install with: pip install pypdf") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
        total += len(text)
        if total >= max_chars:
            break

    return "\n".join(parts)[:max_chars]


def pdf_first_page_preview(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    """
    Render the first page of a PDF to a JPEG using pdf2image + Poppler.
    Returns JPEG bytes at *dpi* resolution.
    Raises ImportError if pdf2image / Poppler are not installed.
    """
    try:
        from pdf2image import convert_from_bytes  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "pdf2image is required. Install with: pip install pdf2image "
            "(also requires Poppler: apt-get install poppler-utils)"
        ) from exc

    pages = convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=1)
    if not pages:
        raise ValueError("pdf2image returned no pages")

    img = _to_rgb(pages[0])
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ── Metadata JSON serialisation ────────────────────────────────────────────────

def build_metadata_json(
    exif: Optional[ExifData] = None,
    dimensions: Optional[ImageDimensions] = None,
    extracted_text: Optional[str] = None,
    duration_seconds: Optional[float] = None,
) -> bytes:
    """Serialise all extracted metadata to JSON bytes for S3 storage."""
    payload: dict = {}
    if exif:
        payload["exif"] = exif.to_dict()
    if dimensions:
        payload["dimensions"] = {
            "width": dimensions.width,
            "height": dimensions.height,
            "megapixels": dimensions.megapixels,
            "aspect_ratio": round(dimensions.aspect_ratio, 4),
        }
    if extracted_text is not None:
        payload["extracted_text"] = extracted_text
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    return json.dumps(payload, default=str).encode()
