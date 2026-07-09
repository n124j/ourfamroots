"""Unit tests for CollaborationService.require_permission()'s app-role bypass.

AUDITOR and SUPER_ADMIN both bypass the tree_members lookup entirely — they
never touch the DB-backed membership repository — so these are pure unit
tests: no session, no DB. A dummy session object proves this (the bypass
branches must never dereference it).
"""
from __future__ import annotations

import uuid

import pytest

from src.application.collaboration.service import CollaborationService
from src.domain.collaboration.entities import Action, TreeRole
from src.domain.collaboration.exceptions import InsufficientPermissionError

TREE_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()


class _ExplodingSession:
    """Any attribute access/usage means a bypass branch leaked into real I/O."""

    def __getattr__(self, name):
        raise AssertionError(f"require_permission touched the session via .{name}() during a bypass")


class _NotAMemberRepo:
    """Simulates TreeMemberRepository.get() finding no membership row."""

    async def get(self, tree_id, actor_id):
        return None


@pytest.fixture
def svc() -> CollaborationService:
    return CollaborationService(_ExplodingSession())


class TestAuditorBypass:
    @pytest.mark.asyncio
    async def test_grants_synthetic_viewer_membership(self, svc: CollaborationService):
        membership = await svc.require_permission(TREE_ID, ACTOR_ID, Action.VIEW_AUDIT_LOG, app_role="AUDITOR")
        assert membership.role == TreeRole.VIEWER
        assert membership.tree_id == TREE_ID
        assert membership.user_id == ACTOR_ID

    @pytest.mark.asyncio
    async def test_viewer_role_cannot_perform_owner_only_action(self, svc: CollaborationService):
        """The synthetic membership is real — VIEWER still can't do owner-only things."""
        membership = await svc.require_permission(TREE_ID, ACTOR_ID, Action.VIEW_MEMBERS, app_role="AUDITOR")
        with pytest.raises(InsufficientPermissionError):
            membership.require(Action.DELETE_TREE)


class TestSuperAdminBypass:
    @pytest.mark.asyncio
    async def test_grants_synthetic_owner_membership(self, svc: CollaborationService):
        membership = await svc.require_permission(TREE_ID, ACTOR_ID, Action.DELETE_TREE, app_role="SUPER_ADMIN")
        assert membership.role == TreeRole.OWNER
        assert membership.tree_id == TREE_ID
        assert membership.user_id == ACTOR_ID

    @pytest.mark.asyncio
    async def test_owner_role_permits_owner_only_action(self, svc: CollaborationService):
        membership = await svc.require_permission(TREE_ID, ACTOR_ID, Action.VIEW_AUDIT_LOG, app_role="SUPER_ADMIN")
        membership.require(Action.DELETE_TREE)  # must not raise


class TestNoBypassForOtherAppRoles:
    """STANDARD and app-level ADMIN are not app_role bypass values here —
    they fall through to the real DB membership lookup, same as an
    unauthenticated tree role would."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("app_role", ["STANDARD", "ADMIN", None])
    async def test_falls_through_to_membership_lookup(self, app_role):
        svc = CollaborationService(object())
        svc._members = _NotAMemberRepo()
        with pytest.raises(InsufficientPermissionError):
            await svc.require_permission(TREE_ID, ACTOR_ID, Action.VIEW_AUDIT_LOG, app_role=app_role)
