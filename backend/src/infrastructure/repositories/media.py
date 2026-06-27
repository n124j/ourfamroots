"""Async and sync repositories for MediaItem."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.domain.media.entities import (
    ExifData,
    GpsCoordinate,
    ImageDimensions,
    MediaCategory,
    MediaItem,
    MediaVariants,
    ProcessingStatus,
)
from src.infrastructure.database.models.media import MediaModel


# ── Mapping helpers ────────────────────────────────────────────────────────────

def _model_to_entity(m: MediaModel) -> MediaItem:
    exif = None
    if m.exif_data:
        from src.infrastructure.media.processors import _parse_exif_datetime  # noqa: PLC0415
        raw = m.exif_data
        gps_raw = raw.get("gps")
        gps = (
            GpsCoordinate(latitude=gps_raw["latitude"], longitude=gps_raw["longitude"])
            if gps_raw else None
        )
        exif = ExifData(
            date_taken=_parse_exif_datetime(raw.get("date_taken") or ""),
            camera_make=raw.get("camera_make"),
            camera_model=raw.get("camera_model"),
            lens_model=raw.get("lens_model"),
            focal_length_mm=raw.get("focal_length_mm"),
            aperture=raw.get("aperture"),
            shutter_speed=raw.get("shutter_speed"),
            iso=raw.get("iso"),
            flash_fired=raw.get("flash_fired"),
            gps=gps,
            orientation=raw.get("orientation", 1),
        )

    dims = (
        ImageDimensions(width=m.image_width, height=m.image_height)
        if m.image_width and m.image_height else None
    )

    return MediaItem(
        id=m.id,
        tree_id=m.tree_id,
        tenant_id=m.tenant_id,
        uploaded_by_id=m.uploaded_by_id,
        person_id=m.person_id,
        original_filename=m.original_filename,
        content_type=m.content_type,
        file_size_bytes=m.file_size_bytes,
        category=MediaCategory(m.category),
        variants=MediaVariants(
            original_key=m.original_key,
            compressed_key=m.compressed_key,
            thumb_200_key=m.thumb_200_key,
            thumb_600_key=m.thumb_600_key,
            preview_key=m.preview_key,
            metadata_key=m.metadata_key,
        ),
        status=ProcessingStatus(m.status),
        celery_task_id=m.celery_task_id,
        processing_error=m.processing_error,
        dimensions=dims,
        exif=exif,
        extracted_text=m.extracted_text,
        duration_seconds=m.duration_seconds,
        title=m.title,
        description=m.description,
        date_circa=m.date_circa,
        year=m.year,
        tags=m.tags or [],
        created_at=m.created_at,
        updated_at=m.updated_at,
        is_deleted=m.is_deleted,
    )


def _apply_kwargs_to_model(model: MediaModel, **kwargs: Any) -> None:
    """Apply flat keyword updates; handles nested 'variants__*' keys."""
    for key, value in kwargs.items():
        if key.startswith("variants__"):
            col = key[len("variants__"):]
            setattr(model, col, value)
        elif isinstance(value, ExifData):
            model.exif_data = value.to_dict()
        elif isinstance(value, ImageDimensions):
            model.image_width  = value.width
            model.image_height = value.height
        else:
            setattr(model, key, value)
    model.updated_at = datetime.now(timezone.utc)


# ── Async repository (FastAPI request handlers) ────────────────────────────────

class MediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: MediaItem) -> None:
        model = MediaModel(
            id=item.id,
            tree_id=item.tree_id,
            tenant_id=item.tenant_id,
            uploaded_by_id=item.uploaded_by_id,
            person_id=item.person_id,
            original_filename=item.original_filename,
            content_type=item.content_type,
            file_size_bytes=item.file_size_bytes,
            category=item.category.value,
            status=item.status.value,
            original_key=item.variants.original_key,
            tags=item.tags,
        )
        self._session.add(model)

    async def get(self, media_id: uuid.UUID) -> Optional[MediaItem]:
        result = await self._session.get(MediaModel, media_id)
        return _model_to_entity(result) if result and not result.is_deleted else None

    async def list_for_person(
        self,
        tree_id: uuid.UUID,
        person_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[MediaItem]:
        stmt = (
            select(MediaModel)
            .where(
                MediaModel.tree_id == tree_id,
                MediaModel.person_id == person_id,
                MediaModel.is_deleted.is_(False),
            )
            .order_by(MediaModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.scalars(stmt)).all()
        return [_model_to_entity(r) for r in rows]

    async def list_for_tree(
        self,
        tree_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[MediaItem]:
        stmt = (
            select(MediaModel)
            .where(
                MediaModel.tree_id == tree_id,
                MediaModel.is_deleted.is_(False),
            )
            .order_by(MediaModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.scalars(stmt)).all()
        return [_model_to_entity(r) for r in rows]

    async def update(self, media_id: uuid.UUID, **kwargs: Any) -> None:
        result = await self._session.get(MediaModel, media_id)
        if result:
            _apply_kwargs_to_model(result, **kwargs)

    async def soft_delete(self, media_id: uuid.UUID) -> None:
        result = await self._session.get(MediaModel, media_id)
        if result:
            result.is_deleted = True
            result.updated_at = datetime.now(timezone.utc)


# ── Sync repository (Celery workers) ──────────────────────────────────────────

class SyncMediaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, media_id: uuid.UUID) -> Optional[MediaItem]:
        result = self._session.get(MediaModel, media_id)
        return _model_to_entity(result) if result and not result.is_deleted else None

    def update(self, media_id: uuid.UUID, **kwargs: Any) -> None:
        result = self._session.get(MediaModel, media_id)
        if result:
            _apply_kwargs_to_model(result, **kwargs)
