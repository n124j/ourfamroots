"""Unit tests for RBAC permission matrix — exhaustive coverage of is_permitted()."""
from __future__ import annotations

import pytest

from src.domain.collaboration.entities import (
    ACTION_MIN_ROLE,
    ROLE_HIERARCHY,
    Action,
    TreeRole,
    is_permitted,
)


# ── Role hierarchy sanity ──────────────────────────────────────────────────────

class TestRoleHierarchy:
    def test_owner_is_highest(self):
        assert ROLE_HIERARCHY[TreeRole.OWNER] > ROLE_HIERARCHY[TreeRole.ADMIN]

    def test_admin_above_editor(self):
        assert ROLE_HIERARCHY[TreeRole.ADMIN] > ROLE_HIERARCHY[TreeRole.EDITOR]

    def test_editor_above_viewer(self):
        assert ROLE_HIERARCHY[TreeRole.EDITOR] > ROLE_HIERARCHY[TreeRole.VIEWER]

    def test_all_roles_have_hierarchy(self):
        for role in TreeRole:
            assert role in ROLE_HIERARCHY, f"{role} missing from ROLE_HIERARCHY"

    def test_all_actions_have_min_role(self):
        for action in Action:
            assert action in ACTION_MIN_ROLE, f"{action} missing from ACTION_MIN_ROLE"


# ── Owner can do everything ────────────────────────────────────────────────────

class TestOwnerPermissions:
    @pytest.mark.parametrize("action", list(Action))
    def test_owner_permitted_for_all_actions(self, action: Action):
        assert is_permitted(TreeRole.OWNER, action) is True


# ── Viewer cannot write ────────────────────────────────────────────────────────

class TestViewerPermissions:
    def test_viewer_can_view_person(self):
        assert is_permitted(TreeRole.VIEWER, Action.VIEW_PERSON) is True

    def test_viewer_cannot_create_person(self):
        assert is_permitted(TreeRole.VIEWER, Action.CREATE_PERSON) is False

    def test_viewer_cannot_delete_tree(self):
        assert is_permitted(TreeRole.VIEWER, Action.DELETE_TREE) is False

    def test_viewer_cannot_invite(self):
        assert is_permitted(TreeRole.VIEWER, Action.INVITE_MEMBER) is False


# ── Editor permissions ─────────────────────────────────────────────────────────

class TestEditorPermissions:
    def test_editor_can_create_person(self):
        assert is_permitted(TreeRole.EDITOR, Action.CREATE_PERSON) is True

    def test_editor_can_update_person(self):
        assert is_permitted(TreeRole.EDITOR, Action.UPDATE_PERSON) is True

    def test_editor_cannot_delete_tree(self):
        assert is_permitted(TreeRole.EDITOR, Action.DELETE_TREE) is False

    def test_editor_cannot_invite(self):
        assert is_permitted(TreeRole.EDITOR, Action.INVITE_MEMBER) is False


# ── Admin permissions ──────────────────────────────────────────────────────────

class TestAdminPermissions:
    def test_admin_can_invite(self):
        assert is_permitted(TreeRole.ADMIN, Action.INVITE_MEMBER) is True

    def test_admin_cannot_delete_tree(self):
        assert is_permitted(TreeRole.ADMIN, Action.DELETE_TREE) is False

    def test_admin_can_do_all_editor_actions(self):
        editor_actions = [a for a, r in ACTION_MIN_ROLE.items() if r == TreeRole.EDITOR]
        for action in editor_actions:
            assert is_permitted(TreeRole.ADMIN, action) is True, f"Admin denied {action}"


# ── App-admin-only actions ────────────────────────────────────────────────────

class TestAppAdminActions:
    """MERGE_TREES is an app-admin-only operation.
    It is mapped to TreeRole.OWNER so that is_permitted() returns False for
    every tree role including ADMIN — enforcement is done at the API layer via
    AdminUserDep, not via the tree-role permission matrix."""

    def test_merge_trees_requires_owner_mapping(self):
        from src.domain.collaboration.entities import ACTION_MIN_ROLE, TreeRole
        assert ACTION_MIN_ROLE[Action.MERGE_TREES] == TreeRole.OWNER

    def test_merge_trees_not_permitted_for_admin_role(self):
        assert is_permitted(TreeRole.ADMIN, Action.MERGE_TREES) is False

    def test_merge_trees_not_permitted_for_editor_role(self):
        assert is_permitted(TreeRole.EDITOR, Action.MERGE_TREES) is False

    def test_export_tree_permitted_for_editor(self):
        assert is_permitted(TreeRole.EDITOR, Action.EXPORT_TREE) is True

    def test_import_tree_permitted_for_editor(self):
        assert is_permitted(TreeRole.EDITOR, Action.IMPORT_TREE) is True

    def test_update_photo_permitted_for_editor(self):
        assert is_permitted(TreeRole.EDITOR, Action.UPDATE_PHOTO) is True

    def test_export_tree_not_permitted_for_viewer(self):
        assert is_permitted(TreeRole.VIEWER, Action.EXPORT_TREE) is False


# ── Monotonicity: higher role always has >= permissions ───────────────────────

class TestPermissionMonotonicity:
    @pytest.mark.parametrize("action", list(Action))
    def test_higher_role_never_loses_permission(self, action: Action):
        """If role R is permitted, all roles above R must also be permitted."""
        ordered = sorted(TreeRole, key=lambda r: ROLE_HIERARCHY[r])
        permitted_seen = False
        for role in ordered:
            if is_permitted(role, action):
                permitted_seen = True
            elif permitted_seen:
                pytest.fail(
                    f"Role {role} lost permission for {action} that a lower role had"
                )
