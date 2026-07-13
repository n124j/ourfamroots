"""Unit tests for the FastAPI dependency functions that gate admin-only
endpoints (src/api/deps.py) — in particular SuperAdminDep, which is the sole
authorization check on POST .../change-requests/{id}/revert. There's no
in-body role check on that endpoint; it relies entirely on this dependency
running before the handler, so it's worth covering in isolation.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.deps import require_admin, require_namespace_owner_or_super_admin, require_super_admin


def _user(app_role: str, tenant_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), app_role=app_role, email_verified=True,
        tenant_id=tenant_id or uuid.uuid4(),
    )


class TestRequireSuperAdmin:
    @pytest.mark.asyncio
    async def test_super_admin_passes(self):
        user = _user("SUPER_ADMIN")
        assert await require_super_admin(user) is user

    @pytest.mark.asyncio
    @pytest.mark.parametrize("app_role", ["ADMIN", "STANDARD", "AUDITOR"])
    async def test_non_super_admin_rejected(self, app_role: str):
        with pytest.raises(HTTPException) as exc_info:
            await require_super_admin(_user(app_role))
        assert exc_info.value.status_code == 403


class TestRequireAdmin:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("app_role", ["ADMIN", "SUPER_ADMIN"])
    async def test_admin_or_super_admin_passes(self, app_role: str):
        user = _user(app_role)
        assert await require_admin(user) is user

    @pytest.mark.asyncio
    @pytest.mark.parametrize("app_role", ["STANDARD", "AUDITOR"])
    async def test_non_admin_rejected(self, app_role: str):
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(_user(app_role))
        assert exc_info.value.status_code == 403


class TestRequireNamespaceOwnerOrSuperAdmin:
    """Gates POST/DELETE .../admin/namespaces/{namespace_id}/invitations."""

    @pytest.mark.asyncio
    async def test_super_admin_passes_for_any_namespace(self):
        namespace_id = uuid.uuid4()
        user = _user("SUPER_ADMIN")  # tenant_id deliberately different from namespace_id
        result = await require_namespace_owner_or_super_admin(namespace_id, user)
        assert result is user

    @pytest.mark.asyncio
    async def test_admin_of_target_namespace_passes(self):
        namespace_id = uuid.uuid4()
        user = _user("ADMIN", tenant_id=namespace_id)
        result = await require_namespace_owner_or_super_admin(namespace_id, user)
        assert result is user

    @pytest.mark.asyncio
    async def test_admin_of_a_different_namespace_rejected(self):
        namespace_id = uuid.uuid4()
        user = _user("ADMIN", tenant_id=uuid.uuid4())  # not the target namespace
        with pytest.raises(HTTPException) as exc_info:
            await require_namespace_owner_or_super_admin(namespace_id, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("app_role", ["STANDARD", "AUDITOR"])
    async def test_non_admin_rejected_even_in_own_namespace(self, app_role: str):
        namespace_id = uuid.uuid4()
        user = _user(app_role, tenant_id=namespace_id)
        with pytest.raises(HTTPException) as exc_info:
            await require_namespace_owner_or_super_admin(namespace_id, user)
        assert exc_info.value.status_code == 403
