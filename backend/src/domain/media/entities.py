"""Media domain entities."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ── Enumerations ───────────────────────────────────────────────────────────────

class MediaCategory(str, Enum):
    PHOTO     = "PHOTO"
    DOCUMENT  = "DOCUMENT"
    AUDIO     = "AUDIO"
    VIDEO     = "VIDEO"
    OTHER     = "OTHER"


class ProcessingStatus(str, Enum):
    PENDING    = "PENDING"      # record created, waiting for client upload confirmation
    CONFIRMED  = "CONFIRMED"    # client confirmed upload; task enqueued
    PROCESSING = "PROCESSING"   # Celery worker running
    READY      = "READY"        # all variants generated; fully usable
    FAILED     = "FAILED"       # processing error; original still accessible


class ThumbnailSize(int, Enum):
    SMALL  = 200   # square crop, gallery grid
    MEDIUM = 600   # longest-edge constrained, preview


# MIME type → category mapping
MIME_CATEGORY: dict[str, MediaCategory] = {
    "image/jpeg":      MediaCategory.PHOTO,
    "image/png":       MediaCategory.PHOTO,
    "image/webp":      MediaCategory.PHOTO,
    "image/gif":       MediaCategory.PHOTO,
    "image/heic":      MediaCategory.PHOTO,
    "image/heif":      MediaCategory.PHOTO,
    "image/tiff":      MediaCategory.PHOTO,
    "application/pdf": MediaCategory.DOCUMENT,
    "application/msword":                                        MediaCategory.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": MediaCategory.DOCUMENT,
    "audio/mpeg":      MediaCategory.AUDIO,
    "audio/wav":       MediaCategory.AUDIO,
    "audio/ogg":       MediaCategory.AUDIO,
    "video/mp4":       MediaCategory.VIDEO,
    "video/quicktime": MediaCategory.VIDEO,
    "video/avi":       MediaCategory.VIDEO,
}

# Max upload size per category (bytes)
MAX_FILE_SIZE: dict[MediaCategory, int] = {
    MediaCategory.PHOTO:    50  * 1024 * 1024,   # 50 MB
    MediaCategory.DOCUMENT: 100 * 1024 * 1024,   # 100 MB
    MediaCategory.AUDIO:    200 * 1024 * 1024,   # 200 MB
    MediaCategory.VIDEO:    500 * 1024 * 1024,   # 500 MB
    MediaCategory.OTHER:    50  * 1024 * 1024,   # 50 MB
}


# ── Value objects ──────────────────────────────────────────────────────────────

@dataclass
class ImageDimensions:
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 1.0

    @property
    def megapixels(self) -> float:
        return round(self.width * self.height / 1_000_000, 1)


@dataclass
class GpsCoordinate:
    latitude: float   # degrees, positive = North
    longitude: float  # degrees, positive = East

    def __str__(self) -> str:
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.6f}°{lat_dir}, {abs(self.longitude):.6f}°{lon_dir}"


@dataclass
class ExifData:
    """Structured EXIF metadata extracted from a photo."""
    date_taken: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    focal_length_mm: Optional[float] = None
    aperture: Optional[float] = None        # f-number
    shutter_speed: Optional[str] = None     # e.g. "1/250"
    iso: Optional[int] = None
    flash_fired: Optional[bool] = None
    gps: Optional[GpsCoordinate] = None
    orientation: int = 1                    # EXIF orientation tag (1–8)
    # Raw dict preserved for future fields
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date_taken":     self.date_taken.isoformat() if self.date_taken else None,
            "camera_make":    self.camera_make,
            "camera_model":   self.camera_model,
            "lens_model":     self.lens_model,
            "focal_length_mm": self.focal_length_mm,
            "aperture":       self.aperture,
            "shutter_speed":  self.shutter_speed,
            "iso":            self.iso,
            "flash_fired":    self.flash_fired,
            "gps": {
                "latitude":  self.gps.latitude,
                "longitude": self.gps.longitude,
            } if self.gps else None,
            "orientation":    self.orientation,
        }


@dataclass
class MediaVariants:
    """S3 keys for all processed variants of a media item."""
    original_key: str
    compressed_key: Optional[str]   = None   # WebP-compressed image
    thumb_200_key: Optional[str]    = None   # 200px square crop
    thumb_600_key: Optional[str]    = None   # 600px preview
    preview_key: Optional[str]      = None   # first-page render (PDFs/docs)
    metadata_key: Optional[str]     = None   # extracted text / EXIF JSON in S3


# ── Aggregate root ─────────────────────────────────────────────────────────────

@dataclass
class MediaItem:
    """A single media file attached to a person or tree."""

    id: uuid.UUID
    tree_id: uuid.UUID
    tenant_id: uuid.UUID

    # Uploader / ownership
    uploaded_by_id: uuid.UUID

    # Attachment (person is optional — media can attach to tree root)
    person_id: Optional[uuid.UUID]

    # File identity
    original_filename: str
    content_type: str
    file_size_bytes: int
    category: MediaCategory

    # Storage
    variants: MediaVariants

    # Processing
    status: ProcessingStatus
    celery_task_id: Optional[str] = None
    processing_error: Optional[str] = None

    # Extracted metadata
    dimensions: Optional[ImageDimensions] = None
    exif: Optional[ExifData] = None
    extracted_text: Optional[str] = None     # PDFs / documents
    duration_seconds: Optional[float] = None # audio / video

    # User-supplied metadata
    title: Optional[str] = None
    description: Optional[str] = None
    date_circa: Optional[str] = None         # "ca. 1920" — user-entered date string
    year: Optional[int] = None               # machine-readable year (from EXIF or user)
    tags: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: bool = False

    @classmethod
    def create(
        cls,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        uploaded_by_id: uuid.UUID,
        person_id: Optional[uuid.UUID],
        original_filename: str,
        content_type: str,
        file_size_bytes: int,
        storage_key: str,
    ) -> "MediaItem":
        category = MIME_CATEGORY.get(content_type, MediaCategory.OTHER)
        return cls(
            id=uuid.uuid4(),
            tree_id=tree_id,
            tenant_id=tenant_id,
            uploaded_by_id=uploaded_by_id,
            person_id=person_id,
            original_filename=original_filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            category=category,
            variants=MediaVariants(original_key=storage_key),
            status=ProcessingStatus.PENDING,
        )

    @property
    def is_image(self) -> bool:
        return self.category == MediaCategory.PHOTO

    @property
    def is_document(self) -> bool:
        return self.category == MediaCategory.DOCUMENT

    @property
    def display_name(self) -> str:
        return self.title or self.original_filename


@dataclass
class PresignedUploadTicket:
    """Issued to the client before direct-to-S3 upload."""
    media_id: uuid.UUID
    upload_url: str          # S3 presigned PUT URL
    upload_fields: dict[str, str]  # for multipart/form-data POST (if using POST instead of PUT)
    storage_key: str
    expires_in_seconds: int
    max_size_bytes: int
    allowed_content_types: list[str]
