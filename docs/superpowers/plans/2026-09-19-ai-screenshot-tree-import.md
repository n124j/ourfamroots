# AI Screenshot → Family Tree Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin upload a screenshot of a family tree chart and have Claude (vision) extract the people, relationships, and per-person photos into a new, fully-editable tree — gated to Admin users on a paid subscription.

**Architecture:** A presigned-upload → confirm → Celery → poll pipeline (mirroring the existing `media.py` flow) runs the vision extraction and Pillow-based photo cropping into a staging area; nothing touches real tree tables until the admin reviews the draft and calls a `finalize` endpoint, which shares its tree-creation logic with the existing `import_tree_zip` endpoint via an extracted helper.

**Tech Stack:** FastAPI, SQLAlchemy (async for the API, sync engine for the Celery task — see Task 6), Alembic, Celery + Redis, boto3/S3 (MinIO), Anthropic Python SDK (vision + tool use), Pillow, React + TanStack Query-free imperative polling hook (matching `useMediaUpload.ts`), Vitest/pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-ai-screenshot-tree-import-design.md`

## Global Constraints

- Admin-only (`app_role` in `ADMIN`, `SUPER_ADMIN`) **and** paid-tier-only (`PREMIUM_INDIVIDUAL` or `PREMIUM_TEAM` subscription tier); Super Admin bypasses the paid check.
- No tree/person/family-group rows are written until the admin calls `finalize` on a reviewed draft.
- One screenshot → one new tree. No merging into an existing tree.
- Reuse existing infrastructure exactly where it already exists: `S3Service` (`src/infrastructure/media/s3.py`) for all S3 operations, the inline sync-engine pattern from `broadcast_tasks.py`/`subscription_tasks.py` for Celery DB access (**not** `media_tasks.py`'s `SyncSessionFactory`/`get_s3()` calls — those imports are dead code with nothing that ever constructs them; do not copy that pattern).
- All new user-facing frontend strings go in both `frontend/src/i18n/locales/en.ts` and `ne.ts`.

---

### Task 1: `ai_tree_import_jobs` table + ORM model

**Files:**
- Create: `backend/alembic/versions/0056_ai_tree_import_jobs.py`
- Create: `backend/src/infrastructure/database/models/ai_tree_import.py`
- Modify: `backend/src/infrastructure/database/models/__init__.py`
- Test: `backend/tests/unit/test_ai_tree_import_model.py`

**Interfaces:**
- Produces: `AiTreeImportJobModel` (table `ai_tree_import_jobs`) with columns `id: uuid.UUID`, `tenant_id: uuid.UUID`, `created_by: uuid.UUID | None`, `status: str` (`"PENDING" | "PROCESSING" | "READY" | "FAILED"`), `screenshot_storage_key: str`, `photo_staging_prefix: str`, `celery_task_id: str | None`, `result_json: dict | None`, `processing_error: str | None`, `created_at: datetime`, `updated_at: datetime`.

- [ ] **Step 1: Write the failing model test**

```python
# backend/tests/unit/test_ai_tree_import_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_ai_tree_import_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infrastructure.database.models.ai_tree_import'`

- [ ] **Step 3: Write the model**

```python
# backend/src/infrastructure/database/models/ai_tree_import.py
"""AiTreeImportJob ORM model — tracks an admin's screenshot-to-tree AI extraction job."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base, TimestampMixin


class AiTreeImportJobModel(Base, TimestampMixin):
    """Maps to the `ai_tree_import_jobs` table."""

    __tablename__ = "ai_tree_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDING'"))
    screenshot_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    photo_staging_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AiTreeImportJobModel id={self.id!r} status={self.status!r}>"
```

Check `backend/src/infrastructure/database/base.py` for `TimestampMixin` — it already provides `created_at`/`updated_at` on every other recent model (confirm by reading the file; if `TimestampMixin` does not exist, add `created_at`/`updated_at` columns explicitly using the exact pattern from `broadcast_log.py:34-36` plus an `updated_at` column with `onupdate=text("now()")`).

- [ ] **Step 4: Register the model**

Edit `backend/src/infrastructure/database/models/__init__.py`:

```python
from src.infrastructure.database.models.section_visibility import SectionVisibilityRuleModel
from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel
```

Add `"AiTreeImportJobModel"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/unit/test_ai_tree_import_model.py -v`
Expected: PASS

- [ ] **Step 6: Write the migration**

```python
# backend/alembic/versions/0056_ai_tree_import_jobs.py
"""Add ai_tree_import_jobs table for the AI screenshot-to-tree import feature.

Revision ID: 0056
Revises: 0055
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_tree_import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("screenshot_storage_key", sa.String(512), nullable=False),
        sa.Column("photo_staging_prefix", sa.String(512), nullable=False),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_tree_import_jobs_tenant_id", "ai_tree_import_jobs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_tree_import_jobs_tenant_id", table_name="ai_tree_import_jobs")
    op.drop_table("ai_tree_import_jobs")
```

- [ ] **Step 7: Run the migration against the local dev database**

Run: `cd backend && alembic upgrade head`
Expected: applies `0056` cleanly with no errors. If `TimestampMixin` was confirmed absent in Step 3, add `onupdate=sa.text("now()")` is not settable via server_default alone — instead, in that case only, add a lightweight `updated_at` trigger identical to whatever the most recent prior migration used for another table's `updated_at` (check `0042_subscriptions.py` — it has no trigger, so a plain column with `server_default=now()` and manual updates in application code is this codebase's existing convention; do not add a trigger).

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/0056_ai_tree_import_jobs.py backend/src/infrastructure/database/models/ai_tree_import.py backend/src/infrastructure/database/models/__init__.py backend/tests/unit/test_ai_tree_import_model.py
git commit -m "feat: add ai_tree_import_jobs table and ORM model"
```

---

### Task 2: Settings + new dependencies

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/requirements/base.txt`
- Test: `backend/tests/unit/test_config_ai_import.py`

