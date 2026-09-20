"""Unit tests for the AiTreeImportJobModel ORM mapping."""
from __future__ import annotations

import uuid

from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel


def test_model_maps_expected_columns() -> None:
    job = AiTreeImportJobModel(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        status="PENDING",
        screenshot_storage_key="tenants/x/ai-imports/y/screenshot.jpg",
        photo_staging_prefix="tenants/x/ai-imports/y/photos/",
    )
    assert job.status == "PENDING"
    assert job.celery_task_id is None
    assert job.result_json is None
    assert job.processing_error is None
    assert job.__tablename__ == "ai_tree_import_jobs"
