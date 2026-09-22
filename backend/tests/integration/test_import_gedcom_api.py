"""Real-database integration tests for POST /trees/import-gedcom.

Follows the same real-Postgres pattern as test_change_request_revert.py (see
that module's docstring for local setup instructions). Requires
TEST_DATABASE_URL; the whole module is skipped if it isn't set.
"""
from __future__ import annotations

import io
import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    pytest.skip(
        "TEST_DATABASE_URL not set — this module needs a real, migrated Postgres "
        "database (see test_change_request_revert.py for local setup). Skipping.",
        allow_module_level=True,
    )

_HEADER = """0 HEAD
1 SOUR TestSource
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
"""
_TRAILER = "0 TRLR\n"


def _ged_bytes(body: str) -> bytes:
    return (_HEADER + body + _TRAILER).encode("utf-8")


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name="Test", family_name="User", full_name="Test User", app_role="STANDARD",
    )


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.user = _user(uuid.uuid4(), self.tenant_id, "gedcom-importer@example.com")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"gedcom-test-{self.tenant_id.hex[:12]}"},
        )
        await s.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                VALUES (:id, :tenant, :email, true, true, 'STANDARD', 'Test', 'User')
            """),
            {"id": self.user.id, "tenant": self.tenant_id, "email": self.user.email},
        )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


def _uow(session: AsyncSession):
    from src.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
    return SqlAlchemyUnitOfWork(session)


def _upload(raw: bytes):
    from fastapi import UploadFile
    return UploadFile(file=io.BytesIO(raw), filename="tree.ged")


class TestImportTreeGedcom:
    @pytest.mark.asyncio
    async def test_import_creates_tree_persons_and_family(self, seed: Seed):
        from src.api.v1.collaboration import import_tree_gedcom

        raw = _ged_bytes(
            "0 @I1@ INDI\n1 NAME Dad /Smith/\n1 SEX M\n"
            "0 @I2@ INDI\n1 NAME Mom /Doe/\n1 SEX F\n"
            "0 @I3@ INDI\n1 NAME Kid /Smith/\n1 SEX M\n1 BIRT\n2 DATE 5 JUN 2000\n"
            "0 @F1@ FAM\n1 HUSB @I1@\n1 WIFE @I2@\n1 CHIL @I3@\n1 MARR\n2 DATE 1 JAN 1995\n"
        )

        result = await import_tree_gedcom(
            current_user=seed.user, uow=_uow(seed.session),
            tree_name="Imported Family", file=_upload(raw),
        )
        assert result["tree_name"] == "Imported Family"
        tree_id = result["tree_id"]

        persons = (await seed.session.execute(
            text("SELECT display_given_name, display_surname, sex FROM persons WHERE tree_id = :tid ORDER BY display_given_name"),
            {"tid": tree_id},
        )).all()
        assert [(p.display_given_name, p.display_surname, p.sex) for p in persons] == [
            ("Dad", "Smith", "MALE"),
            ("Kid", "Smith", "MALE"),
            ("Mom", "Doe", "FEMALE"),
        ]

        fg = (await seed.session.execute(
            text("SELECT union_type FROM family_groups WHERE tree_id = :tid"),
            {"tid": tree_id},
        )).first()
        assert fg.union_type == "MARRIAGE"

        owner_role = (await seed.session.execute(
            text("SELECT role FROM tree_members WHERE tree_id = :tid AND user_id = :uid"),
            {"tid": tree_id, "uid": seed.user.id},
        )).scalar()
        assert owner_role == "OWNER"

    @pytest.mark.asyncio
    async def test_import_rejects_unreadable_file(self, seed: Seed):
        from fastapi import HTTPException
        from src.api.v1.collaboration import import_tree_gedcom

        with pytest.raises(HTTPException) as exc_info:
            await import_tree_gedcom(
                current_user=seed.user, uow=_uow(seed.session),
                tree_name="Bad Import", file=_upload(b"not a gedcom file"),
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_import_rejects_file_with_no_individuals(self, seed: Seed):
        from fastapi import HTTPException
        from src.api.v1.collaboration import import_tree_gedcom

        with pytest.raises(HTTPException) as exc_info:
            await import_tree_gedcom(
                current_user=seed.user, uow=_uow(seed.session),
                tree_name="Empty Import", file=_upload(_ged_bytes("")),
            )
        assert exc_info.value.status_code == 422
