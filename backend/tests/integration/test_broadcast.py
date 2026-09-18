"""Real-database integration tests for the admin Broadcast Email feature
(src/api/v1/broadcast.py).

Follows the same real-Postgres, direct-function-call pattern as
test_site_banner.py (requires TEST_DATABASE_URL; skipped otherwise).

Focuses on the async-queueing behavior: POST /broadcast/send must return
immediately with a queued marker (not final sent/failed counts), write the
BroadcastLogModel row up front with zero counts, and hand off the actual
SMTP sending to a Celery task. Sending itself (SMTP, the task body) is
Celery/infrastructure territory and is intentionally not covered here, the
same way src/infrastructure/media/*.py's task bodies aren't unit-tested in
this codebase (see .coveragerc).
"""
from __future__ import annotations

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
        "database (see test_dashboard_hide_tree.py for local setup). Skipping.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    await engine.dispose()


def _user(uid: uuid.UUID, tenant_id: uuid.UUID, email: str, app_role: str = "STANDARD") -> SimpleNamespace:
    given = email.split("@")[0].title()
    return SimpleNamespace(
        id=uid, tenant_id=tenant_id, email=email,
        given_name=given, family_name="Test", full_name=f"{given} Test", app_role=app_role,
    )


def fake_request() -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


class Seed:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_id = uuid.uuid4()
        self.super_admin = _user(uuid.uuid4(), self.tenant_id, "root@example.com", app_role="SUPER_ADMIN")
        self.alice = _user(uuid.uuid4(), self.tenant_id, "alice@example.com")
        self.bob = _user(uuid.uuid4(), self.tenant_id, "bob@example.com")

    async def build(self) -> "Seed":
        s = self.session
        await s.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Test Tenant', :slug)"),
            {"id": self.tenant_id, "slug": f"test-{self.tenant_id.hex[:12]}"},
        )
        for u in (self.super_admin, self.alice, self.bob):
            await s.execute(
                text("""
                    INSERT INTO users (id, tenant_id, email, email_verified, is_active,
                                        broadcast_unsubscribed, app_role, given_name, family_name)
                    VALUES (:id, :tenant, :email, true, true, false, :role, :given, :family)
                """),
                {"id": u.id, "tenant": u.tenant_id, "email": u.email, "role": u.app_role,
                 "given": u.given_name, "family": u.family_name},
            )
        await s.commit()
        return self


@pytest_asyncio.fixture
async def seed(session: AsyncSession) -> Seed:
    return await Seed(session).build()


class TestSendBroadcastQueuesInsteadOfBlocking:
    @pytest.mark.asyncio
    async def test_returns_queued_marker_not_send_counts(self, seed: Seed, monkeypatch):
        from src.api.v1.broadcast import send_broadcast, BroadcastRequest
        from src.infrastructure.broadcast.broadcast_tasks import send_broadcast_task

        monkeypatch.setattr(send_broadcast_task, "delay", lambda **kwargs: None)

        result = await send_broadcast(
            BroadcastRequest(subject="Hello", body="World", category="notice"),
            fake_request(), seed.super_admin, seed.session,
        )

        assert not hasattr(result, "sent_count")
        assert not hasattr(result, "failed_count")
        assert result.recipient_count == 3  # super_admin, alice, bob — all eligible
        assert isinstance(result.log_id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_writes_log_row_immediately_with_zero_counts(self, seed: Seed, monkeypatch):
        from src.api.v1.broadcast import send_broadcast, BroadcastRequest
        from src.infrastructure.broadcast.broadcast_tasks import send_broadcast_task
        from src.infrastructure.database.models.broadcast_log import BroadcastLogModel
        from sqlalchemy import select

        monkeypatch.setattr(send_broadcast_task, "delay", lambda **kwargs: None)

        result = await send_broadcast(
            BroadcastRequest(subject="Hello", body="World", category="notice"),
            fake_request(), seed.super_admin, seed.session,
        )

        row = (await seed.session.execute(
            select(BroadcastLogModel).where(BroadcastLogModel.id == result.log_id)
        )).scalar_one()
        assert row.sent_count == 0
        assert row.failed_count == 0
        assert row.recipient_count == 3
        assert set(row.recipient_emails) == {"root@example.com", "alice@example.com", "bob@example.com"}

    @pytest.mark.asyncio
    async def test_enqueues_celery_task_with_recipients_and_content(self, seed: Seed, monkeypatch):
        from src.api.v1.broadcast import send_broadcast, BroadcastRequest
        from src.infrastructure.broadcast.broadcast_tasks import send_broadcast_task

        captured = {}
        monkeypatch.setattr(
            send_broadcast_task, "delay",
            lambda **kwargs: captured.update(kwargs),
        )

        result = await send_broadcast(
            BroadcastRequest(subject="Hello", body="World", category="notice"),
            fake_request(), seed.super_admin, seed.session,
        )

        assert captured["log_id"] == str(result.log_id)
        assert captured["subject"] == "Hello"
        assert captured["body"] == "World"
        assert captured["category"] == "notice"
        recipient_emails = {r["email"] for r in captured["recipients"]}
        assert recipient_emails == {"root@example.com", "alice@example.com", "bob@example.com"}

    @pytest.mark.asyncio
    async def test_no_eligible_recipients_still_returns_400(self, seed: Seed):
        """Regression guard: unrelated existing behavior must survive the refactor."""
        from fastapi import HTTPException
        from src.api.v1.broadcast import send_broadcast, BroadcastRequest

        with pytest.raises(HTTPException) as exc_info:
            await send_broadcast(
                BroadcastRequest(subject="Hi", body="Body", category="notice", recipient_ids=[uuid.uuid4()]),
                fake_request(), seed.super_admin, seed.session,
            )
        assert exc_info.value.status_code == 400


class TestHistoryInProgressFlag:
    @pytest.mark.asyncio
    async def test_freshly_queued_broadcast_is_in_progress(self, seed: Seed, monkeypatch):
        from src.api.v1.broadcast import send_broadcast, list_history, BroadcastRequest
        from src.infrastructure.broadcast.broadcast_tasks import send_broadcast_task

        monkeypatch.setattr(send_broadcast_task, "delay", lambda **kwargs: None)

        await send_broadcast(
            BroadcastRequest(subject="Hello", body="World", category="notice"),
            fake_request(), seed.super_admin, seed.session,
        )

        history = await list_history(seed.super_admin, seed.session, page=1, page_size=10)
        assert history.items[0].in_progress is True

    @pytest.mark.asyncio
    async def test_completed_broadcast_is_not_in_progress(self, seed: Seed, monkeypatch):
        from src.api.v1.broadcast import send_broadcast, list_history, BroadcastRequest
        from src.infrastructure.broadcast.broadcast_tasks import send_broadcast_task
        from src.infrastructure.database.models.broadcast_log import BroadcastLogModel
        from sqlalchemy import select

        monkeypatch.setattr(send_broadcast_task, "delay", lambda **kwargs: None)

        result = await send_broadcast(
            BroadcastRequest(subject="Hello", body="World", category="notice"),
            fake_request(), seed.super_admin, seed.session,
        )

        row = (await seed.session.execute(
            select(BroadcastLogModel).where(BroadcastLogModel.id == result.log_id)
        )).scalar_one()
        row.sent_count = 3
        row.failed_count = 0
        await seed.session.commit()

        history = await list_history(seed.super_admin, seed.session, page=1, page_size=10)
        assert history.items[0].in_progress is False
