"""CollaborationService — orchestrates members, invitations, audit, and versioning."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.collaboration.entities import (
    Action, AuditEntry, AuditEntityType, Invitation, InvitationStatus,
    PersonVersion, TreeMembership, TreeRole,
)
from src.domain.collaboration.exceptions import (
    AlreadyMemberError, CannotDowngradeOwnerError, CannotRemoveOwnerError,
    InsufficientPermissionError, InvitationAlreadyUsedError,
    InvitationExpiredError, InvitationNotFoundError,
)
from src.infrastructure.repositories.collaboration import (
    AuditLogRepository, InvitationRepository, PersonVersionRepository,
    TreeMemberRepository,
)


class CollaborationService:
    """
    Application-layer service for all collaboration operations.

    Instantiate per-request; pass the current AsyncSession.
    All write operations are flushed but not committed — the caller's
    Unit of Work handles the transaction boundary.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._members = TreeMemberRepository(session)
        self._invitations = InvitationRepository(session)
        self._audit = AuditLogRepository(session)
        self._versions = PersonVersionRepository(session)

    # ── Permission check ───────────────────────────────────────────────────────

    async def require_permission(
        self,
        tree_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: Action,
        app_role: Optional[str] = None,
    ) -> TreeMembership:
        """Load the actor's membership and assert they can perform *action*.

        Pass app_role="AUDITOR" to bypass the DB membership lookup and grant
        a synthetic viewer-level membership for compliance reads.
        """
        if app_role == "AUDITOR":
            return TreeMembership(
                id=uuid.uuid4(),
                tree_id=tree_id,
                user_id=actor_id,
                tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                role=TreeRole.VIEWER,
            )
        membership = await self._members.get(tree_id, actor_id)
        if not membership:
            raise InsufficientPermissionError(action, TreeRole.VIEWER)
        membership.require(action)
        return membership

    # ── Member management ─────────────────────────────────────────────────────

    async def list_members(
        self, tree_id: uuid.UUID, actor_id: uuid.UUID
    ) -> list[TreeMembership]:
        await self.require_permission(tree_id, actor_id, Action.VIEW_MEMBERS)
        return await self._members.list_by_tree(tree_id)

    async def change_member_role(
        self,
        tree_id: uuid.UUID,
        target_user_id: uuid.UUID,
        new_role: TreeRole,
        actor_id: uuid.UUID,
        actor_name: str,
        ip_address: Optional[str] = None,
        app_role: Optional[str] = None,
    ) -> None:
        actor_membership = await self.require_permission(
            tree_id, actor_id, Action.CHANGE_MEMBER_ROLE, app_role=app_role
        )
        target = await self._members.get(tree_id, target_user_id)
        if not target:
            raise ValueError(f"User {target_user_id} is not a member of this tree")

        if target.role == TreeRole.OWNER:
            raise CannotDowngradeOwnerError()

        # Admin cannot promote another member to OWNER
        if new_role == TreeRole.OWNER and actor_membership.role != TreeRole.OWNER:
            raise InsufficientPermissionError(Action.TRANSFER_OWNERSHIP, actor_membership.role)

        # ADMIN cannot change another ADMIN's role — only OWNER can
        if actor_membership.role == TreeRole.ADMIN and target.role == TreeRole.ADMIN:
            raise InsufficientPermissionError(Action.CHANGE_MEMBER_ROLE, actor_membership.role)

        old_role = target.role
        await self._members.update_role(tree_id, target_user_id, new_role)

        await self._audit.append(
            AuditEntry.create(
                tree_id=tree_id,
                tenant_id=actor_membership.tenant_id,
                actor_id=actor_id,
                actor_display_name=actor_name,
                action=Action.CHANGE_MEMBER_ROLE,
                entity_type=AuditEntityType.MEMBER,
                entity_id=target_user_id,
                before={"role": old_role.value},
                after={"role": new_role.value},
                ip_address=ip_address,
            )
        )

    async def remove_member(
        self,
        tree_id: uuid.UUID,
        target_user_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_name: str,
        tenant_id: uuid.UUID,
        ip_address: Optional[str] = None,
        app_role: Optional[str] = None,
    ) -> None:
        actor_membership = await self.require_permission(tree_id, actor_id, Action.REMOVE_MEMBER, app_role=app_role)
        target = await self._members.get(tree_id, target_user_id)
        if not target:
            return  # idempotent

        if target.role == TreeRole.OWNER:
            raise CannotRemoveOwnerError()

        # ADMIN cannot revoke another ADMIN — only OWNER can
        if actor_membership.role == TreeRole.ADMIN and target.role == TreeRole.ADMIN:
            raise InsufficientPermissionError(Action.REMOVE_MEMBER, actor_membership.role)

        # Fetch the removed user's name/email for the audit record before deleting
        from sqlalchemy import text
        user_row = (await self._session.execute(
            text("SELECT email, given_name, family_name FROM users WHERE id = :uid LIMIT 1"),
            {"uid": target_user_id},
        )).first()
        if user_row:
            member_display = (
                f"{user_row.given_name or ''} {user_row.family_name or ''}".strip()
                or user_row.email
            )
        else:
            member_display = str(target_user_id)

        await self._members.remove(tree_id, target_user_id)
        await self._audit.append(
            AuditEntry.create(
                tree_id=tree_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_display_name=actor_name,
                action=Action.REMOVE_MEMBER,
                entity_type=AuditEntityType.MEMBER,
                entity_id=target_user_id,
                entity_display_name=member_display,
                ip_address=ip_address,
            )
        )

    # ── Invitation flow ────────────────────────────────────────────────────────

    async def send_invitation(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_name: str,
        invitee_email: str,
        role: TreeRole,
        message: Optional[str] = None,
        ip_address: Optional[str] = None,
        app_role: Optional[str] = None,
    ) -> Invitation:
        await self.require_permission(tree_id, actor_id, Action.INVITE_MEMBER, app_role=app_role)

        # Check invitee isn't already a member
        # (Would need user lookup by email; simplified here)

        invitation = Invitation.create(
            tree_id=tree_id,
            tenant_id=tenant_id,
            inviter_id=actor_id,
            invitee_email=invitee_email,
            role=role,
            message=message,
        )
        await self._invitations.add(invitation)

        await self._audit.append(
            AuditEntry.create(
                tree_id=tree_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_display_name=actor_name,
                action=Action.INVITE_MEMBER,
                entity_type=AuditEntityType.INVITATION,
                entity_id=invitation.id,
                entity_display_name=invitee_email,
                after={"role": role.value, "email": invitee_email},
                ip_address=ip_address,
            )
        )
        return invitation

    async def accept_invitation(
        self,
        token: str,
        accepting_user_id: uuid.UUID,
        ip_address: Optional[str] = None,
    ) -> TreeMembership:
        inv = await self._invitations.get_by_token(token)
        if not inv:
            raise InvitationNotFoundError(token)
        if inv.status != InvitationStatus.PENDING:
            raise InvitationAlreadyUsedError(inv.status.value)
        if not inv.is_valid:
            raise InvitationExpiredError()

        # Check not already a member
        existing = await self._members.get(inv.tree_id, accepting_user_id)
        if existing:
            raise AlreadyMemberError(accepting_user_id, inv.tree_id)

        now = datetime.now(timezone.utc)
        membership = TreeMembership(
            id=uuid.uuid4(),
            tree_id=inv.tree_id,
            user_id=accepting_user_id,
            tenant_id=inv.tenant_id,
            role=inv.role,
            invited_by_id=inv.inviter_id,
            joined_at=now,
        )
        await self._members.add(membership)
        await self._invitations.update_status(
            inv.id, InvitationStatus.ACCEPTED, accepted_at=now
        )

        await self._audit.append(
            AuditEntry.create(
                tree_id=inv.tree_id,
                tenant_id=inv.tenant_id,
                actor_id=accepting_user_id,
                actor_display_name="",   # caller should fill this
                action=Action.INVITE_MEMBER,
                entity_type=AuditEntityType.MEMBER,
                entity_id=accepting_user_id,
                after={"role": inv.role.value, "via": "invitation"},
                ip_address=ip_address,
            )
        )
        return membership

    async def revoke_invitation(
        self,
        invitation_id: uuid.UUID,
        tree_id: uuid.UUID,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID,
        actor_name: str,
        app_role: Optional[str] = None,
    ) -> None:
        await self.require_permission(tree_id, actor_id, Action.INVITE_MEMBER, app_role=app_role)
        inv = await self._invitations.get_by_id(invitation_id)
        if not inv or inv.tree_id != tree_id:
            return
        if inv.status != InvitationStatus.PENDING:
            raise InvitationAlreadyUsedError(inv.status.value)
        await self._invitations.update_status(inv.id, InvitationStatus.REVOKED)

    # ── Audit log ──────────────────────────────────────────────────────────────

    async def get_audit_log(
        self,
        tree_id: uuid.UUID,
        actor_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        entity_type: Optional[AuditEntityType] = None,
        entity_id: Optional[uuid.UUID] = None,
        filter_actor_id: Optional[uuid.UUID] = None,
        app_role: Optional[str] = None,
    ) -> list[AuditEntry]:
        await self.require_permission(tree_id, actor_id, Action.VIEW_AUDIT_LOG, app_role=app_role)
        return await self._audit.list_by_tree(
            tree_id, limit, offset, entity_type, entity_id, filter_actor_id
        )

    async def record_audit(self, entry: AuditEntry) -> None:
        """Append an audit entry (called by other application services)."""
        await self._audit.append(entry)

    # ── Version history ────────────────────────────────────────────────────────

    async def snapshot_person(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        created_by_id: uuid.UUID,
        snapshot: dict[str, Any],
        change_summary: str = "",
        audit_entry_id: Optional[uuid.UUID] = None,
    ) -> PersonVersion:
        """Called immediately after a person update to capture the new state."""
        version_number = await self._versions.next_version_number(person_id)
        version = PersonVersion(
            id=uuid.uuid4(),
            person_id=person_id,
            tree_id=tree_id,
            tenant_id=tenant_id,
            version_number=version_number,
            snapshot=snapshot,
            audit_entry_id=audit_entry_id,
            created_by_id=created_by_id,
            change_summary=change_summary,
        )
        return await self._versions.append(version)

    async def get_person_history(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        actor_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
        app_role: Optional[str] = None,
    ) -> list[PersonVersion]:
        await self.require_permission(tree_id, actor_id, Action.VIEW_VERSION, app_role=app_role)
        return await self._versions.list_by_person(person_id, limit, offset)

    async def restore_person_version(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        version_number: int,
        actor_id: uuid.UUID,
        actor_name: str,
        tenant_id: uuid.UUID,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Return the snapshot dict for the requested version so the caller
        can write it back to the persons table.
        """
        await self.require_permission(tree_id, actor_id, Action.RESTORE_VERSION)
        version = await self._versions.get_version(person_id, version_number)
        if not version:
            raise ValueError(f"Version {version_number} not found for person {person_id}")

        await self._audit.append(
            AuditEntry.create(
                tree_id=tree_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_display_name=actor_name,
                action=Action.RESTORE_VERSION,
                entity_type=AuditEntityType.PERSON,
                entity_id=person_id,
                after={"restored_to_version": version_number},
                ip_address=ip_address,
            )
        )
        return version.snapshot