**Interfaces:**
- Produces: `Settings.anthropic_api_key: str`, `Settings.ai_import_model: str` (default `"claude-sonnet-5"`), `Settings.ai_import_max_screenshot_bytes: int` (default `15 * 1024 * 1024`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_config_ai_import.py
"""Unit tests for the AI-import-related Settings fields."""
from __future__ import annotations

from src.config import Settings


def test_ai_import_settings_have_sane_defaults(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 32)
    settings = Settings()
    assert settings.anthropic_api_key == ""
    assert settings.ai_import_model == "claude-sonnet-5"
    assert settings.ai_import_max_screenshot_bytes == 15 * 1024 * 1024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_config_ai_import.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'anthropic_api_key'`

- [ ] **Step 3: Add the settings**

Edit `backend/src/config.py`, after the `# ── Sentry ───` block (before `@field_validator`):

```python
    # ── AI screenshot → tree import ───────────────────────────
    anthropic_api_key: str = ""
    ai_import_model: str = "claude-sonnet-5"
    ai_import_max_screenshot_bytes: int = 15 * 1024 * 1024  # 15 MB
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/unit/test_config_ai_import.py -v`
Expected: PASS

- [ ] **Step 5: Add the new Python dependencies**

Edit `backend/requirements/base.txt`, after the `# Storage` block:

```
# Storage
boto3==1.35.0

# AI vision extraction
anthropic==0.69.0

# Image processing (screenshot cropping)
Pillow==11.0.0
```

Run: `cd backend && pip install -r requirements/base.txt` and confirm both packages install without conflicts. If either pinned version fails to resolve, run `pip index versions anthropic` / `pip index versions Pillow` and update the pin to the latest compatible release before proceeding — do not leave the install broken.

- [ ] **Step 6: Commit**

```bash
git add backend/src/config.py backend/requirements/base.txt backend/tests/unit/test_config_ai_import.py
git commit -m "feat: add Anthropic/vision-import settings and dependencies"
```

---

### Task 3: `AdminPaidFeatureDep`

**Files:**
- Modify: `backend/src/api/deps.py`
- Test: `backend/tests/integration/test_admin_paid_feature_dep.py`

**Interfaces:**
- Consumes: `VerifiedUserDep`, `SessionDep` (both already in `deps.py`), `AppRole` enum (`src.domain.collaboration.entities`).
- Produces: `AdminPaidFeatureDep = Annotated[UserModel, Depends(require_admin_paid_feature)]`.

- [ ] **Step 1: Write the failing test**

This codebase's admin-feature integration tests (e.g. `tests/integration/test_broadcast.py`) don't use an HTTP test client — they call the router's async function directly with a `SimpleNamespace` fake `current_user`, against a real seeded Postgres database gated behind `TEST_DATABASE_URL`. Follow that exact pattern:

```python
# backend/tests/integration/test_admin_paid_feature_dep.py
"""Real-database integration tests for AdminPaidFeatureDep (admin-only AND
paid-tier-only gating). Same real-Postgres, direct-function-call pattern as
test_broadcast.py (requires TEST_DATABASE_URL; skipped otherwise)."""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

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


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    return SimpleNamespace(id=uid, tenant_id=tenant_id, email=email, app_role=app_role)


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.free_admin = _user(uuid.uuid4(), self.tenant_id, "free-admin@example.com", "ADMIN")
        self.paid_standard = _user(uuid.uuid4(), self.tenant_id, "paid-standard@example.com", "STANDARD")
        self.paid_admin = _user(uuid.uuid4(), self.tenant_id, "paid-admin@example.com", "ADMIN")
        self.super_admin = _user(uuid.uuid4(), self.tenant_id, "root@example.com", "SUPER_ADMIN")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.free_admin, self.paid_standard, self.paid_admin, self.super_admin):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, :role, 'Test', 'User')
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role},
            )
        sub_id = uuid.uuid4()
        await s.execute(
            text("""INSERT INTO subscriptions (id, tenant_id, name, tier)
                    VALUES (:id, :tenant, 'Premium', 'PREMIUM_INDIVIDUAL')"""),
            {"id": sub_id, "tenant": self.tenant_id},
        )
        for u in (self.paid_standard, self.paid_admin):
            await s.execute(
                text("""INSERT INTO subscription_members (id, subscription_id, user_id)
                        VALUES (gen_random_uuid(), :sid, :uid)"""),
                {"sid": sub_id, "uid": u.id},
            )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestAdminPaidFeatureDep:
    @pytest.mark.asyncio
    async def test_free_tier_admin_is_blocked(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        with pytest.raises(HTTPException) as exc:
            await require_admin_paid_feature(user=seed.free_admin, session=seed.session)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_paid_non_admin_is_blocked(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        with pytest.raises(HTTPException) as exc:
            await require_admin_paid_feature(user=seed.paid_standard, session=seed.session)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_paid_admin_is_allowed(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        result = await require_admin_paid_feature(user=seed.paid_admin, session=seed.session)
        assert result.id == seed.paid_admin.id

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_paid_check(self, seed: Seed):
        from src.api.deps import require_admin_paid_feature
        result = await require_admin_paid_feature(user=seed.super_admin, session=seed.session)
        assert result.id == seed.super_admin.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/integration/test_admin_paid_feature_dep.py -v`
Expected: FAIL with `ImportError: cannot import name 'require_admin_paid_feature'`

- [ ] **Step 3: Implement the dependency**

Append to `backend/src/api/deps.py`, after `NamespaceOwnerDep`:

```python
async def require_admin_paid_feature(user: VerifiedUserDep, session: SessionDep) -> UserModel:
    """Restrict endpoint to Admins/Super Admins whose account is entitled by an
    active paid-tier subscription. Super Admin bypasses the paid check
    entirely — same precedent as get_my_filters() in subscriptions.py."""
    if user.app_role not in (AppRole.ADMIN, AppRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Administrator access required")
    if user.app_role == AppRole.SUPER_ADMIN:
        return user

    from sqlalchemy import text

    row = (await session.execute(
        text("""
            SELECT 1
            FROM subscriptions s
            WHERE (s.expires_at IS NULL OR s.expires_at > now())
              AND s.tier IN ('PREMIUM_INDIVIDUAL', 'PREMIUM_TEAM')
              AND (
                s.is_default
                OR EXISTS (
                    SELECT 1 FROM subscription_members sm
                    WHERE sm.subscription_id = s.id AND sm.user_id = :uid
                )
              )
            LIMIT 1
        """),
        {"uid": user.id},
    )).first()

    if row is None:
        raise HTTPException(status_code=403, detail="This feature requires a paid subscription.")
    return user

AdminPaidFeatureDep = Annotated[UserModel, Depends(require_admin_paid_feature)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/integration/test_admin_paid_feature_dep.py -v`
Expected: PASS (all 4 cases)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/deps.py backend/tests/integration/test_admin_paid_feature_dep.py
git commit -m "feat: add AdminPaidFeatureDep for admin+paid-tier gated endpoints"
```

---

### Task 4: Vision extraction module

**Files:**
- Create: `backend/src/infrastructure/ai_import/__init__.py`
- Create: `backend/src/infrastructure/ai_import/vision_extraction.py`
- Test: `backend/tests/unit/test_vision_extraction.py`

**Interfaces:**
- Produces:
  - `ExtractedPerson(BaseModel)`: `id: str`, `display_given_name: str = ""`, `display_surname: str = ""`, `sex: str = "UNKNOWN"`, `bbox: Optional[list[float]] = None`.
  - `ExtractedFamilyGroup(BaseModel)`: `id: str`, `union_type: str = "UNKNOWN"`, `parent_ids: list[str] = []`, `children: dict[str, str] = {}`.
  - `ExtractedTreeDraft(BaseModel)`: `persons: list[ExtractedPerson] = []`, `family_groups: list[ExtractedFamilyGroup] = []`.
  - `extract_tree_from_image(image_bytes: bytes, media_type: str, api_key: str, model: str) -> ExtractedTreeDraft` — raises `VisionExtractionError` (new exception class in the same module) on API failure or an unparseable tool response.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_vision_extraction.py
"""Unit tests for vision_extraction: parsing/validating Claude's tool-use output."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ai_import.vision_extraction import (
    ExtractedTreeDraft,
    VisionExtractionError,
    extract_tree_from_image,
)


def _fake_anthropic_response(tool_input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_parses_valid_response(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [
            {"id": "jane", "display_given_name": "Jane", "display_surname": "Doe",
             "sex": "FEMALE", "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"id": "no_photo_kid", "display_given_name": "Sam", "display_surname": "Doe",
             "sex": "UNKNOWN"},
        ],
        "family_groups": [
            {"id": "fg1", "union_type": "MARRIAGE", "parent_ids": ["jane"],
             "children": {"no_photo_kid": "BIOLOGICAL"}},
        ],
    })

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")

    assert isinstance(draft, ExtractedTreeDraft)
    assert len(draft.persons) == 2
    assert draft.persons[0].bbox == [0.1, 0.1, 0.2, 0.2]
    assert draft.persons[1].bbox is None
    assert draft.family_groups[0].children == {"no_photo_kid": "BIOLOGICAL"}


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_drops_malformed_bbox(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _fake_anthropic_response({
        "persons": [
            {"id": "p1", "display_given_name": "A", "display_surname": "B",
             "sex": "MALE", "bbox": [1.5, 0, 0, 0]},  # out of [0,1] range
        ],
        "family_groups": [],
    })

    draft = extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")
    assert draft.persons[0].bbox is None


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_raises_on_no_tool_use_block(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    text_block = MagicMock()
    text_block.type = "text"
    resp = MagicMock()
    resp.content = [text_block]
    mock_client.messages.create.return_value = resp

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")


@patch("src.infrastructure.ai_import.vision_extraction.Anthropic")
def test_extract_tree_from_image_wraps_api_errors(mock_anthropic_cls) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = RuntimeError("network down")

    with pytest.raises(VisionExtractionError):
        extract_tree_from_image(b"fake-image-bytes", "image/jpeg", "sk-test", "claude-sonnet-5")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_vision_extraction.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infrastructure.ai_import'`

- [ ] **Step 3: Create the package and implement extraction**

```python
# backend/src/infrastructure/ai_import/__init__.py
```
(empty — package marker)

```python
# backend/src/infrastructure/ai_import/vision_extraction.py
"""Calls Claude (vision + forced tool use) to extract a family tree draft from
a screenshot: people (with an optional normalized photo bounding box) and
family groups (unions + parent/child links). Never writes to real tree tables
— this module only returns a validated draft."""
from __future__ import annotations

import base64
from typing import Optional

from anthropic import Anthropic
from pydantic import BaseModel, field_validator


class VisionExtractionError(Exception):
    """Raised when the vision API call fails or returns an unusable response."""


class ExtractedPerson(BaseModel):
    id: str
    display_given_name: str = ""
    display_surname: str = ""
    sex: str = "UNKNOWN"
    bbox: Optional[list[float]] = None

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is None:
            return None
        if len(v) != 4 or any((not isinstance(n, (int, float))) or n < 0 or n > 1 for n in v):
            return None  # drop a malformed box rather than fail the whole extraction
        return [float(n) for n in v]

    @field_validator("sex")
    @classmethod
    def _validate_sex(cls, v: str) -> str:
        return v if v in ("MALE", "FEMALE", "OTHER", "UNKNOWN") else "UNKNOWN"


class ExtractedFamilyGroup(BaseModel):
    id: str
    union_type: str = "UNKNOWN"
    parent_ids: list[str] = []
    children: dict[str, str] = {}

    @field_validator("union_type")
    @classmethod
    def _validate_union_type(cls, v: str) -> str:
        return v if v in ("MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN") else "UNKNOWN"


class ExtractedTreeDraft(BaseModel):
    persons: list[ExtractedPerson] = []
    family_groups: list[ExtractedFamilyGroup] = []


_EXTRACTION_TOOL = {
    "name": "record_family_tree",
    "description": (
        "Record every person and family relationship visible in the family "
        "tree chart image. Omit any person or relationship you are not "
        "reasonably confident about rather than guessing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "persons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "A short unique slug for this person, e.g. 'john_smith'."},
                        "display_given_name": {"type": "string"},
                        "display_surname": {"type": "string"},
                        "sex": {"type": "string", "enum": ["MALE", "FEMALE", "OTHER", "UNKNOWN"]},
                        "bbox": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 4,
                            "maxItems": 4,
                            "description": "Normalized [x, y, width, height] (each 0-1) bounding box of this person's photo. Omit entirely if no photo is shown for them.",
                        },
                    },
                    "required": ["id", "display_given_name", "display_surname", "sex"],
                },
            },
            "family_groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "union_type": {"type": "string", "enum": ["MARRIAGE", "PARTNERSHIP", "COHABITATION", "UNKNOWN"]},
                        "parent_ids": {"type": "array", "items": {"type": "string"}},
                        "children": {
                            "type": "object",
                            "description": "Map of child person id -> parentage type.",
                            "additionalProperties": {
                                "type": "string",
                                "enum": ["BIOLOGICAL", "ADOPTIVE", "STEP", "FOSTER", "UNKNOWN"],
                            },
                        },
                    },
                    "required": ["id", "parent_ids", "children"],
                },
            },
        },
        "required": ["persons", "family_groups"],
    },
}

_PROMPT = (
    "This image is a family tree chart. Identify every person shown (by the "
    "label near their photo or box) and every parent-child / spousal "
    "relationship the chart's lines indicate. Call record_family_tree with "
    "the full result."
)


def extract_tree_from_image(
    image_bytes: bytes,
    media_type: str,
    api_key: str,
    model: str,
) -> ExtractedTreeDraft:
    """Call Claude vision with forced tool use and return a validated draft.

    Raises VisionExtractionError on any API failure, missing tool_use block,
    or a response that fails ExtractedTreeDraft validation.
    """
    client = Anthropic(api_key=api_key)
    encoded = base64.standard_b64encode(image_bytes).decode("ascii")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            tools=[_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_family_tree"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}},
                    {"type": "text", "text": _PROMPT},
                ],
            }],
        )
    except Exception as exc:
        raise VisionExtractionError(f"Vision API call failed: {exc}") from exc

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        raise VisionExtractionError("Vision API response did not include a tool_use block")

    try:
        return ExtractedTreeDraft(**tool_block.input)
    except Exception as exc:
        raise VisionExtractionError(f"Vision API response failed schema validation: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/unit/test_vision_extraction.py -v`
Expected: PASS (all 4 cases)

- [ ] **Step 5: Commit**

```bash
git add backend/src/infrastructure/ai_import/__init__.py backend/src/infrastructure/ai_import/vision_extraction.py backend/tests/unit/test_vision_extraction.py
git commit -m "feat: add Claude vision extraction for screenshot-to-tree drafts"
```

---

### Task 5: Photo cropping helper

**Files:**
- Create: `backend/src/infrastructure/ai_import/photo_cropping.py`
- Test: `backend/tests/unit/test_photo_cropping.py`

**Interfaces:**
- Consumes: `ExtractedPerson.bbox` shape (`list[float]` of 4 normalized numbers) from Task 4.
- Produces: `crop_person_photo(image_bytes: bytes, bbox: list[float]) -> bytes` — returns JPEG bytes of the cropped region, clamped to the image bounds.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_photo_cropping.py
"""Unit tests for crop_person_photo."""
from __future__ import annotations

import io

from PIL import Image

from src.infrastructure.ai_import.photo_cropping import crop_person_photo


def _make_test_image(width: int, height: int) -> bytes:
    im = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def test_crop_person_photo_returns_expected_dimensions() -> None:
    source = _make_test_image(1000, 800)
    # bbox = 10%-30% of width, 20%-50% of height
    cropped_bytes = crop_person_photo(source, [0.1, 0.2, 0.2, 0.3])

    cropped = Image.open(io.BytesIO(cropped_bytes))
    assert cropped.format == "JPEG"
    assert cropped.width == 200   # 0.2 * 1000
    assert cropped.height == 240  # 0.3 * 800


def test_crop_person_photo_clamps_out_of_bounds_bbox() -> None:
    source = _make_test_image(500, 500)
    # bbox extends past the right/bottom edge
    cropped_bytes = crop_person_photo(source, [0.9, 0.9, 0.5, 0.5])

    cropped = Image.open(io.BytesIO(cropped_bytes))
    assert cropped.width == 50    # clamped to 500 - 450
    assert cropped.height == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_photo_cropping.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infrastructure.ai_import.photo_cropping'`

- [ ] **Step 3: Implement cropping**

```python
# backend/src/infrastructure/ai_import/photo_cropping.py
"""Crops a single person's photo out of a family-tree screenshot using a
normalized [x, y, width, height] bounding box from vision_extraction."""
from __future__ import annotations

import io

from PIL import Image


def crop_person_photo(image_bytes: bytes, bbox: list[float]) -> bytes:
    """Return JPEG bytes of the region *bbox* (normalized 0-1 [x,y,w,h])
    cropped out of *image_bytes*, clamped to the image's actual dimensions."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    x, y, w, h = bbox

    left = max(0, min(width, round(x * width)))
    top = max(0, min(height, round(y * height)))
    right = max(left, min(width, round((x + w) * width)))
    bottom = max(top, min(height, round((y + h) * height)))

    cropped = image.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/unit/test_photo_cropping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/infrastructure/ai_import/photo_cropping.py backend/tests/unit/test_photo_cropping.py
git commit -m "feat: add Pillow-based per-person photo cropping for AI tree import"
```

---

### Task 6: Celery task — orchestrate the full extraction pipeline

**Files:**
- Create: `backend/src/infrastructure/ai_import/ai_import_tasks.py`
- Modify: `backend/src/infrastructure/media/celery_app.py`
- Modify: `docker-compose.yml`
- Test: `backend/tests/unit/test_ai_import_tasks.py`

**Interfaces:**
- Consumes: `extract_tree_from_image` (Task 4), `crop_person_photo` (Task 5), `AiTreeImportJobModel` (Task 1), `S3Service` (`src/infrastructure/media/s3.py`, already exists).
- Produces: Celery task `extract_tree_from_screenshot_task(job_id: str) -> dict`, registered as `"src.infrastructure.ai_import.ai_import_tasks.extract_tree_from_screenshot_task"`. On success sets the job row's `status="READY"` and `result_json = {"persons": [...], "family_groups": [...]}` where each person with a crop carries `"photo_staging_key": "<photo_staging_prefix><person_id>.jpg"`. On any failure sets `status="FAILED"` and `processing_error`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_ai_import_tasks.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_ai_import_tasks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infrastructure.ai_import.ai_import_tasks'`

- [ ] **Step 3: Implement the task**

```python
# backend/src/infrastructure/ai_import/ai_import_tasks.py
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

from src.infrastructure.media.celery_app import celery_app

log = logging.getLogger(__name__)


def _get_sync_engine():
    url = os.environ.get(
        "SYNC_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/ourfamroots",
    )
    return create_engine(url, pool_pre_ping=True)


def _make_s3_service():
    from src.config import get_settings
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
    from src.config import get_settings
    from src.infrastructure.ai_import.photo_cropping import crop_person_photo
    from src.infrastructure.ai_import.vision_extraction import (
        VisionExtractionError,
        extract_tree_from_image,
    )
    from src.infrastructure.database.models.ai_tree_import import AiTreeImportJobModel

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/unit/test_ai_import_tasks.py -v`
Expected: PASS (both cases)

- [ ] **Step 5: Wire the task into the Celery app**

Edit `backend/src/infrastructure/media/celery_app.py`:

```python
    task_routes={
        "src.infrastructure.media.media_tasks.*": {"queue": "media"},
        "src.infrastructure.ai_import.ai_import_tasks.*": {"queue": "ai_import"},
    },
```

and:

```python
celery_app.autodiscover_tasks(["src.infrastructure.media", "src.infrastructure.subscriptions", "src.infrastructure.broadcast", "src.infrastructure.ai_import"])

from src.infrastructure.subscriptions import subscription_tasks  # noqa: F401,E402
from src.infrastructure.broadcast import broadcast_tasks  # noqa: F401,E402
from src.infrastructure.ai_import import ai_import_tasks  # noqa: F401,E402
```

- [ ] **Step 6: Add the new queue to the worker**

Edit `docker-compose.yml` line 154 (the worker's `--queues=media,default`):

```
              --queues=media,ai_import,default
```

- [ ] **Step 7: Run the full unit test file once more post-wiring**

Run: `cd backend && pytest tests/unit/test_ai_import_tasks.py tests/unit/test_vision_extraction.py tests/unit/test_photo_cropping.py -v`
Expected: PASS (all cases, confirms the wiring didn't break imports)

- [ ] **Step 8: Commit**

```bash
git add backend/src/infrastructure/ai_import/ai_import_tasks.py backend/src/infrastructure/media/celery_app.py docker-compose.yml backend/tests/unit/test_ai_import_tasks.py
git commit -m "feat: add Celery task orchestrating screenshot vision extraction + photo cropping"
```

---

### Task 7: Extract shared tree-creation helper from `import_tree_zip`

**Files:**
- Modify: `backend/src/api/v1/collaboration.py`
- Test: `backend/tests/unit/test_ofr_import_export.py` (existing — must still pass unmodified), `backend/tests/integration/test_create_tree_from_ofr_data.py` (new)

**Interfaces:**
- Produces: `_create_tree_from_ofr_data(uow, current_user, tree_name, tree_description, persons_raw, fgs_raw, photos_by_person_id) -> CreatedTreeResult` where `CreatedTreeResult` is a `NamedTuple(tree_id: uuid.UUID, tree_name: str, old_to_new: dict[str, uuid.UUID])`, and `photos_by_person_id: dict[str, tuple[bytes, str]]` maps an *old* (pre-import) person id to `(raw_photo_bytes, file_extension)`.
- Consumes (unchanged from before this task): `_VALID_SEX`, `_VALID_UNION_TYPES`, `_VALID_PARENTAGE_TYPES` (already at `collaboration.py:1915-1917`), `AuditEntry`/`Action`/`AuditEntityType`/`AuditLogRepository` (already imported inline inside `import_tree_zip`).

This task is a pure refactor: `import_tree_zip`'s behavior and its existing tests must not change. Do this task test-first by pinning current behavior with a new integration test that exercises `import_tree_zip` end-to-end, *then* refactor, then confirm the same test (and the existing unit tests) still pass.

- [ ] **Step 1: Write an integration test pinning `import_tree_zip`'s current behavior**

Following the same real-Postgres, direct-function-call pattern as `test_broadcast.py` (no HTTP test client is used anywhere in this codebase's admin/collaboration integration tests — see Task 3, Step 1):

```python
# backend/tests/integration/test_create_tree_from_ofr_data.py
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
```

- [ ] **Step 2: Run test to verify it currently passes (pinning existing behavior)**

Run: `cd backend && pytest tests/integration/test_create_tree_from_ofr_data.py -v`
Expected: PASS (this documents current behavior before refactor — if it fails, fix the fixture names first, since the refactor must not be blamed for a pre-existing failure)

- [ ] **Step 3: Extract the shared helper**

In `backend/src/api/v1/collaboration.py`, add near the top of the module (after the `_VALID_PARENTAGE_TYPES` constants, before `_OfrPerson`):

```python
from typing import Callable, NamedTuple


class CreatedTreeResult(NamedTuple):
    tree_id: uuid.UUID
    tree_name: str
    old_to_new: dict[str, uuid.UUID]


async def _create_tree_from_ofr_data(
    uow,
    current_user,
    tree_name: str,
    tree_description: str | None,
    persons_raw: list[dict],
    fgs_raw: list[dict],
    photos_by_person_id: dict[str, tuple[bytes, str]],
) -> CreatedTreeResult:
    """Create a new tree + persons + family groups from OFR-shaped dicts, and
    upload each person's primary photo from *photos_by_person_id* (old person
    id -> (raw_bytes, file_extension)). Does not handle gallery photos or a
    tree cover photo — callers that need those (currently only
    import_tree_zip) do so themselves using the returned old_to_new map."""
    from sqlalchemy import text as _text

    new_tree_id = uuid.uuid4()
    await uow._session.execute(_text("""
        INSERT INTO family_trees (id, tenant_id, name, description)
        VALUES (:id, :tenant, :name, :desc)
    """), {"id": new_tree_id, "tenant": current_user.tenant_id,
           "name": tree_name, "desc": tree_description})

    await uow._session.execute(_text("""
        INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role)
        VALUES (gen_random_uuid(), :tid, :uid, :tenant, 'OWNER')
    """), {"tid": new_tree_id, "uid": current_user.id, "tenant": current_user.tenant_id})

    old_to_new: dict[str, uuid.UUID] = {}
    for p in persons_raw:
        new_pid = uuid.uuid4()
        old_to_new[p["id"]] = new_pid
        birth_date_val = None
        if p.get("birth_date"):
            try: birth_date_val = __import__("datetime").date.fromisoformat(p["birth_date"])
            except ValueError: pass
        death_date_val = None
        if p.get("death_date"):
            try: death_date_val = __import__("datetime").date.fromisoformat(p["death_date"])
            except ValueError: pass
        await uow._session.execute(_text("""
            INSERT INTO persons
              (id, tenant_id, tree_id, display_given_name, display_surname,
               sex, is_living, is_deceased,
               birth_date, death_date, birth_year, death_year,
               born_city, born_country, died_city, died_country,
               notes)
            VALUES (:id, :tenant, :tid, :given, :surname, :sex, :living, :deceased,
                    :birth_date, :death_date, :birth_year, :death_year,
                    :born_city, :born_country, :died_city, :died_country,
                    :notes)
        """), {
            "id":           new_pid,
            "tenant":       current_user.tenant_id,
            "tid":          new_tree_id,
            "given":        p.get("display_given_name", ""),
            "surname":      p.get("display_surname", ""),
            "sex":          p.get("sex", "UNKNOWN") if p.get("sex", "UNKNOWN") in _VALID_SEX else "UNKNOWN",
            "living":       p.get("is_living", True),
            "deceased":     p.get("is_deceased", False),
            "birth_date":   birth_date_val,
            "death_date":   death_date_val,
            "birth_year":   p.get("birth_year"),
            "death_year":   p.get("death_year"),
            "born_city":    p.get("born_city") or p.get("city"),
            "born_country": p.get("born_country") or p.get("country"),
            "died_city":    p.get("died_city"),
            "died_country": p.get("died_country"),
            "notes":        p.get("notes"),
        })

    for fg in fgs_raw:
        new_fg_id = uuid.uuid4()
        parent_ids = [old_to_new.get(pid) for pid in fg.get("parent_ids", []) if pid in old_to_new]
        p1 = parent_ids[0] if len(parent_ids) > 0 else None
        p2 = parent_ids[1] if len(parent_ids) > 1 else None

        from datetime import date as _date
        udate_val = None
        if fg.get("union_date"):
            try: udate_val = _date.fromisoformat(fg["union_date"])
            except ValueError: pass
        uedate_val = None
        if fg.get("union_end_date"):
            try: uedate_val = _date.fromisoformat(fg["union_end_date"])
            except ValueError: pass

        await uow._session.execute(_text("""
            INSERT INTO family_groups (id, tenant_id, tree_id, union_type, custom_label, is_divorced,
                                       union_date, union_date_year, union_end_date, union_end_date_year,
                                       parent1_id, parent2_id)
            VALUES (:id, :tenant, :tid, :utype, :clabel, :divorced,
                    :udate, :udate_year, :uedate, :uedate_year, :p1, :p2)
        """), {"id": new_fg_id, "tenant": current_user.tenant_id, "tid": new_tree_id,
               "utype": fg.get("union_type", "UNKNOWN") if fg.get("union_type", "UNKNOWN") in _VALID_UNION_TYPES else "UNKNOWN",
               "clabel": fg.get("custom_label"),
               "divorced": fg.get("is_divorced", False),
               "udate": udate_val,
               "udate_year": fg.get("union_date_year"),
               "uedate": uedate_val,
               "uedate_year": fg.get("union_end_date_year"),
               "p1": p1, "p2": p2})

        for old_pid in fg.get("parent_ids", []):
            new_pid = old_to_new.get(old_pid)
            if new_pid is None:
                continue
            await uow._session.execute(_text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'PARENT')
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_pid})

        for old_child_id, parentage in fg.get("children", {}).items():
            new_child_id = old_to_new.get(old_child_id)
            if new_child_id is None:
                continue
            await uow._session.execute(_text("""
                INSERT INTO family_group_members
                  (id, tenant_id, tree_id, family_group_id, person_id, role, parentage_type)
                VALUES (gen_random_uuid(), :tenant, :tid, :fgid, :pid, 'CHILD', :pt)
            """), {"tenant": current_user.tenant_id, "tid": new_tree_id,
                   "fgid": new_fg_id, "pid": new_child_id,
                   "pt": parentage if parentage in _VALID_PARENTAGE_TYPES else "UNKNOWN"})

    await uow._session.commit()

    if photos_by_person_id:
        from src.api.v1._s3 import _make_s3_client
        from src.config import get_settings
        settings = get_settings()
        bucket = settings.s3_bucket or "ourfamroots-local"
        s3 = _make_s3_client(settings)
        content_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
        for old_pid, (photo_bytes, ext) in photos_by_person_id.items():
            new_pid = old_to_new.get(old_pid)
            if new_pid is None:
                continue
            try:
                s3_key = f"tenants/{current_user.tenant_id}/trees/{new_tree_id}/persons/{new_pid}/photo/{uuid.uuid4()}.{ext}"
                s3.put_object(Bucket=bucket, Key=s3_key, Body=photo_bytes,
                               ContentType=content_types.get(ext.lower(), "image/jpeg"))
                await uow._session.execute(_text("""
                    UPDATE persons SET photo_url = :url WHERE id = :pid
                """), {"url": s3_key, "pid": new_pid})
            except Exception:
                pass  # skip individual photo failures
        await uow._session.commit()

    from src.domain.collaboration.entities import AuditEntry, Action, AuditEntityType
    from src.infrastructure.repositories.collaboration import AuditLogRepository
    actor_name = f"{current_user.given_name or ''} {current_user.family_name or ''}".strip() or current_user.email
    await AuditLogRepository(uow._session).append(
        AuditEntry.create(
            tree_id=new_tree_id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            actor_display_name=actor_name,
            action=Action.IMPORT_TREE,
            entity_type=AuditEntityType.TREE,
            entity_id=new_tree_id,
            entity_display_name=tree_name,
            after={"tree_name": tree_name, "person_count": len(persons_raw),
                   "photos": len(photos_by_person_id)},
        )
    )
    await uow._session.commit()

    return CreatedTreeResult(tree_id=new_tree_id, tree_name=tree_name, old_to_new=old_to_new)
