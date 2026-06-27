"""Media application service — orchestrates presigned URL issuance, confirmation, retrieval."""
from __future__ import annotations

import uuid
from typing import Optional

from src.domain.media.entities import (
    MAX_FILE_SIZE,
    MIME_CATEGORY,
    MediaCategory,
    MediaItem,
    PresignedUploadTicket,
    ProcessingStatus,
)
from src.domain.media.exceptions import (
    FileTooLargeError,
    MediaNotFoundError,
    MediaNotReadyError,
    UnsupportedMediaTypeError,
)
from src.infrastructure.media.s3 import S3Service, make_storage_key
from src.infrastructure.repositories.media import MediaRepository

PRESIGN_EXPIRES = 3600        # 1 hour
DOWNLOAD_EXPIRES = 3600       # 1 hour for download URLs


class MediaApplicationService:
    def __init__(
        self,
        repo: MediaRepository,
        s3: S3Service,
        cdn_base: Optional[str] = None,
    ) -> None:
        self._repo    = repo
        self._s3      = s3
        self._cdn     = cdn_base

    # ── Request upload URL ────────────────────────────────────────────────────

    async def request_upload_url(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        uploaded_by_id: uuid.UUID,
        person_id: Optional[uuid.UUID],
        original_filename: str,
        content_type: str,
        file_size_bytes: int,
    ) -> PresignedUploadTicket:
        # Validate content type
        if content_type not in MIME_CATEGORY:
            raise UnsupportedMediaTypeError(content_type)

        category = MIME_CATEGORY[content_type]
        max_bytes = MAX_FILE_SIZE[category]

        # Validate file size
        if file_size_bytes > max_bytes:
            raise FileTooLargeError(file_size_bytes, max_bytes)

        # Create domain entity (PENDING)
        media_id = uuid.uuid4()
        storage_key = make_storage_key(
            tenant_id=tenant_id,
            tree_id=tree_id,
            media_id=media_id,
            filename=original_filename,
            person_id=person_id,
        )

        media = MediaItem.create(
            tree_id=tree_id,
            tenant_id=tenant_id,
            uploaded_by_id=uploaded_by_id,
            person_id=person_id,
            original_filename=original_filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            storage_key=storage_key,
        )
        # Override auto-generated UUID so storage key matches
        media.id = media_id

        await self._repo.add(media)

        # Generate presigned POST (enforces Content-Length-Range at S3 level)
        presigned = self._s3.presigned_post(
            key=storage_key,
            content_type=content_type,
            expires_in=PRESIGN_EXPIRES,
            max_size_bytes=max_bytes,
        )

        return PresignedUploadTicket(
            media_id=media_id,
            upload_url=presigned["url"],
            upload_fields=presigned["fields"],
            storage_key=storage_key,
            expires_in_seconds=PRESIGN_EXPIRES,
            max_size_bytes=max_bytes,
            allowed_content_types=[content_type],
        )

    # ── Confirm upload ─────────────────────────────────────────────────────────

    async def confirm_upload(
        self,
        media_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> MediaItem:
        """
        Client calls this after successfully uploading to S3.
        Validates the file actually exists in S3, updates status to CONFIRMED,
        and dispatches the Celery processing chord.
        """
        media = await self._repo.get(media_id)
        if not media or media.tenant_id != tenant_id:
            raise MediaNotFoundError(media_id)

        # Verify S3 object is present
        if not self._s3.object_exists(media.variants.original_key):
            raise MediaNotFoundError(media_id)  # upload never completed

        # Dispatch async processing
        from src.infrastructure.media.media_tasks import dispatch_media_processing  # noqa: PLC0415
        task_id = dispatch_media_processing(media_id)

        await self._repo.update(
            media_id,
            status=ProcessingStatus.CONFIRMED.value,
            celery_task_id=task_id,
        )
        media.status = ProcessingStatus.CONFIRMED
        media.celery_task_id = task_id
        return media

    # ── Get media item ─────────────────────────────────────────────────────────

    async def get_media(
        self,
        media_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> MediaItem:
        media = await self._repo.get(media_id)
        if not media or media.tenant_id != tenant_id:
            raise MediaNotFoundError(media_id)
        return media

    # ── Get download URL ───────────────────────────────────────────────────────

    async def get_download_url(
        self,
        media_id: uuid.UUID,
        tenant_id: uuid.UUID,
        variant: str = "original",  # "original" | "compressed" | "thumb_200" | "thumb_600" | "preview"
    ) -> str:
        media = await self._repo.get(media_id)
        if not media or media.tenant_id != tenant_id:
            raise MediaNotFoundError(media_id)

        if media.status not in (ProcessingStatus.READY, ProcessingStatus.FAILED):
            if variant != "original":
                raise MediaNotReadyError(media_id, media.status.value)

        variants = media.variants
        key_map = {
            "original":   variants.original_key,
            "compressed": variants.compressed_key,
            "thumb_200":  variants.thumb_200_key,
            "thumb_600":  variants.thumb_600_key,
            "preview":    variants.preview_key,
        }
        key = key_map.get(variant)
        if not key:
            # Fall back to original if variant not available
            key = variants.original_key

        return self._s3.presigned_download_url(
            key=key,
            expires_in=DOWNLOAD_EXPIRES,
            filename=media.original_filename if variant == "original" else None,
        )

    # ── Update metadata ────────────────────────────────────────────────────────

    async def update_metadata(
        self,
        media_id: uuid.UUID,
        tenant_id: uuid.UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        date_circa: Optional[str] = None,
        year: Optional[int] = None,
        tags: Optional[list[str]] = None,
    ) -> MediaItem:
        media = await self._repo.get(media_id)
        if not media or media.tenant_id != tenant_id:
            raise MediaNotFoundError(media_id)

        updates: dict = {}
        if title       is not None: updates["title"]       = title
        if description is not None: updates["description"] = description
        if date_circa  is not None: updates["date_circa"]  = date_circa
        if year        is not None: updates["year"]        = year
        if tags        is not None: updates["tags"]        = tags

        if updates:
            await self._repo.update(media_id, **updates)

        return await self._repo.get(media_id)  # type: ignore[return-value]

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_media(
        self,
        media_id: uuid.UUID,
        tenant_id: uuid.UUID,
        delete_from_s3: bool = True,
    ) -> None:
        media = await self._repo.get(media_id)
        if not media or media.tenant_id != tenant_id:
            raise MediaNotFoundError(media_id)

        if delete_from_s3:
            # Delete all variants under the common prefix
            prefix = media.variants.original_key.rsplit("/original.", 1)[0] + "/"
            try:
                self._s3.delete_prefix(prefix)
            except Exception:
                pass  # log and continue — DB record still soft-deleted

        await self._repo.soft_delete(media_id)
