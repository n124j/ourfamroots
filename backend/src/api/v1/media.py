"""Media API — upload URLs, confirmation, retrieval, metadata, delete."""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, get_db_session, get_media_service
from src.application.media.service import MediaApplicationService
from src.domain.media.exceptions import (
    FileTooLargeError,
    MediaNotFoundError,
    MediaNotReadyError,
    UnsupportedMediaTypeError,
)

router = APIRouter(prefix="/media", tags=["media"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class RequestUploadUrlBody(BaseModel):
    tree_id: uuid.UUID
    person_id: Optional[uuid.UUID] = None
    original_filename: str = Field(..., min_length=1, max_length=512)
    content_type: str
    file_size_bytes: int = Field(..., gt=0)


class PresignedTicketResponse(BaseModel):
    media_id: uuid.UUID
    upload_url: str
    upload_fields: dict[str, str]
    storage_key: str
    expires_in_seconds: int
    max_size_bytes: int


class MediaStatusResponse(BaseModel):
    media_id: uuid.UUID
    status: str
    category: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    celery_task_id: Optional[str] = None
    processing_error: Optional[str] = None

    # Variants (present once READY)
    thumb_200_url: Optional[str] = None
    thumb_600_url: Optional[str] = None
    compressed_url: Optional[str] = None
    preview_url: Optional[str] = None

    # Metadata
    title: Optional[str] = None
    description: Optional[str] = None
    date_circa: Optional[str] = None
    year: Optional[int] = None
    tags: list[str] = []
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    duration_seconds: Optional[float] = None
    created_at: str = ""


class UpdateMetadataBody(BaseModel):
    title: Optional[str]       = Field(None, max_length=512)
    description: Optional[str] = Field(None, max_length=4096)
    date_circa: Optional[str]  = Field(None, max_length=64)
    year: Optional[int]        = Field(None, ge=1, le=9999)
    tags: Optional[list[str]]  = None


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int = 3600


# ── Exception → HTTP mapping ───────────────────────────────────────────────────

def _handle_media_exception(exc: Exception) -> None:
    if isinstance(exc, UnsupportedMediaTypeError):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=exc.message)
    if isinstance(exc, FileTooLargeError):
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=exc.message)
    if isinstance(exc, MediaNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, MediaNotReadyError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    raise exc


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/upload-url",
    response_model=PresignedTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a presigned S3 upload URL",
)
async def request_upload_url(
    body: RequestUploadUrlBody,
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    """
    Step 1 of the upload flow.
    Returns a presigned POST URL + fields; the client uploads directly to S3,
    then calls `/media/{id}/confirm`.
    """
    try:
        ticket = await svc.request_upload_url(
            tree_id=body.tree_id,
            tenant_id=current_user.tenant_id,
            uploaded_by_id=current_user.id,
            person_id=body.person_id,
            original_filename=body.original_filename,
            content_type=body.content_type,
            file_size_bytes=body.file_size_bytes,
        )
    except Exception as exc:
        _handle_media_exception(exc)

    return PresignedTicketResponse(
        media_id=ticket.media_id,
        upload_url=ticket.upload_url,
        upload_fields=ticket.upload_fields,
        storage_key=ticket.storage_key,
        expires_in_seconds=ticket.expires_in_seconds,
        max_size_bytes=ticket.max_size_bytes,
    )


@router.post(
    "/{media_id}/confirm",
    response_model=MediaStatusResponse,
    summary="Confirm S3 upload and trigger processing",
)
async def confirm_upload(
    media_id: Annotated[uuid.UUID, Path()],
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    """
    Step 3 of the upload flow (step 2 is the direct S3 upload).
    Verifies the object exists in S3, transitions to CONFIRMED, and
    dispatches the Celery processing chord.
    """
    try:
        media = await svc.confirm_upload(media_id, current_user.tenant_id)
    except Exception as exc:
        _handle_media_exception(exc)

    return MediaStatusResponse(
        media_id=media.id,
        status=media.status.value,
        category=media.category.value,
        original_filename=media.original_filename,
        content_type=media.content_type,
        file_size_bytes=media.file_size_bytes,
        celery_task_id=media.celery_task_id,
        created_at=media.created_at.isoformat(),
    )


@router.get(
    "/{media_id}",
    response_model=MediaStatusResponse,
    summary="Get media item status and URLs",
)
async def get_media(
    media_id: Annotated[uuid.UUID, Path()],
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    """
    Polling endpoint — frontend polls until status is READY or FAILED.
    When READY, variant URLs are generated (presigned GET).
    """
    try:
        media = await svc.get_media(media_id, current_user.tenant_id)
    except Exception as exc:
        _handle_media_exception(exc)

    # Build variant URLs for READY items
    thumb_200_url  = None
    thumb_600_url  = None
    compressed_url = None
    preview_url    = None

    from src.domain.media.entities import ProcessingStatus  # noqa: PLC0415
    if media.status == ProcessingStatus.READY:
        s3 = svc._s3
        if media.variants.thumb_200_key:
            thumb_200_url  = s3.presigned_download_url(media.variants.thumb_200_key)
        if media.variants.thumb_600_key:
            thumb_600_url  = s3.presigned_download_url(media.variants.thumb_600_key)
        if media.variants.compressed_key:
            compressed_url = s3.presigned_download_url(media.variants.compressed_key)
        if media.variants.preview_key:
            preview_url    = s3.presigned_download_url(media.variants.preview_key)

    return MediaStatusResponse(
        media_id=media.id,
        status=media.status.value,
        category=media.category.value,
        original_filename=media.original_filename,
        content_type=media.content_type,
        file_size_bytes=media.file_size_bytes,
        celery_task_id=media.celery_task_id,
        processing_error=media.processing_error,
        thumb_200_url=thumb_200_url,
        thumb_600_url=thumb_600_url,
        compressed_url=compressed_url,
        preview_url=preview_url,
        title=media.title,
        description=media.description,
        date_circa=media.date_circa,
        year=media.year,
        tags=media.tags,
        image_width=media.dimensions.width  if media.dimensions else None,
        image_height=media.dimensions.height if media.dimensions else None,
        duration_seconds=media.duration_seconds,
        created_at=media.created_at.isoformat(),
    )


@router.patch(
    "/{media_id}",
    response_model=MediaStatusResponse,
    summary="Update user-editable media metadata",
)
async def update_metadata(
    media_id: Annotated[uuid.UUID, Path()],
    body: UpdateMetadataBody,
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    try:
        media = await svc.update_metadata(
            media_id=media_id,
            tenant_id=current_user.tenant_id,
            title=body.title,
            description=body.description,
            date_circa=body.date_circa,
            year=body.year,
            tags=body.tags,
        )
    except Exception as exc:
        _handle_media_exception(exc)

    return MediaStatusResponse(
        media_id=media.id,
        status=media.status.value,
        category=media.category.value,
        original_filename=media.original_filename,
        content_type=media.content_type,
        file_size_bytes=media.file_size_bytes,
        title=media.title,
        description=media.description,
        date_circa=media.date_circa,
        year=media.year,
        tags=media.tags,
        created_at=media.created_at.isoformat(),
    )


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete a media item (and its S3 variants)",
)
async def delete_media(
    media_id: Annotated[uuid.UUID, Path()],
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    try:
        await svc.delete_media(media_id, current_user.tenant_id)
    except Exception as exc:
        _handle_media_exception(exc)


@router.get(
    "/{media_id}/download",
    response_model=DownloadUrlResponse,
    summary="Get a time-limited download URL for a variant",
)
async def get_download_url(
    media_id: Annotated[uuid.UUID, Path()],
    variant: str = Query(default="original", pattern="^(original|compressed|thumb_200|thumb_600|preview)$"),
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    try:
        url = await svc.get_download_url(media_id, current_user.tenant_id, variant)
    except Exception as exc:
        _handle_media_exception(exc)

    return DownloadUrlResponse(url=url)


# ── Tree-scoped gallery endpoint ───────────────────────────────────────────────

persons_media_router = APIRouter(
    prefix="/trees/{tree_id}/persons/{person_id}/media",
    tags=["media"],
)


class MediaListResponse(BaseModel):
    items: list[MediaStatusResponse]
    total: int


@persons_media_router.get(
    "",
    response_model=MediaListResponse,
    summary="List all media attached to a person",
)
async def list_person_media(
    tree_id: Annotated[uuid.UUID, Path()],
    person_id: Annotated[uuid.UUID, Path()],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    svc: MediaApplicationService = Depends(get_media_service),
):
    items = await svc._repo.list_for_person(tree_id, person_id, limit=limit, offset=offset)
    return MediaListResponse(
        items=[
            MediaStatusResponse(
                media_id=m.id,
                status=m.status.value,
                category=m.category.value,
                original_filename=m.original_filename,
                content_type=m.content_type,
                file_size_bytes=m.file_size_bytes,
                title=m.title,
                description=m.description,
                date_circa=m.date_circa,
                year=m.year,
                tags=m.tags,
                image_width=m.dimensions.width  if m.dimensions else None,
                image_height=m.dimensions.height if m.dimensions else None,
                duration_seconds=m.duration_seconds,
                created_at=m.created_at.isoformat(),
            )
            for m in items
        ],
        total=len(items),
    )