```

- [ ] **Step 4: Replace `import_tree_zip`'s inline logic with a call to the helper**

In `import_tree_zip`, replace the block from `# 1. Create tree` through the audit-log `await uow._session.commit()` (i.e. everything the new helper now owns) with:

```python
    photos_by_person_id: dict[str, tuple[bytes, str]] = {}
    for p in persons_raw:
        zip_path = p.get("photo_filename")
        if zip_path and zip_path in zf.namelist():
            ext = zip_path.rsplit(".", 1)[-1] if "." in zip_path else "jpg"
            photos_by_person_id[p["id"]] = (zf.read(zip_path), ext)

    result = await _create_tree_from_ofr_data(
        uow, current_user, tree_name, tree_description, persons_raw, fgs_raw, photos_by_person_id,
    )
    new_tree_id = result.tree_id
    old_to_new = result.old_to_new
```

Keep the tree-cover-photo restore block (`tree_cover_filename` handling) and the **gallery photos** block (`# 4b. Import gallery photos`) exactly as they are today — they still run after this, using `new_tree_id`/`old_to_new` from `result`. Remove the now-duplicated `photo_filename_map` construction if it's no longer used elsewhere in the function; keep it only if the gallery-photos block still reads from it (check — the gallery block iterates `persons_raw` directly and doesn't need `photo_filename_map`, so it's safe to remove). End the function with:

