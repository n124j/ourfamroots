"""Unit tests for media domain entities and validation logic."""
from __future__ import annotations

import uuid

import pytest

from src.domain.media.entities import (
    MAX_FILE_SIZE,
    MIME_CATEGORY,
    ExifData,
    GpsCoordinate,
    ImageDimensions,
    MediaCategory,
    MediaItem,
    MediaVariants,
    ProcessingStatus,
)
from src.domain.media.exceptions import (
    FileTooLargeError,
    MediaNotFoundError,
    MediaNotReadyError,
    UnsupportedMediaTypeError,
)
from src.infrastructure.media.s3 import make_storage_key, make_variant_key


# ── MIME category mapping ──────────────────────────────────────────────────────

class TestMimeCategoryMapping:
    @pytest.mark.parametrize("mime,expected", [
        ("image/jpeg",      MediaCategory.PHOTO),
        ("image/png",       MediaCategory.PHOTO),
        ("image/heic",      MediaCategory.PHOTO),
        ("application/pdf", MediaCategory.DOCUMENT),
        ("audio/mpeg",      MediaCategory.AUDIO),
        ("video/mp4",       MediaCategory.VIDEO),
    ])
    def test_known_mimes_map_correctly(self, mime: str, expected: MediaCategory):
        assert MIME_CATEGORY[mime] == expected

    def test_unknown_mime_falls_back_to_other(self):
        assert "application/octet-stream" not in MIME_CATEGORY


# ── MediaItem.create() ─────────────────────────────────────────────────────────

class TestMediaItemCreate:
    def _make(self, **kwargs) -> MediaItem:
        defaults = dict(
            tree_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            uploaded_by_id=uuid.uuid4(),
            person_id=uuid.uuid4(),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            file_size_bytes=1_000_000,
            storage_key="key/original.jpg",
        )
        defaults.update(kwargs)
        return MediaItem.create(**defaults)

    def test_creates_with_pending_status(self):
        item = self._make()
        assert item.status == ProcessingStatus.PENDING

    def test_assigns_uuid(self):
        item = self._make()
        assert isinstance(item.id, uuid.UUID)

    def test_infers_photo_category_from_jpeg(self):
        item = self._make(content_type="image/jpeg")
        assert item.category == MediaCategory.PHOTO

    def test_infers_document_category_from_pdf(self):
        item = self._make(content_type="application/pdf", original_filename="scan.pdf")
        assert item.category == MediaCategory.DOCUMENT

    def test_falls_back_to_other_for_unknown_type(self):
        item = self._make(content_type="application/octet-stream", original_filename="blob.bin")
        assert item.category == MediaCategory.OTHER

    def test_is_image_property(self):
        item = self._make(content_type="image/png")
        assert item.is_image is True

    def test_is_document_property(self):
        item = self._make(content_type="application/pdf", original_filename="doc.pdf")
        assert item.is_document is True

    def test_display_name_prefers_title(self):
        item = self._make()
        item.title = "Wedding Day 1952"
        assert item.display_name == "Wedding Day 1952"

    def test_display_name_falls_back_to_filename(self):
        item = self._make(original_filename="photo.jpg")
        assert item.display_name == "photo.jpg"


# ── ImageDimensions value object ───────────────────────────────────────────────

class TestImageDimensions:
    def test_aspect_ratio(self):
        d = ImageDimensions(width=1920, height=1080)
        assert abs(d.aspect_ratio - 16 / 9) < 0.001

    def test_megapixels(self):
        d = ImageDimensions(width=4000, height=3000)
        assert d.megapixels == 12.0

    def test_zero_height_no_division_error(self):
        d = ImageDimensions(width=100, height=0)
        assert d.aspect_ratio == 1.0


# ── GpsCoordinate string representation ───────────────────────────────────────

class TestGpsCoordinate:
    def test_north_east_string(self):
        coord = GpsCoordinate(latitude=51.5, longitude=0.127)
        s = str(coord)
        assert "N" in s and "E" in s

    def test_south_west_string(self):
        coord = GpsCoordinate(latitude=-33.87, longitude=-70.65)
        s = str(coord)
        assert "S" in s and "W" in s


# ── ExifData.to_dict() ─────────────────────────────────────────────────────────

class TestExifData:
    def test_to_dict_with_gps(self):
        exif = ExifData(
            gps=GpsCoordinate(latitude=40.7128, longitude=-74.0060),
            orientation=1,
        )
        d = exif.to_dict()
        assert d["gps"]["latitude"] == pytest.approx(40.7128)
        assert d["gps"]["longitude"] == pytest.approx(-74.0060)

    def test_to_dict_without_gps(self):
        exif = ExifData()
        d = exif.to_dict()
        assert d["gps"] is None


# ── File size limits ───────────────────────────────────────────────────────────

class TestFileSizeLimits:
    def test_photo_limit_is_50mb(self):
        assert MAX_FILE_SIZE[MediaCategory.PHOTO] == 50 * 1024 * 1024

    def test_video_limit_is_500mb(self):
        assert MAX_FILE_SIZE[MediaCategory.VIDEO] == 500 * 1024 * 1024

    def test_all_categories_have_limits(self):
        for cat in MediaCategory:
            assert cat in MAX_FILE_SIZE


# ── S3 key conventions ─────────────────────────────────────────────────────────

class TestS3KeyConventions:
    def _ids(self):
        return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def test_storage_key_with_person(self):
        tid, treeid, mid = self._ids()
        pid = uuid.uuid4()
        key = make_storage_key(tid, treeid, mid, "photo.jpg", person_id=pid)
        assert f"persons/{pid}" in key
        assert key.endswith("/original.jpg")

    def test_storage_key_without_person(self):
        tid, treeid, mid = self._ids()
        key = make_storage_key(tid, treeid, mid, "tree.jpg")
        assert "tree" in key
        assert "persons" not in key

    def test_storage_key_lowercases_extension(self):
        tid, treeid, mid = self._ids()
        key = make_storage_key(tid, treeid, mid, "PHOTO.JPG")
        assert key.endswith(".jpg")

    def test_storage_key_no_dot_extension_defaults_to_bin(self):
        tid, treeid, mid = self._ids()
        key = make_storage_key(tid, treeid, mid, "nodotfile")
        assert key.endswith(".bin")

    def test_variant_key_replaces_original(self):
        orig = "abc/def/original.jpg"
        variant = make_variant_key(orig, "thumb_200")
        assert variant == "abc/def/thumb_200.webp"
        assert "original" not in variant


# ── Domain exceptions ──────────────────────────────────────────────────────────

class TestMediaExceptions:
    def test_unsupported_media_type_error(self):
        exc = UnsupportedMediaTypeError("application/x-unknown")
        assert exc.code == "UNSUPPORTED_MEDIA_TYPE"
        assert "application/x-unknown" in exc.message

    def test_file_too_large_error_shows_mb(self):
        exc = FileTooLargeError(60_000_000, 50 * 1024 * 1024)
        assert "50 MB" in exc.message
        assert exc.size_bytes == 60_000_000

    def test_media_not_found_error(self):
        mid = uuid.uuid4()
        exc = MediaNotFoundError(mid)
        assert exc.code == "MEDIA_NOT_FOUND"
        assert str(mid) in exc.message

    def test_media_not_ready_error(self):
        mid = uuid.uuid4()
        exc = MediaNotReadyError(mid, "PROCESSING")
        assert "PROCESSING" in exc.message
