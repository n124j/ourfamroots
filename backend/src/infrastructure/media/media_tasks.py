"""
Celery tasks for async media processing.

Task graph per media item:

    chord(
        group(
            extract_metadata.s(media_id),     # parallel: EXIF / PDF text / duration
            generate_thumbnails.s(media_id),  # parallel: thumb_200, thumb_600, compressed
        ),
        finalize_media.s(media_id)            # runs after BOTH complete
    ).apply_async()
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import chord, group, shared_task
from celery.exceptions import SoftTimeLimitExceeded

from src.infrastructure.media.celery_app import celery_app
from src.infrastructure.media.processors import (
    build_metadata_json,
    compress_image,
    extract_exif,
    extract_pdf_text,
    generate_thumb_preview,
    generate_thumb_square,
    get_image_dimensions,
    pdf_first_page_preview,
)
from src.infrastructure.media.s3 import (
    get_s3,
    make_metadata_key,
    make_preview_key,
    make_variant_key,
)

log = logging.getLogger(__name__)

# ── Retry policy ───────────────────────────────────────────────────────────────

_RETRY_KWARGS = dict(
    max_retries=3,
    default_retry_delay=30,      # 30s, 90s, 270s (exponential back-off via countdown)
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)


# ── Helper: load MediaItem from DB ─────────────────────────────────────────────
# Import is deferred inside tasks to avoid circular imports at module load time.

def _get_media_sync(media_id: uuid.UUID):
    """Synchronous DB fetch — Celery workers run synchronously."""
    from src.infrastructure.database.session import SyncSessionFactory  # noqa: PLC0415
    from src.infrastructure.repositories.media import SyncMediaRepository  # noqa: PLC0415

    with SyncSessionFactory() as session:
        repo = SyncMediaRepository(session)
        media = repo.get(media_id)
        if media is None:
            raise ValueError(f"MediaItem {media_id} not found")
        return media


def _update_media_sync(media_id: uuid.UUID, **kwargs) -> None:
    from src.infrastructure.database.session import SyncSessionFactory  # noqa: PLC0415
    from src.infrastructure.repositories.media import SyncMediaRepository  # noqa: PLC0415

    with SyncSessionFactory() as session:
        repo = SyncMediaRepository(session)
        repo.update(media_id, **kwargs)
        session.commit()


# ── Task 1: extract_metadata ───────────────────────────────────────────────────

@celery_app.task(
    name="src.infrastructure.media.media_tasks.extract_metadata",
    bind=True,
    **_RETRY_KWARGS,
)
def extract_metadata(self, media_id: str) -> dict[str, Any]:
    """
    Download original from S3, extract:
    - EXIF (photos)
    - Text (PDFs / documents)
    - Duration (audio / video — stub)
    Uploads metadata.json to S3 and returns a result dict for finalize_media.
    """
    mid = uuid.UUID(media_id)
    log.info("extract_metadata start media_id=%s", mid)

    try:
        media = _get_media_sync(mid)
        s3 = get_s3()
        original_bytes = s3.download_bytes(media.variants.original_key)

        exif        = None
        dimensions  = None
        text        = None
        duration    = None

        if media.category.value == "PHOTO":
            exif       = extract_exif(original_bytes)
            dimensions = get_image_dimensions(original_bytes)

        elif media.category.value == "DOCUMENT" and media.content_type == "application/pdf":
            text = extract_pdf_text(original_bytes)

        # Audio/video duration extraction (requires ffprobe — stub for now)
        # elif media.category.value in ("AUDIO", "VIDEO"):
        #     duration = extract_duration(original_bytes, media.content_type)

        # Upload metadata.json
        meta_bytes = build_metadata_json(
            exif=exif,
            dimensions=dimensions,
            extracted_text=text,
            duration_seconds=duration,
        )
        meta_key = make_metadata_key(media.variants.original_key)
        s3.upload_bytes(meta_key, meta_bytes, "application/json")

        # Persist extracted fields
        update_fields: dict[str, Any] = {"variants__metadata_key": meta_key}
        if exif:
            update_fields["exif"] = exif
        if dimensions:
            update_fields["dimensions"] = dimensions
        if text is not None:
            update_fields["extracted_text"] = text
        if duration is not None:
            update_fields["duration_seconds"] = duration

        _update_media_sync(mid, **update_fields)

        log.info("extract_metadata done media_id=%s", mid)
        return {"task": "extract_metadata", "media_id": media_id, "ok": True}

    except SoftTimeLimitExceeded:
        log.warning("extract_metadata soft time limit exceeded media_id=%s", mid)
        raise
    except Exception as exc:
        log.exception("extract_metadata failed media_id=%s error=%s", mid, exc)
        raise self.retry(exc=exc)


# ── Task 2: generate_thumbnails ────────────────────────────────────────────────

@celery_app.task(
    name="src.infrastructure.media.media_tasks.generate_thumbnails",
    bind=True,
    **_RETRY_KWARGS,
)
def generate_thumbnails(self, media_id: str) -> dict[str, Any]:
    """
    For photos: generate thumb_200.webp (square), thumb_600.webp (preview),
                and compressed.webp (full-size WebP @ 85%).
    For PDFs:   generate preview.jpg (first-page render).
    Other:      no-op, returns ok immediately.
    """
    mid = uuid.UUID(media_id)
    log.info("generate_thumbnails start media_id=%s", mid)

    try:
        media = _get_media_sync(mid)
        s3 = get_s3()
        original_key = media.variants.original_key
        variant_updates: dict[str, Any] = {}

        if media.category.value == "PHOTO":
            original_bytes = s3.download_bytes(original_key)

            # 200px square crop
            thumb_200_bytes = generate_thumb_square(original_bytes, size=200)
            thumb_200_key   = make_variant_key(original_key, "thumb_200")
            s3.upload_bytes(thumb_200_key, thumb_200_bytes, "image/webp")
            variant_updates["variants__thumb_200_key"] = thumb_200_key

            # 600px longest-edge
            thumb_600_bytes = generate_thumb_preview(original_bytes, max_side=600)
            thumb_600_key   = make_variant_key(original_key, "thumb_600")
            s3.upload_bytes(thumb_600_key, thumb_600_bytes, "image/webp")
            variant_updates["variants__thumb_600_key"] = thumb_600_key

            # Full compressed WebP
            compressed_bytes = compress_image(original_bytes)
            compressed_key   = make_variant_key(original_key, "compressed")
            s3.upload_bytes(compressed_key, compressed_bytes, "image/webp")
            variant_updates["variants__compressed_key"] = compressed_key

        elif media.category.value == "DOCUMENT" and media.content_type == "application/pdf":
            original_bytes = s3.download_bytes(original_key)
            try:
                preview_bytes = pdf_first_page_preview(original_bytes)
                preview_key   = make_preview_key(original_key)
                s3.upload_bytes(preview_key, preview_bytes, "image/jpeg")
                variant_updates["variants__preview_key"] = preview_key
            except ImportError:
                log.warning(
                    "pdf2image not available — skipping PDF preview for media_id=%s", mid
                )

        if variant_updates:
            _update_media_sync(mid, **variant_updates)

        log.info("generate_thumbnails done media_id=%s", mid)
        return {"task": "generate_thumbnails", "media_id": media_id, "ok": True}

    except SoftTimeLimitExceeded:
        log.warning("generate_thumbnails soft time limit exceeded media_id=%s", mid)
        raise
    except Exception as exc:
        log.exception("generate_thumbnails failed media_id=%s error=%s", mid, exc)
        raise self.retry(exc=exc)


# ── Task 3: finalize_media ─────────────────────────────────────────────────────

@celery_app.task(
    name="src.infrastructure.media.media_tasks.finalize_media",
    bind=True,
    max_retries=2,
)
def finalize_media(self, group_results: list[dict], media_id: str) -> dict[str, Any]:
    """
    Callback task — runs after extract_metadata AND generate_thumbnails both complete.
    Sets status to READY (or FAILED if either upstream task failed).

    *group_results* is the list of return values from the chord group.
    """
    mid = uuid.UUID(media_id)
    log.info("finalize_media start media_id=%s group_results=%s", mid, group_results)

    try:
        all_ok = all(r.get("ok") for r in (group_results or []))
        new_status = "READY" if all_ok else "FAILED"
        error_msg  = None if all_ok else "One or more processing steps failed."

        _update_media_sync(
            mid,
            status=new_status,
            processing_error=error_msg,
            celery_task_id=None,
        )

        log.info("finalize_media done media_id=%s status=%s", mid, new_status)
        return {"task": "finalize_media", "media_id": media_id, "status": new_status}

    except Exception as exc:
        log.exception("finalize_media error media_id=%s", mid)
        try:
            _update_media_sync(mid, status="FAILED", processing_error=str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)


# ── Public helper: dispatch processing chord ───────────────────────────────────

def dispatch_media_processing(media_id: uuid.UUID) -> str:
    """
    Build and submit the Celery chord for a newly confirmed media item.
    Returns the chord's AsyncResult ID.
    """
    mid_str = str(media_id)
    result = chord(
        group(
            extract_metadata.s(mid_str),
            generate_thumbnails.s(mid_str),
        ),
        finalize_media.s(mid_str),
    ).apply_async()
    return result.id
