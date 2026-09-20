"""Admin, paid-tier-gated: upload a family-tree screenshot, let Claude vision
extract people/relationships/photos, review, then finalize into a new tree."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.deps import AdminPaidFeatureDep, SessionDep, UoWDep
from src.api.v1._admin_log import log_admin_action
from src.api.v1._s3 import _make_s3_client
from src.api.v1.collaboration import _create_tree_from_ofr_data
from src.infrastructure.ai_import.ai_import_tasks import extract_tree_from_screenshot_task
from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel

router = APIRouter(prefix="/admin/ai-tree-import", tags=["Admin", "AI Tree Import"])

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class UploadUrlRequest(BaseModel):
    content_type: str
    file_size_bytes: int = Field(..., gt=0)


class UploadUrlResponse(BaseModel):
    job_id: str
    upload_url: str
    upload_fields: dict[str, str]
    max_size_bytes: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    processing_error: Optional[str] = None
    persons: Optional[list[dict]] = None
    family_groups: Optional[list[dict]] = None
    photo_urls: dict[str, str] = {}


class FinalizePerson(BaseModel):
    id: str
    display_given_name: str = ""
    display_surname: str = ""
    sex: str = "UNKNOWN"


class FinalizeFamilyGroup(BaseModel):
    id: str
    union_type: str = "UNKNOWN"
    parent_ids: list[str] = []
    children: dict[str, str] = {}


class FinalizeRequest(BaseModel):
    tree_name: str = Field(..., min_length=1, max_length=200)
    tree_description: Optional[str] = None
    persons: list[FinalizePerson] = []
    family_groups: list[FinalizeFamilyGroup] = []


async def _get_job(session, job_id: uuid.UUID, tenant_id: uuid.UUID) -> AiTreeImportJobModel:
    from sqlalchemy import select
    result = await session.execute(
        select(AiTreeImportJobModel).where(
            AiTreeImportJobModel.id == job_id,
            AiTreeImportJobModel.tenant_id == tenant_id,
        )
    )
    job = result.scalars().first()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    return job


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=status.HTTP_201_CREATED,
             summary="Request a presigned upload URL for a family-tree screenshot")
async def request_upload_url(
    body: UploadUrlRequest,
    current_user: AdminPaidFeatureDep,
    session: SessionDep,
) -> UploadUrlResponse:
    from src.config import get_settings
    settings = get_settings()

    if body.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                             f"Unsupported content type: {body.content_type}")
    if body.file_size_bytes > settings.ai_import_max_screenshot_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                             f"File exceeds {settings.ai_import_max_screenshot_bytes} bytes")

    job_id = uuid.uuid4()
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[body.content_type]
    screenshot_key = f"tenants/{current_user.tenant_id}/ai-imports/{job_id}/screenshot.{ext}"
    staging_prefix = f"tenants/{current_user.tenant_id}/ai-imports/{job_id}/photos/"

    job = AiTreeImportJobModel(
        id=job_id,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        status="PENDING",
        screenshot_storage_key=screenshot_key,
        photo_staging_prefix=staging_prefix,
    )
    session.add(job)
    await session.commit()

    bucket = settings.s3_bucket or "ourfamroots-local"
    s3 = _make_s3_client(settings)
    presigned = s3.generate_presigned_post(
        Bucket=bucket,
        Key=screenshot_key,
        Fields={"Content-Type": body.content_type},
        Conditions=[
            {"Content-Type": body.content_type},
            ["content-length-range", 1, settings.ai_import_max_screenshot_bytes],
        ],
        ExpiresIn=900,
    )

    return UploadUrlResponse(
        job_id=str(job_id),
        upload_url=presigned["url"],
        upload_fields=presigned["fields"],
        max_size_bytes=settings.ai_import_max_screenshot_bytes,
    )


@router.post("/{job_id}/confirm", response_model=JobStatusResponse,
             summary="Confirm the screenshot upload and start AI extraction")
async def confirm_upload(
    job_id: uuid.UUID,
    current_user: AdminPaidFeatureDep,
    session: SessionDep,
) -> JobStatusResponse:
    from src.config import get_settings
    settings = get_settings()

    job = await _get_job(session, job_id, current_user.tenant_id)
    bucket = settings.s3_bucket or "ourfamroots-local"
    s3 = _make_s3_client(settings)
    try:
        s3.head_object(Bucket=bucket, Key=job.screenshot_storage_key)
    except Exception as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screenshot upload not found in storage") from exc

    task = extract_tree_from_screenshot_task.delay(str(job_id))
    job.status = "PROCESSING"
    job.celery_task_id = task.id
    await session.commit()

    return JobStatusResponse(job_id=str(job_id), status=job.status)


@router.get("/{job_id}", response_model=JobStatusResponse,
            summary="Poll AI extraction job status; returns the draft once READY")
async def get_job(
    job_id: uuid.UUID,
    current_user: AdminPaidFeatureDep,
    session: SessionDep,
) -> JobStatusResponse:
    from src.api.v1._s3 import presign_photo

    job = await _get_job(session, job_id, current_user.tenant_id)

    persons = None
    family_groups = None
    photo_urls: dict[str, str] = {}
    if job.status == "READY" and job.result_json:
        persons = job.result_json.get("persons", [])
        family_groups = job.result_json.get("family_groups", [])
        for p in persons:
            key = p.get("photo_staging_key")
            if key:
                photo_urls[p["id"]] = presign_photo(key)

    return JobStatusResponse(
        job_id=str(job_id),
        status=job.status,
        processing_error=job.processing_error,
        persons=persons,
        family_groups=family_groups,
        photo_urls=photo_urls,
    )


@router.post("/{job_id}/finalize", summary="Create a real tree from the reviewed draft")
async def finalize_job(
    job_id: uuid.UUID,
    body: FinalizeRequest,
    current_user: AdminPaidFeatureDep,
    session: SessionDep,
    uow: UoWDep,
) -> dict:
    from src.config import get_settings
    settings = get_settings()

    job = await _get_job(session, job_id, current_user.tenant_id)
    if job.status != "READY":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Job is {job.status}, not READY")

    staged_photo_keys = {}
    if job.result_json:
        for p in job.result_json.get("persons", []):
            key = p.get("photo_staging_key")
            if key:
                staged_photo_keys[p["id"]] = key

    bucket = settings.s3_bucket or "ourfamroots-local"
    s3 = _make_s3_client(settings)
    photos_by_person_id: dict[str, tuple[bytes, str]] = {}
    for pid, key in staged_photo_keys.items():
        if pid in {p.id for p in body.persons}:
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                photos_by_person_id[pid] = (obj["Body"].read(), "jpg")
            except Exception:
                pass

    result = await _create_tree_from_ofr_data(
        uow, current_user, body.tree_name, body.tree_description,
        [p.model_dump() for p in body.persons],
        [fg.model_dump() for fg in body.family_groups],
        photos_by_person_id,
    )

    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email,
        "AI_TREE_IMPORT", result.tree_name,
    )
    await session.commit()

    s3.delete_object(Bucket=bucket, Key=job.screenshot_storage_key)
    for key in staged_photo_keys.values():
        try:
            s3.delete_object(Bucket=bucket, Key=key)
        except Exception:
            pass
    await session.delete(job)
    await session.commit()

    return {"tree_id": str(result.tree_id), "tree_name": result.tree_name}
