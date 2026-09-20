"""Real-database integration test pinning import_tree_zip's tree-creation
behavior before extracting a shared helper in Task 7, so the refactor is
provably behavior-preserving. Same pattern as test_broadcast.py (requires
TEST_DATABASE_URL; skipped otherwise)."""
from __future__ import annotations

import io
import json
import os
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import UploadFile
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


@pytest_asyncio.fixture
async def seeded_user(session: AsyncSession):
    tenant_id = uuid.uuid4()
    user = SimpleNamespace(
        id=uuid.uuid4(), tenant_id=tenant_id, email="importer@example.com",
        given_name="Import", family_name="Er", app_role="STANDARD",
    )
    await session.execute(
        text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
        {"id": tenant_id, "slug": f"test-{tenant_id.hex[:12]}"},
    )
    await session.execute(
        text("""INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                VALUES (:id, :tenant, :email, true, true, 'STANDARD', 'Import', 'Er')"""),
        {"id": user.id, "tenant": tenant_id, "email": user.email},
    )
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_import_zip_creates_tree_persons_and_family_groups(session: AsyncSession, seeded_user) -> None:
    from src.api.v1.collaboration import import_tree_zip
    from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork

    payload = {
        "ofr_version": "1.0",
        "tree_name": "Refactor Pin Test",
        "persons": [
            {"id": "p1", "display_given_name": "Ann", "display_surname": "Lee", "sex": "FEMALE"},
            {"id": "p2", "display_given_name": "Bo", "display_surname": "Lee", "sex": "MALE"},
        ],
        "family_groups": [
            {"id": "fg1", "union_type": "MARRIAGE", "parent_ids": ["p1", "p2"], "children": {}},
        ],
    }
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("Refactor_Pin_Test.ofr", json.dumps(payload))
    zip_buf.seek(0)
    upload = UploadFile(file=zip_buf, filename="test.zip")

    uow = SqlAlchemyUnitOfWork(session)
    result = await import_tree_zip(current_user=seeded_user, uow=uow, file=upload)

    assert result["tree_name"] == "Refactor Pin Test"
    tree_id = uuid.UUID(result["tree_id"])

    persons = (await session.execute(
        text("SELECT display_given_name FROM persons WHERE tree_id = :tid ORDER BY display_given_name"),
        {"tid": tree_id},
    )).fetchall()
    assert [p.display_given_name for p in persons] == ["Ann", "Bo"]

    fg_count = (await session.execute(
        text("SELECT COUNT(*) FROM family_groups WHERE tree_id = :tid"), {"tid": tree_id},
    )).scalar_one()
    assert fg_count == 1


@pytest.mark.asyncio
async def test_import_zip_restores_cover_photo_with_no_primary_person_photos(
    session: AsyncSession, seeded_user
) -> None:
    """Pins the highest-risk path touched by the Task 7 refactor: a tree whose
    archive has a cover photo but where NO person has a primary photo, so
    photos_by_person_id ends up empty. Before the refactor, the cover-photo
    UPDATE was committed together with the tree/persons/family-groups commit
    that used to run right after it in the same function. After the refactor,
    that commit happens inside _create_tree_from_ofr_data, *before* the
    cover-photo block even runs, so the cover-photo block needed its own
    explicit commit to stay durable for any caller that doesn't go through
    the request-scoped session wrapper (which auto-commits on clean exit) —
    including this test, which calls import_tree_zip directly. This test
    proves that added commit actually persists the cover photo URL."""
    from src.api.v1.collaboration import import_tree_zip
    from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork

    payload = {
        "ofr_version": "1.0",
        "tree_name": "Cover Photo Pin Test",
        "tree_cover_photo_filename": "cover.jpg",
        "persons": [
            {"id": "p1", "display_given_name": "Cam", "display_surname": "Nolan", "sex": "MALE"},
        ],
        "family_groups": [],
    }
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("Cover_Photo_Pin_Test.ofr", json.dumps(payload))
        zf.writestr("cover.jpg", b"fake-cover-photo-bytes")
    zip_buf.seek(0)
    upload = UploadFile(file=zip_buf, filename="test.zip")

    uow = SqlAlchemyUnitOfWork(session)
    mock_s3 = MagicMock()
    with patch("src.api.v1._s3._make_s3_client", return_value=mock_s3):
        result = await import_tree_zip(current_user=seeded_user, uow=uow, file=upload)

    assert result["tree_name"] == "Cover Photo Pin Test"
    tree_id = uuid.UUID(result["tree_id"])

    # No person declared a photo_filename, so photos_by_person_id is empty —
    # the primary-photo-upload branch inside the helper never runs.
    mock_s3.put_object.assert_called_once()

    cover_url = (await session.execute(
        text("SELECT cover_image_url FROM family_trees WHERE id = :tid"), {"tid": tree_id},
    )).scalar_one()
    assert cover_url is not None
