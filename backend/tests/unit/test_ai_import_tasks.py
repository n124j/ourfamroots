"""Unit tests for extract_tree_from_screenshot_task, with DB/S3/vision mocked."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ai_import.vision_extraction import (
    ExtractedFamilyGroup,
    ExtractedPerson,
    ExtractedTreeDraft,
    VisionExtractionError,
)


@pytest.fixture
def job_id() -> str:
    return str(uuid.uuid4())


def _mock_job_row():
    row = MagicMock()
    row.tenant_id = uuid.uuid4()
    row.screenshot_storage_key = "tenants/x/ai-imports/y/screenshot.jpg"
    row.photo_staging_prefix = "tenants/x/ai-imports/y/photos/"
    row.status = "PROCESSING"
    row.result_json = None
    row.processing_error = None
    return row


@patch("src.infrastructure.ai_import.ai_import_tasks._get_sync_engine")
@patch("src.infrastructure.ai_import.ai_import_tasks._make_s3_service")
@patch("src.infrastructure.ai_import.ai_import_tasks.extract_tree_from_image")
def test_task_writes_ready_result_with_staged_photos(
    mock_extract, mock_make_s3, mock_engine
) -> None:
    from src.infrastructure.ai_import.ai_import_tasks import extract_tree_from_screenshot_task

    job_row = _mock_job_row()
    session_ctx = MagicMock()
    session_ctx.get.return_value = job_row
    mock_engine.return_value = MagicMock()

    with patch("src.infrastructure.ai_import.ai_import_tasks.Session") as mock_session_cls:
        mock_session_cls.return_value.__enter__.return_value = session_ctx

        s3 = MagicMock()
        s3.download_bytes.return_value = b"fake-screenshot-bytes"
        mock_make_s3.return_value = s3

        mock_extract.return_value = ExtractedTreeDraft(
            persons=[
                ExtractedPerson(id="jane", display_given_name="Jane", display_surname="Doe",
                                 sex="FEMALE", bbox=[0.0, 0.0, 0.1, 0.1]),
                ExtractedPerson(id="kid", display_given_name="Sam", display_surname="Doe", sex="UNKNOWN"),
            ],
            family_groups=[
                ExtractedFamilyGroup(id="fg1", union_type="MARRIAGE", parent_ids=["jane"],
                                      children={"kid": "BIOLOGICAL"}),
            ],
        )

        with patch("src.infrastructure.ai_import.ai_import_tasks.crop_person_photo", return_value=b"cropped"):
            result = extract_tree_from_screenshot_task(str(uuid.uuid4()))

    assert result["status"] == "READY"
    assert job_row.status == "READY"
    assert job_row.result_json["persons"][0]["photo_staging_key"] == \
        "tenants/x/ai-imports/y/photos/jane.jpg"
    assert "photo_staging_key" not in job_row.result_json["persons"][1]
    s3.upload_bytes.assert_called_once()
    session_ctx.commit.assert_called()


@patch("src.infrastructure.ai_import.ai_import_tasks._get_sync_engine")
@patch("src.infrastructure.ai_import.ai_import_tasks._make_s3_service")
@patch("src.infrastructure.ai_import.ai_import_tasks.extract_tree_from_image")
def test_task_marks_job_failed_on_vision_error(
    mock_extract, mock_make_s3, mock_engine
) -> None:
    from src.infrastructure.ai_import.ai_import_tasks import extract_tree_from_screenshot_task

    job_row = _mock_job_row()
    session_ctx = MagicMock()
    session_ctx.get.return_value = job_row
    mock_engine.return_value = MagicMock()

    with patch("src.infrastructure.ai_import.ai_import_tasks.Session") as mock_session_cls:
        mock_session_cls.return_value.__enter__.return_value = session_ctx
        s3 = MagicMock()
        s3.download_bytes.return_value = b"fake-screenshot-bytes"
        mock_make_s3.return_value = s3
        mock_extract.side_effect = VisionExtractionError("boom")

        result = extract_tree_from_screenshot_task(str(uuid.uuid4()))

    assert result["status"] == "FAILED"
    assert job_row.status == "FAILED"
    assert "boom" in job_row.processing_error