```python
    return {"tree_id": str(new_tree_id), "tree_name": result.tree_name}
```

- [ ] **Step 5: Run both the pinning test and the existing OFR unit tests**

Run: `cd backend && pytest tests/integration/test_create_tree_from_ofr_data.py tests/unit/test_ofr_import_export.py -v`
Expected: PASS — identical behavior to before the refactor. If the pinning test fails, the refactor introduced a regression; fix `_create_tree_from_ofr_data` or the call site until both pass, do not weaken the test.

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/v1/collaboration.py backend/tests/integration/test_create_tree_from_ofr_data.py
git commit -m "refactor: extract _create_tree_from_ofr_data helper from import_tree_zip"
```

---

### Task 8: AI tree import API endpoints

**Files:**
- Create: `backend/src/api/v1/ai_tree_import.py`
- Modify: `backend/src/api/v1/router.py`
- Modify: `backend/src/api/v1/_admin_log.py`
- Test: `backend/tests/integration/test_ai_tree_import_api.py`

**Interfaces:**
- Consumes: `AdminPaidFeatureDep` (Task 3), `AiTreeImportJobModel` (Task 1), `extract_tree_from_screenshot_task` (Task 6), `_create_tree_from_ofr_data`/`CreatedTreeResult` (Task 7).
- Produces:
  - `POST /api/v1/admin/ai-tree-import/upload-url` → `{"job_id": str, "upload_url": str, "upload_fields": dict, "max_size_bytes": int}`
  - `POST /api/v1/admin/ai-tree-import/{job_id}/confirm` → `{"job_id": str, "status": str}`
  - `GET /api/v1/admin/ai-tree-import/{job_id}` → `{"job_id": str, "status": str, "processing_error": str | None, "persons": list | None, "family_groups": list | None, "photo_urls": dict[str, str]}`
  - `POST /api/v1/admin/ai-tree-import/{job_id}/finalize`, body `{"persons": [...], "family_groups": [...]}` → `{"tree_id": str, "tree_name": str}`

- [ ] **Step 1: Write the failing integration test**

Same real-Postgres, direct-function-call pattern as `test_broadcast.py` and Tasks 3/7 above (S3 and the Celery task's `.delay` are mocked/monkeypatched; nothing calls Anthropic here):

```python
# backend/tests/integration/test_ai_tree_import_api.py
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
    @patch("src.api.v1.ai_tree_import._make_s3_client")
    async def test_creates_pending_job(self, mock_make_s3, seed: Seed):
        from src.api.v1.ai_tree_import import request_upload_url, UploadUrlRequest

        s3 = MagicMock()
        s3.generate_presigned_post.return_value = {"url": "https://s3.example/", "fields": {}}
        mock_make_s3.return_value = s3

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
    async def test_dispatches_celery_task_and_sets_processing(self, mock_make_s3, mock_task, seed: Seed):
        from src.api.v1.ai_tree_import import request_upload_url, confirm_upload, UploadUrlRequest

        s3 = MagicMock()
        s3.generate_presigned_post.return_value = {"url": "https://s3.example/", "fields": {}}
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/integration/test_ai_tree_import_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.api.v1.ai_tree_import'`

