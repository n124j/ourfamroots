"""Celery task: run the full AI screenshot-to-tree extraction pipeline.

Follows the sync-engine-inline pattern already used by broadcast_tasks.py and
subscription_tasks.py — NOT media_tasks.py's SyncSessionFactory/get_s3(),
which are dead imports nothing in this codebase ever constructs.
"""
from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import get_settings
from src.infrastructure.ai_import.photo_cropping import crop_person_photo
from src.infrastructure.ai_import.vision_extraction import (
    VisionExtractionError,
    extract_tree_from_image,
)
from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel
from src.infrastructure.media.celery_app import celery_app

log = logging.getLogger(__name__)


def _get_sync_engine():
    url = os.environ.get(
        "SYNC_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/ourfamroots",
    )
    return create_engine(url, pool_pre_ping=True)


def _make_s3_service():
    from src.infrastructure.media.s3 import S3Service

    settings = get_settings()
    return S3Service(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id or None,
        secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.s3_endpoint_url or None,
        public_url=settings.s3_public_url or None,
    )


@celery_app.task(
    name="src.infrastructure.ai_import.ai_import_tasks.extract_tree_from_screenshot_task",
    soft_time_limit=180,
    time_limit=240,
)
def extract_tree_from_screenshot_task(job_id: str) -> dict:
    engine = _get_sync_engine()
    with Session(engine) as session:
        job = session.get(AiTreeImportJobModel, uuid.UUID(job_id))
        if job is None:
            log.error("extract_tree_from_screenshot_task: job %s not found", job_id)
            return {"status": "FAILED", "error": "job not found"}

        try:
            s3 = _make_s3_service()
            screenshot_bytes = s3.download_bytes(job.screenshot_storage_key)

            settings = get_settings()
            media_type = "image/png" if job.screenshot_storage_key.lower().endswith(".png") else "image/jpeg"
            draft = extract_tree_from_image(
                screenshot_bytes, media_type, settings.anthropic_api_key, settings.ai_import_model,
            )

            persons_out = []
            for person in draft.persons:
                entry = person.model_dump(exclude={"bbox"})
                if person.bbox is not None:
                    cropped = crop_person_photo(screenshot_bytes, person.bbox)
                    staging_key = f"{job.photo_staging_prefix}{person.id}.jpg"
                    s3.upload_bytes(staging_key, cropped, "image/jpeg")
                    entry["photo_staging_key"] = staging_key
                persons_out.append(entry)

            job.result_json = {
                "persons": persons_out,
                "family_groups": [fg.model_dump() for fg in draft.family_groups],
            }
            job.status = "READY"
            job.processing_error = None
            session.commit()
            return {"status": "READY", "person_count": len(persons_out)}

        except VisionExtractionError as exc:
            job.status = "FAILED"
            job.processing_error = str(exc)
            session.commit()
            return {"status": "FAILED", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — any other failure still marks the job FAILED
            log.exception("extract_tree_from_screenshot_task: unexpected failure for job %s", job_id)
            job.status = "FAILED"
            job.processing_error = f"Unexpected error: {exc}"
            session.commit()
            return {"status": "FAILED", "error": str(exc)}
