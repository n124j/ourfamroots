"""Real-database integration tests for the AI tree import endpoints
(src/api/v1/ai_tree_import.py). Same real-Postgres, direct-function-call
pattern as test_broadcast.py (requires TEST_DATABASE_URL; skipped otherwise).
S3 and the Celery task are mocked; Anthropic is never called here — see
test_vision_extraction.py / test_ai_import_tasks.py for that."""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see test_broadcast.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid, tenant_id, email, app_role="STANDARD"):
    return SimpleNamespace(id=uid, tenant_id=tenant_id, email=email,
                            given_name="Test", family_name="User", app_role=app_role)


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.paid_admin = _user(uuid.uuid4(), self.tenant_id, "paid-admin@example.com", "ADMIN")
        self.standard_user = _user(uuid.uuid4(), self.tenant_id, "standard@example.com", "STANDARD")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.paid_admin, self.standard_user):
            await s.execute(
                text("""INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                        VALUES (:id, :tenant, :email, true, true, :role, 'Test', 'User')"""),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role},
            )
        sub_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO subscriptions (id, tenant_id, name, tier)
                    VALUES (:id, :tenant, 'Premium', 'PREMIUM_INDIVIDUAL')"""),
            {"id": sub_id, "tenant": self.tenant_id},
        )
        await s.execute(
            text("""INSERT INTO subscription_members (id, subscription_id, user_id)
                    VALUES (gen_random_uuid(), :sid, :uid)"""),
            {"sid": sub_id, "uid": self.paid_admin.id},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestUploadUrl:
    @pytest.mark.asyncio
    async def test_standard_user_is_blocked(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        with pytest.raises(HTTPException) as exc:
            await require_admin_paid_feature(user=seed.standard_user, session=seed.session)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @patch("src.api.v1.ai_tree_import._make_presign_client")
    async def test_creates_pending_job(self, mock_make_presign, seed: Seed):
        from src.api.v1.ai_tree_import import request_upload_url, UploadUrlRequest

        s3 = MagicMock()
        s3.generate_presigned_post.return_value = {"url": "https://s3.example/", "fields": {}}
        mock_make_presign.return_value = s3

        result = await request_upload_url(
            UploadUrlRequest(content_type="image/jpeg", file_size_bytes=1000),
            current_user=seed.paid_admin, session=seed.session,
        )
        assert result.upload_url == "https://s3.example/"

        row = (await seed.session.execute(
            text("SELECT status FROM ai_tree_import_jobs WHERE id = :id"), {"id": uuid.UUID(result.job_id)},
        )).first()
        assert row.status == "PENDING"


class TestConfirm:
    @pytest.mark.asyncio
    @patch("src.api.v1.ai_tree_import.extract_tree_from_screenshot_task")
    @patch("src.api.v1.ai_tree_import._make_s3_client")
    @patch("src.api.v1.ai_tree_import._make_presign_client")
    async def test_dispatches_celery_task_and_sets_processing(
        self, mock_make_presign, mock_make_s3, mock_task, seed: Seed
    ):
        from src.api.v1.ai_tree_import import request_upload_url, confirm_upload, UploadUrlRequest

        presign_s3 = MagicMock()
        presign_s3.generate_presigned_post.return_value = {"url": "https://s3.example/", "fields": {}}
        mock_make_presign.return_value = presign_s3

        s3 = MagicMock()
        s3.head_object.return_value = {}
        mock_make_s3.return_value = s3
        mock_task.delay.return_value = SimpleNamespace(id="celery-task-123")

        created = await request_upload_url(
            UploadUrlRequest(content_type="image/jpeg", file_size_bytes=1000),
            current_user=seed.paid_admin, session=seed.session,
        )
        result = await confirm_upload(
            uuid.UUID(created.job_id), current_user=seed.paid_admin, session=seed.session,
        )
        assert result.status == "PROCESSING"
        mock_task.delay.assert_called_once_with(created.job_id)


class TestFinalize:
    @pytest.mark.asyncio
    @patch("src.api.v1.ai_tree_import._create_tree_from_ofr_data")
    async def test_creates_tree_from_reviewed_draft(self, mock_create_tree, seed: Seed):
        from src.api.v1.ai_tree_import import finalize_job, FinalizeRequest, FinalizePerson
        from src.api.v1.collaboration import CreatedTreeResult
        from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel
        from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork

        mock_create_tree.return_value = CreatedTreeResult(
            tree_id=uuid.uuid4(), tree_name="From Screenshot", old_to_new={},
        )

        job = AiTreeImportJobModel(
            tenant_id=seed.tenant_id, status="READY",
            screenshot_storage_key=f"tenants/{seed.tenant_id}/ai-imports/x/screenshot.jpg",
            photo_staging_prefix=f"tenants/{seed.tenant_id}/ai-imports/x/photos/",
            result_json={"persons": [], "family_groups": []},
        )
        seed.session.add(job)
        await seed.session.commit()

        with patch("src.api.v1.ai_tree_import._make_s3_client") as mock_make_s3:
            mock_make_s3.return_value = MagicMock()
            result = await finalize_job(
                job.id,
                FinalizeRequest(tree_name="From Screenshot",
                                 persons=[FinalizePerson(id="p1", display_given_name="A", display_surname="B", sex="MALE")],
                                 family_groups=[]),
                current_user=seed.paid_admin, session=seed.session,
                uow=SqlAlchemyUnitOfWork(seed.session),
            )
        assert result["tree_name"] == "From Screenshot"
        mock_create_tree.assert_called_once()

        remaining = (await seed.session.execute(
            text("SELECT COUNT(*) FROM ai_tree_import_jobs WHERE id = :id"), {"id": job.id},
        )).scalar_one()
        assert remaining == 0