- [ ] **Step 3: Implement the endpoints**

```python
# backend/src/api/v1/ai_tree_import.py
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
    from src.config import get_settings
    from src.api.v1._s3 import presign_photo
    settings = get_settings()

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
```

- [ ] **Step 4: Register the router**

Edit `backend/src/api/v1/router.py`:

```python
from src.api.v1.ai_tree_import import router as ai_tree_import_router
```

and:

```python
v1_router.include_router(ai_tree_import_router)
```

- [ ] **Step 5: Add the admin-log event type**

Edit `backend/src/api/v1/_admin_log.py`, adding to `LOGIN_EVENT_TYPES` near the Broadcast group:

```python
    # AI tree import
    "AI_TREE_IMPORT",
```

Also add the matching entry to `frontend/src/pages/ActivityPage.tsx`'s `ACTION_OPTIONS` list (the comment on `LOGIN_EVENT_TYPES` says to keep them in sync) — find that list and add an `AI_TREE_IMPORT` option using the same `{value, label}` shape as the neighboring `BROADCAST_SEND` entry.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/integration/test_ai_tree_import_api.py -v`
Expected: PASS (all 4 cases)

- [ ] **Step 7: Run the full backend test suite to confirm no regressions**

Run: `cd backend && pytest -v`
Expected: PASS — in particular `test_ofr_import_export.py` and `test_create_tree_from_ofr_data.py` from Task 7 must still be green.

