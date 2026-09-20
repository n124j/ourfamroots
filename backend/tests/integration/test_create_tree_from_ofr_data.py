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
