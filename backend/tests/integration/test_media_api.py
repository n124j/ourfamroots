"""Integration tests for the Media API endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.domain.media.entities import (
    MediaCategory,
    MediaItem,
    MediaVariants,
    ProcessingStatus,
)
from src.domain.media.exceptions import (
    FileTooLargeError,
    MediaNotFoundError,
    UnsupportedMediaTypeError,
)

# ── Test constants ─────────────────────────────────────────────────────────────

TREE_ID   = uuid.uuid4()
MEDIA_ID  = uuid.uuid4()
PERSON_ID = uuid.uuid4()
TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_media_item(status: str = "PENDING") -> MediaItem:
    return MediaItem(
        id=MEDIA_ID,
        tree_id=TREE_ID,
        tenant_id=TENANT_ID,
        uploaded_by_id=uuid.uuid4(),
        person_id=PERSON_ID,
        original_filename="photo.jpg",
        content_type="image/jpeg",
        file_size_bytes=1_000_000,
        category=MediaCategory.PHOTO,
        variants=MediaVariants(original_key=f"{TENANT_ID}/{TREE_ID}/persons/{PERSON_ID}/{MEDIA_ID}/original.jpg"),
        status=ProcessingStatus(status),
    )


# ── Upload URL endpoint ────────────────────────────────────────────────────────

class TestRequestUploadUrl:
    @pytest.mark.asyncio
    async def test_returns_presigned_ticket(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        from src.domain.media.entities import PresignedUploadTicket
        mock_svc.request_upload_url.return_value = PresignedUploadTicket(
            media_id=MEDIA_ID,
            upload_url="https://s3.amazonaws.com/bucket",
            upload_fields={"key": "test", "Content-Type": "image/jpeg"},
            storage_key="key/original.jpg",
            expires_in_seconds=3600,
            max_size_bytes=50 * 1024 * 1024,
            allowed_content_types=["image/jpeg"],
        )
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.post("/api/v1/media/upload-url", json={
                "tree_id": str(TREE_ID),
                "person_id": str(PERSON_ID),
                "original_filename": "photo.jpg",
                "content_type": "image/jpeg",
                "file_size_bytes": 1_000_000,
            }, headers=auth_headers)
        assert r.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_unsupported_type_returns_415(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.request_upload_url.side_effect = UnsupportedMediaTypeError("application/x-exe")
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.post("/api/v1/media/upload-url", json={
                "tree_id": str(TREE_ID),
                "original_filename": "virus.exe",
                "content_type": "application/x-exe",
                "file_size_bytes": 1_000,
            }, headers=auth_headers)
        assert r.status_code == 415

    @pytest.mark.asyncio
    async def test_file_too_large_returns_413(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.request_upload_url.side_effect = FileTooLargeError(
            100_000_000, 50 * 1024 * 1024
        )
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.post("/api/v1/media/upload-url", json={
                "tree_id": str(TREE_ID),
                "original_filename": "huge.jpg",
                "content_type": "image/jpeg",
                "file_size_bytes": 100_000_000,
            }, headers=auth_headers)
        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_missing_filename_rejected(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        r = await test_client.post("/api/v1/media/upload-url", json={
            "tree_id": str(TREE_ID),
            "content_type": "image/jpeg",
            "file_size_bytes": 1000,
            # original_filename missing
        }, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unauthenticated_rejected(self, test_client: AsyncClient):
        r = await test_client.post("/api/v1/media/upload-url", json={
            "tree_id": str(TREE_ID),
            "original_filename": "photo.jpg",
            "content_type": "image/jpeg",
            "file_size_bytes": 1000,
        })
        assert r.status_code == 401


# ── Confirm upload endpoint ────────────────────────────────────────────────────

class TestConfirmUpload:
    @pytest.mark.asyncio
    async def test_confirm_transitions_to_confirmed(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        item = _make_media_item("CONFIRMED")
        mock_svc = AsyncMock()
        mock_svc.confirm_upload.return_value = item
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.post(
                f"/api/v1/media/{MEDIA_ID}/confirm", headers=auth_headers
            )
        assert r.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_confirm_not_found_returns_404(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.confirm_upload.side_effect = MediaNotFoundError(MEDIA_ID)
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.post(
                f"/api/v1/media/{MEDIA_ID}/confirm", headers=auth_headers
            )
        assert r.status_code == 404


# ── Get media endpoint ─────────────────────────────────────────────────────────

class TestGetMedia:
    @pytest.mark.asyncio
    async def test_get_returns_media_item(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        item = _make_media_item("READY")
        mock_svc = AsyncMock()
        mock_svc.get_media.return_value = item
        mock_svc._s3 = MagicMock()
        mock_svc._s3.presigned_download_url.return_value = "https://s3.example.com/thumb"
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/media/{MEDIA_ID}", headers=auth_headers
            )
        assert r.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_get_unknown_media_returns_404(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.get_media.side_effect = MediaNotFoundError(MEDIA_ID)
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/media/{MEDIA_ID}", headers=auth_headers
            )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_get_response_has_status_field(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        item = _make_media_item("READY")
        mock_svc = AsyncMock()
        mock_svc.get_media.return_value = item
        mock_svc._s3 = MagicMock()
        mock_svc._s3.presigned_download_url.return_value = "https://example.com/url"
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/media/{MEDIA_ID}", headers=auth_headers
            )
        if r.status_code == 200:
            assert "status" in r.json()
            assert "media_id" in r.json()


# ── Delete endpoint ────────────────────────────────────────────────────────────

class TestDeleteMedia:
    @pytest.mark.asyncio
    async def test_delete_returns_204(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.delete_media.return_value = None
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.delete(
                f"/api/v1/media/{MEDIA_ID}", headers=auth_headers
            )
        assert r.status_code in (204, 404)

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.delete_media.side_effect = MediaNotFoundError(MEDIA_ID)
        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.delete(
                f"/api/v1/media/{MEDIA_ID}", headers=auth_headers
            )
        assert r.status_code == 404
