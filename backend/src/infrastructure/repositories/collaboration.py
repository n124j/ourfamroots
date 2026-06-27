"""Repositories for collaboration entities."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.collaboration.entities import (
    TreeMembership, Invitation, AuditEntry, PersonVersion,
    TreeRole, InvitationStatus, Action, AuditEntityType,
)
from src.infrastructure.database.models.collaboration import (
    TreeMemberModel, InvitationModel, AuditLogModel, PersonVersionModel,
)


# ── Mapper helpers ─────────────────────────────────────────────────────────────

def _member_to_domain(m: TreeMemberModel) -> TreeMembership:
    return TreeMembership(
        id=m.id,
        tree_id=m.tree_id,
        user_id=m.user_id,
        tenant_id=m.tenant_id,
        role=TreeRole(m.role),
        invited_by_id=m.invited_by_id,
        joined_at=m.joined_at,
    )

def _invitation_to_domain(i: InvitationModel) -> Invitation:
    from dataclasses import fields as dc_fields
    return Invitation(
        id=i.id,
        tree_id=i.tree_id,
        tenant_id=i.tenant_id,
        inviter_id=i.inviter_id,
        invitee_email=i.invitee_email,
        role=TreeRole(i.role),
        token=i.token,
        status=InvitationStatus(i.status),
        expires_at=i.expires_at,
        created_at=i.created_at,
        accepted_at=i.accepted_at,
        message=i.message,
    )

def _audit_to_domain(a: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        id=a.id,
        tree_id=a.tree_id,
        tenant_id=a.tenant_id,
        actor_id=a.actor_id,
        actor_display_name=a.actor_display_name,
        action=Action(a.action),
        entity_type=AuditEntityType(a.entity_type),
        entity_id=a.entity_id,
        entity_display_name=a.entity_display_name,
        before=a.before,
        after=a.after,
        ip_address=a.ip_address,
        occurred_at=a.occurred_at,
        metadata=a.metadata_,
    )

def _version_to_domain(v: PersonVersionModel) -> PersonVersion:
    return PersonVersion(
        id=v.id,
        person_id=v.person_id,
        tree_id=v.tree_id,
        tenant_id=v.tenant_id,
        version_number=v.version_number,
        snapshot=v.snapshot,
        audit_entry_id=v.audit_entry_id,
        created_by_id=v.created_by_id,
        created_at=v.created_at,
        change_summary=v.change_summary,
    )


# ── Tree Member Repository ─────────────────────────────────────────────────────

class TreeMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tree_id: uuid.UUID, user_id: uuid.UUID) -> Optional[TreeMembership]:
        result = await self._session.execute(
            select(TreeMemberModel).where(
                TreeMemberModel.tree_id == tree_id,
                TreeMemberModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return _member_to_domain(row) if row else None

    async def list_by_tree(self, tree_id: uuid.UUID) -> list[TreeMembership]:
        result = await self._session.execute(
            select(TreeMemberModel).where(TreeMemberModel.tree_id == tree_id)
        )
        return [_member_to_domain(r) for r in result.scalars().all()]

    async def list_by_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[TreeMembership]:
        result = await self._session.execute(
            select(TreeMemberModel).where(
                TreeMemberModel.user_id == user_id,
                TreeMemberModel.tenant_id == tenant_id,
            )
        )
        return [_member_to_domain(r) for r in result.scalars().all()]

    async def add(self, membership: TreeMembership) -> TreeMembership:
        model = TreeMemberModel(
            id=membership.id,
            tree_id=membership.tree_id,
            user_id=membership.user_id,
            tenant_id=membership.tenant_id,
            role=membership.role.value,
            invited_by_id=membership.invited_by_id,
            joined_at=membership.joined_at or datetime.now(timezone.utc),
        )
        self._session.add(model)
        await self._session.flush()
        return membership

    async def update_role(
        self, tree_id: uuid.UUID, user_id: uuid.UUID, new_role: TreeRole
    ) -> None:
        await self._session.execute(
            update(TreeMemberModel)
            .where(
                TreeMemberModel.tree_id == tree_id,
                TreeMemberModel.user_id == user_id,
            )
            .values(role=new_role.value)
        )

    async def remove(self, tree_id: uuid.UUID, user_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(TreeMemberModel).where(
                TreeMemberModel.tree_id == tree_id,
                TreeMemberModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)

    async def count(self, tree_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(TreeMemberModel.tree_id == tree_id)
        )
        return result.scalar_one()


# ── Invitation Repository ──────────────────────────────────────────────────────

class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_token(self, token: str) -> Optional[Invitation]:
        result = await self._session.execute(
            select(InvitationModel).where(InvitationModel.token == token)
        )
        row = result.scalar_one_or_none()
        return _invitation_to_domain(row) if row else None

    async def get_by_id(self, invitation_id: uuid.UUID) -> Optional[Invitation]:
        result = await self._session.execute(
            select(InvitationModel).where(InvitationModel.id == invitation_id)
        )
        row = result.scalar_one_or_none()
        return _invitation_to_domain(row) if row else None

    async def list_by_tree(self, tree_id: uuid.UUID) -> list[Invitation]:
        result = await self._session.execute(
            select(InvitationModel)
            .where(InvitationModel.tree_id == tree_id)
            .order_by(InvitationModel.created_at.desc())
        )
        return [_invitation_to_domain(r) for r in result.scalars().all()]

    async def add(self, invitation: Invitation) -> Invitation:
        model = InvitationModel(
            id=invitation.id,
            tree_id=invitation.tree_id,
            tenant_id=invitation.tenant_id,
            inviter_id=invitation.inviter_id,
            invitee_email=invitation.invitee_email,
            role=invitation.role.value,
            token=invitation.token,
            status=invitation.status.value,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            message=invitation.message,
        )
        self._session.add(model)
        await self._session.flush()
        return invitation

    async def update_status(
        self,
        invitation_id: uuid.UUID,
        status: InvitationStatus,
        accepted_at: Optional[datetime] = None,
    ) -> None:
        values: dict = {"status": status.value}
        if accepted_at:
            values["accepted_at"] = accepted_at
        await self._session.execute(
            update(InvitationModel)
            .where(InvitationModel.id == invitation_id)
            .values(**values)
        )

    async def expire_old(self, tree_id: uuid.UUID) -> int:
        """Mark all expired PENDING invitations as EXPIRED. Returns count."""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            update(InvitationModel)
            .where(
                InvitationModel.tree_id == tree_id,
                InvitationModel.status == InvitationStatus.PENDING.value,
                InvitationModel.expires_at < now,
            )
            .values(status=InvitationStatus.EXPIRED.value)
        )
        return result.rowcount  # type: ignore[return-value]


# ── Audit Log Repository ───────────────────────────────────────────────────────

class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditEntry) -> None:
        model = AuditLogModel(
            id=entry.id,
            tree_id=entry.tree_id,
            tenant_id=entry.tenant_id,
            actor_id=entry.actor_id,
            actor_display_name=entry.actor_display_name,
            action=entry.action.value,
            entity_type=entry.entity_type.value,
            entity_id=entry.entity_id,
            entity_display_name=entry.entity_display_name,
            before=entry.before,
            after=entry.after,
            ip_address=entry.ip_address,
            occurred_at=entry.occurred_at,
            metadata_=entry.metadata,
        )
        self._session.add(model)
        await self._session.flush()

    async def list_by_tree(
        self,
        tree_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        entity_type: Optional[AuditEntityType] = None,
        entity_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> list[AuditEntry]:
        q = (
            select(AuditLogModel)
            .where(AuditLogModel.tree_id == tree_id)
            .order_by(AuditLogModel.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if entity_type:
            q = q.where(AuditLogModel.entity_type == entity_type.value)
        if entity_id:
            q = q.where(AuditLogModel.entity_id == entity_id)
        if actor_id:
            q = q.where(AuditLogModel.actor_id == actor_id)

        result = await self._session.execute(q)
        return [_audit_to_domain(r) for r in result.scalars().all()]

    async def count_by_tree(self, tree_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).where(AuditLogModel.tree_id == tree_id)
        )
        return result.scalar_one()


# ── Person Version Repository ──────────────────────────────────────────────────

class PersonVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_person(
        self, person_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> list[PersonVersion]:
        result = await self._session.execute(
            select(PersonVersionModel)
            .where(PersonVersionModel.person_id == person_id)
            .order_by(PersonVersionModel.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_version_to_domain(r) for r in result.scalars().all()]

    async def get_version(
        self, person_id: uuid.UUID, version_number: int
    ) -> Optional[PersonVersion]:
        result = await self._session.execute(
            select(PersonVersionModel).where(
                PersonVersionModel.person_id == person_id,
                PersonVersionModel.version_number == version_number,
            )
        )
        row = result.scalar_one_or_none()
        return _version_to_domain(row) if row else None

    async def next_version_number(self, person_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(PersonVersionModel.version_number), 0))
            .where(PersonVersionModel.person_id == person_id)
        )
        return result.scalar_one() + 1

    async def append(self, version: PersonVersion) -> PersonVersion:
        model = PersonVersionModel(
            id=version.id,
            person_id=version.person_id,
            tree_id=version.tree_id,
            tenant_id=version.tenant_id,
            version_number=version.version_number,
            snapshot=version.snapshot,
            audit_entry_id=version.audit_entry_id,
            created_by_id=version.created_by_id,
            created_at=version.created_at,
            change_summary=version.change_summary,
        )
        self._session.add(model)
        await self._session.flush()
        return version