- [ ] **Step 8: Commit**

```bash
git add backend/src/api/v1/ai_tree_import.py backend/src/api/v1/router.py backend/src/api/v1/_admin_log.py frontend/src/pages/ActivityPage.tsx backend/tests/integration/test_ai_tree_import_api.py
git commit -m "feat: add AI tree import API endpoints (upload, confirm, poll, finalize)"
```

---

### Task 9: Frontend — types + upload/poll hook

**Files:**
- Create: `frontend/src/features/admin/aiTreeImport/types.ts`
- Create: `frontend/src/features/admin/aiTreeImport/useAiTreeImportJob.ts`
- Test: `frontend/src/__tests__/hooks/useAiTreeImportJob.test.ts`

**Interfaces:**
- Produces: `useAiTreeImportJob()` hook returning `{ status: 'idle'|'uploading'|'processing'|'ready'|'error', draft: ExtractedDraft | null, errorMessage: string | null, photoUrls: Record<string,string>, uploadScreenshot: (file: File) => Promise<void>, reset: () => void }`.

- [ ] **Step 1: Write the types**

```typescript
// frontend/src/features/admin/aiTreeImport/types.ts
export interface ExtractedPerson {
  id: string;
  display_given_name: string;
  display_surname: string;
  sex: 'MALE' | 'FEMALE' | 'OTHER' | 'UNKNOWN';
}

export interface ExtractedFamilyGroup {
  id: string;
  union_type: 'MARRIAGE' | 'PARTNERSHIP' | 'COHABITATION' | 'UNKNOWN';
  parent_ids: string[];
  children: Record<string, string>;
}

export interface ExtractedDraft {
  persons: ExtractedPerson[];
  family_groups: ExtractedFamilyGroup[];
}

export interface UploadUrlResponse {
  job_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  max_size_bytes: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED';
  processing_error: string | null;
  persons: ExtractedPerson[] | null;
  family_groups: ExtractedFamilyGroup[] | null;
  photo_urls: Record<string, string>;
}
```

- [ ] **Step 2: Write the failing hook test**

```typescript
// frontend/src/__tests__/hooks/useAiTreeImportJob.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAiTreeImportJob } from '@features/admin/aiTreeImport/useAiTreeImportJob';
import { post } from '@api/client';

vi.mock('@api/client', () => ({ post: vi.fn() }));

describe('useAiTreeImportJob', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    global.XMLHttpRequest = vi.fn(() => ({
      open: vi.fn(),
      send: vi.fn(function (this: any) {
        this.status = 200;
        this.onload();
      }),
      upload: {},
    })) as any;
  });

  it('walks through uploading -> processing -> ready', async () => {
    (post as any).mockImplementation((url: string) => {
      if (url === '/admin/ai-tree-import/upload-url') {
        return Promise.resolve({
          job_id: 'job-1', upload_url: 'https://s3.example/', upload_fields: {}, max_size_bytes: 1000,
        });
      }
      if (url === '/admin/ai-tree-import/job-1/confirm') {
        return Promise.resolve({ job_id: 'job-1', status: 'PROCESSING' });
      }
      return Promise.reject(new Error(`unexpected post ${url}`));
    });
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({
        job_id: 'job-1', status: 'READY', processing_error: null,
        persons: [{ id: 'p1', display_given_name: 'A', display_surname: 'B', sex: 'MALE' }],
        family_groups: [], photo_urls: {},
      }),
    });

    const { result } = renderHook(() => useAiTreeImportJob());

    await act(async () => {
      await result.current.uploadScreenshot(new File(['x'], 'shot.jpg', { type: 'image/jpeg' }));
    });

    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.draft?.persons[0].display_given_name).toBe('A');
  });

  it('surfaces a FAILED job as an error', async () => {
    (post as any).mockImplementation((url: string) => {
      if (url === '/admin/ai-tree-import/upload-url') {
        return Promise.resolve({
          job_id: 'job-2', upload_url: 'https://s3.example/', upload_fields: {}, max_size_bytes: 1000,
        });
      }
      if (url === '/admin/ai-tree-import/job-2/confirm') {
        return Promise.resolve({ job_id: 'job-2', status: 'PROCESSING' });
      }
      return Promise.reject(new Error('unexpected'));
    });
    (global.fetch as any).mockResolvedValue({
      json: () => Promise.resolve({
        job_id: 'job-2', status: 'FAILED', processing_error: 'vision call failed',
        persons: null, family_groups: null, photo_urls: {},
      }),
    });

    const { result } = renderHook(() => useAiTreeImportJob());
    await act(async () => {
      await result.current.uploadScreenshot(new File(['x'], 'shot.jpg', { type: 'image/jpeg' }));
    });

    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.errorMessage).toBe('vision call failed');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/hooks/useAiTreeImportJob.test.ts`
Expected: FAIL with a module-not-found error for `@features/admin/aiTreeImport/useAiTreeImportJob`

- [ ] **Step 4: Implement the hook**

Model this directly on `frontend/src/features/media/useMediaUpload.ts` (already read in full during planning) — same 3-step upload + interval-poll shape, adapted to the AI-import endpoints and a single in-flight job instead of a list.

```typescript
// frontend/src/features/admin/aiTreeImport/useAiTreeImportJob.ts
/**
 * useAiTreeImportJob — drives one admin AI-screenshot-import job:
 *   1. POST /admin/ai-tree-import/upload-url  → presigned POST ticket
 *   2. POST <presigned_url>                   → direct S3 upload
 *   3. POST /admin/ai-tree-import/{id}/confirm → triggers Celery extraction
 * Then polls GET /admin/ai-tree-import/{id} until READY or FAILED.
 */
import { useCallback, useRef, useState } from 'react';
import { post } from '@api/client';
import type { ExtractedDraft, JobStatusResponse, UploadUrlResponse } from './types';

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 3 * 60 * 1_000; // 3 minutes

export type AiImportStatus = 'idle' | 'uploading' | 'processing' | 'ready' | 'error';

export function useAiTreeImportJob() {
  const [status, setStatus] = useState<AiImportStatus>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ExtractedDraft | null>(null);
  const [photoUrls, setPhotoUrls] = useState<Record<string, string>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const xhrUpload = useCallback((ticket: UploadUrlResponse, file: File): Promise<void> =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      Object.entries(ticket.upload_fields).forEach(([k, v]) => form.append(k, v));
      form.append('file', file);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', ticket.upload_url);
      xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 upload failed: HTTP ${xhr.status}`)));
      xhr.onerror = () => reject(new Error('S3 upload network error'));
      xhr.send(form);
    }), []);

  const pollUntilDone = useCallback((id: string) => {
    const started = Date.now();
    pollTimer.current = setInterval(async () => {
      if (Date.now() - started > POLL_TIMEOUT_MS) {
        stopPolling();
        setStatus('error');
        setErrorMessage('Extraction timed out.');
        return;
      }
      try {
        const res = await fetch(`/api/v1/admin/ai-tree-import/${id}`, { credentials: 'include' });
        const job: JobStatusResponse = await res.json();
        if (job.status === 'READY') {
          stopPolling();
          setDraft({ persons: job.persons ?? [], family_groups: job.family_groups ?? [] });
          setPhotoUrls(job.photo_urls);
          setStatus('ready');
        } else if (job.status === 'FAILED') {
          stopPolling();
          setErrorMessage(job.processing_error ?? 'Extraction failed.');
          setStatus('error');
        }
      } catch {
        // transient network error — keep polling
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling]);

  const uploadScreenshot = useCallback(async (file: File): Promise<void> => {
    setStatus('uploading');
    setErrorMessage(null);
    try {
      const ticket = await post<UploadUrlResponse>('/admin/ai-tree-import/upload-url', {
        content_type: file.type,
        file_size_bytes: file.size,
      });
      setJobId(ticket.job_id);
      await xhrUpload(ticket, file);
      await post(`/admin/ai-tree-import/${ticket.job_id}/confirm`);
      setStatus('processing');
      pollUntilDone(ticket.job_id);
    } catch (err) {
      setStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Upload failed.');
    }
  }, [xhrUpload, pollUntilDone]);

  const reset = useCallback(() => {
    stopPolling();
    setStatus('idle');
    setJobId(null);
    setDraft(null);
    setPhotoUrls({});
    setErrorMessage(null);
  }, [stopPolling]);

  return { status, jobId, draft, photoUrls, errorMessage, uploadScreenshot, reset };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/hooks/useAiTreeImportJob.test.ts`
Expected: PASS (both cases)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/admin/aiTreeImport/types.ts frontend/src/features/admin/aiTreeImport/useAiTreeImportJob.ts frontend/src/__tests__/hooks/useAiTreeImportJob.test.ts
git commit -m "feat: add useAiTreeImportJob upload/poll hook"
```

---

### Task 10: Frontend — review panel + finalize

**Files:**
- Create: `frontend/src/features/admin/aiTreeImport/AiTreeImportPanel.tsx`
- Test: `frontend/src/__tests__/components/AiTreeImportPanel.test.tsx`

**Interfaces:**
- Consumes: `useAiTreeImportJob` (Task 9), `ExtractedDraft`/`ExtractedPerson`/`ExtractedFamilyGroup` types (Task 9).
- Produces: `<AiTreeImportPanel />` — self-contained: file picker → upload/processing states → editable review table (name/sex per person, delete; parent/children per family group) → "Create Tree" button calling `POST /admin/ai-tree-import/{jobId}/finalize` → success message with a link to the new tree at `/trees/{tree_id}`.

- [ ] **Step 1: Write the failing component test**

```typescript
// frontend/src/__tests__/components/AiTreeImportPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AiTreeImportPanel } from '@features/admin/aiTreeImport/AiTreeImportPanel';
import { useAiTreeImportJob } from '@features/admin/aiTreeImport/useAiTreeImportJob';
import { post } from '@api/client';

vi.mock('@features/admin/aiTreeImport/useAiTreeImportJob');
vi.mock('@api/client', () => ({ post: vi.fn() }));

describe('AiTreeImportPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the editable draft once the job is ready and finalizes it', async () => {
    (useAiTreeImportJob as any).mockReturnValue({
      status: 'ready',
      jobId: 'job-1',
      draft: {
        persons: [{ id: 'p1', display_given_name: 'Jane', display_surname: 'Doe', sex: 'FEMALE' }],
        family_groups: [],
      },
      photoUrls: {},
      errorMessage: null,
      uploadScreenshot: vi.fn(),
      reset: vi.fn(),
    });
    (post as any).mockResolvedValue({ tree_id: 'tree-1', tree_name: 'From Screenshot' });

    render(<AiTreeImportPanel />);

    expect(screen.getByDisplayValue('Jane')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /create tree/i }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/admin/ai-tree-import/job-1/finalize',
        expect.objectContaining({ persons: expect.arrayContaining([expect.objectContaining({ display_given_name: 'Jane' })]) })
      )
    );
    expect(await screen.findByText(/from screenshot/i)).toBeInTheDocument();
  });

  it('shows the error message when the job fails', () => {
    (useAiTreeImportJob as any).mockReturnValue({
      status: 'error', jobId: null, draft: null, photoUrls: {},
      errorMessage: 'Vision API call failed', uploadScreenshot: vi.fn(), reset: vi.fn(),
    });

    render(<AiTreeImportPanel />);
    expect(screen.getByText('Vision API call failed')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/__tests__/components/AiTreeImportPanel.test.tsx`
Expected: FAIL — module not found for `AiTreeImportPanel`

- [ ] **Step 3: Implement the panel**

```tsx
// frontend/src/features/admin/aiTreeImport/AiTreeImportPanel.tsx
import React, { useState } from 'react';
import { post } from '@api/client';
import { useAiTreeImportJob } from './useAiTreeImportJob';
import type { ExtractedFamilyGroup, ExtractedPerson } from './types';

export function AiTreeImportPanel() {
  const { status, jobId, draft, photoUrls, errorMessage, uploadScreenshot, reset } = useAiTreeImportJob();
  const [persons, setPersons] = useState<ExtractedPerson[]>([]);
  const [familyGroups, setFamilyGroups] = useState<ExtractedFamilyGroup[]>([]);
  const [treeName, setTreeName] = useState('Imported Tree');
  const [finalizeResult, setFinalizeResult] = useState<{ tree_id: string; tree_name: string } | null>(null);
  const [finalizing, setFinalizing] = useState(false);

  React.useEffect(() => {
    if (status === 'ready' && draft) {
      setPersons(draft.persons);
      setFamilyGroups(draft.family_groups);
    }
  }, [status, draft]);

  function updatePerson(id: string, patch: Partial<ExtractedPerson>) {
    setPersons((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  function removePerson(id: string) {
    setPersons((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleFinalize() {
    if (!jobId) return;
    setFinalizing(true);
    try {
      const result = await post<{ tree_id: string; tree_name: string }>(
        `/admin/ai-tree-import/${jobId}/finalize`,
        { tree_name: treeName, persons, family_groups: familyGroups },
      );
      setFinalizeResult(result);
    } finally {
      setFinalizing(false);
    }
  }

  if (finalizeResult) {
    return (
      <div>
        <p>Tree "{finalizeResult.tree_name}" created.</p>
        <a href={`/trees/${finalizeResult.tree_id}`}>Open tree</a>
        <button onClick={reset}>Import another screenshot</button>
      </div>
    );
  }

  if (status === 'idle') {
    return (
      <div>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => e.target.files?.[0] && uploadScreenshot(e.target.files[0])}
        />
      </div>
    );
  }

  if (status === 'uploading' || status === 'processing') {
    return <p>{status === 'uploading' ? 'Uploading screenshot…' : 'Extracting family tree…'}</p>;
  }

  if (status === 'error') {
    return (
      <div>
        <p>{errorMessage}</p>
        <button onClick={reset}>Try again</button>
      </div>
    );
  }

  return (
    <div>
      <label>
        Tree name
        <input value={treeName} onChange={(e) => setTreeName(e.target.value)} />
      </label>

      <h3>People ({persons.length})</h3>
      {persons.map((p) => (
        <div key={p.id}>
          {photoUrls[p.id] && <img src={photoUrls[p.id]} alt="" width={48} height={48} />}
          <input
            value={p.display_given_name}
            onChange={(e) => updatePerson(p.id, { display_given_name: e.target.value })}
          />
          <input
            value={p.display_surname}
            onChange={(e) => updatePerson(p.id, { display_surname: e.target.value })}
          />
          <select value={p.sex} onChange={(e) => updatePerson(p.id, { sex: e.target.value as ExtractedPerson['sex'] })}>
            <option value="MALE">Male</option>
            <option value="FEMALE">Female</option>
            <option value="OTHER">Other</option>
            <option value="UNKNOWN">Unknown</option>
          </select>
          <button onClick={() => removePerson(p.id)}>Remove</button>
        </div>
      ))}

      <h3>Family groups ({familyGroups.length})</h3>
      {familyGroups.map((fg) => (
        <div key={fg.id}>
          {fg.parent_ids.join(' & ')} → {Object.keys(fg.children).join(', ') || '(no children)'}
        </div>
      ))}

      <button onClick={handleFinalize} disabled={finalizing}>
        {finalizing ? 'Creating…' : 'Create Tree'}
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/__tests__/components/AiTreeImportPanel.test.tsx`
Expected: PASS (both cases)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/admin/aiTreeImport/AiTreeImportPanel.tsx frontend/src/__tests__/components/AiTreeImportPanel.test.tsx
git commit -m "feat: add AI tree import review/finalize panel"
```

---

### Task 11: Wire the panel into the Admin dashboard

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`
- Modify: `frontend/src/i18n/locales/en.ts`
- Modify: `frontend/src/i18n/locales/ne.ts`

**Interfaces:**
- Consumes: `<AiTreeImportPanel />` (Task 10).

- [ ] **Step 1: Add the i18n strings**

Edit `frontend/src/i18n/locales/en.ts`, inside `adminPage.tabs` (see the block at line ~965-975):

```typescript
      subscriptions: 'Subscriptions',
      broadcast: 'Broadcast',
      aiTreeImport: 'AI Tree Import',
```

Edit `frontend/src/i18n/locales/ne.ts` at the matching `adminPage.tabs` location — read the existing Nepali translations for `subscriptions`/`broadcast` there first, then add a `aiTreeImport` key in the same style (a short Nepali label for "AI Tree Import"; if uncertain of an idiomatic phrase, use a transliteration consistent with how this file already handles other English product-feature names — check how e.g. `broadcast` was translated there for the precedent to follow).

- [ ] **Step 2: Add the tab**

Edit `frontend/src/pages/AdminPage.tsx`:

1. Add the import near the top with the other feature imports:

```typescript
import { AiTreeImportPanel } from '@features/admin/aiTreeImport/AiTreeImportPanel';
```

2. Extend the `activeTab` union type (line 2953):

```typescript
const [activeTab, setActiveTab] = useState<'users' | 'permissions' | 'user-groups' | 'merge' | 'global' | 'subscriptions' | 'broadcast' | 'site' | 'namespaces' | 'ai-tree-import'>('users');
```

3. Add the tab entry next to the other tab-label pairs (near line 3084-3085):

```typescript
            ['ai-tree-import', t('adminPage.tabs.aiTreeImport')] as const,
```

4. Add the conditional render next to `SubscriptionsPanel`/`BroadcastPanel` (near line 3108-3109) — gated on `isAdmin` (both ADMIN and SUPER_ADMIN may use the feature; the paid-tier check happens server-side and the panel surfaces a 403 as its error state):

```typescript
      {activeTab === 'ai-tree-import' && (isSuperAdmin || currentUser?.appRole === 'ADMIN') && <AiTreeImportPanel />}
```

`AdminPage.tsx:2952` only defines `const isSuperAdmin = currentUser?.appRole === 'SUPER_ADMIN';` — there is no existing `isAdmin` boolean in this component. Use `(isSuperAdmin || currentUser?.appRole === 'ADMIN')` inline as the render guard, matching how `AdminGateway.tsx:40` checks the same "Admin or Super Admin" condition.

- [ ] **Step 3: Manually verify in the browser**

Run the dev server (`cd frontend && npm run dev`), log in as a user with `app_role=ADMIN` and an active `PREMIUM_INDIVIDUAL`/`PREMIUM_TEAM` subscription membership, open `/admin`, select the "AI Tree Import" tab, and confirm:
- The file picker appears.
- Uploading a real family-tree screenshot moves through "Uploading…" → "Extracting…" → the review table.
- Editing a name/sex in the review table is reflected before finalizing.
- "Create Tree" navigates to a real, editable tree with the extracted people and photos.
- Logging in as a non-paid Admin and opening the tab shows the 403 error message instead.

This step has no automated test — record the outcome in the task's completion notes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminPage.tsx frontend/src/i18n/locales/en.ts frontend/src/i18n/locales/ne.ts
git commit -m "feat: wire AI Tree Import panel into the Admin dashboard"
```

---

## Post-plan follow-ups (not part of this plan, noted per the spec's Scope section)

- Per-tenant rate/cost cap on Anthropic API usage.
- Cleanup task for abandoned `ai_tree_import_jobs` rows / orphaned staging S3 objects (jobs left `PENDING`/`PROCESSING` because the admin never returned), modeled on `subscription_tasks.py`'s beat-scheduled reminder task.
- Manual QA against a handful of real screenshots (including a busy multi-generation chart) before this ships to real admins — vision extraction accuracy cannot be unit-tested.
