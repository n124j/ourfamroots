"""SqlAlchemy person + family group repositories."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, select

from src.infrastructure.database.models.person import (
    FamilyGroupMemberModel,
    FamilyGroupModel,
    PersonModel,
)
from src.infrastructure.repositories.base import SqlAlchemyRepository


class SqlAlchemyPersonRepository(SqlAlchemyRepository[PersonModel]):
    model_class = PersonModel

    async def get_by_tree(
        self,
        tenant_id: uuid.UUID,
        tree_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> list[PersonModel]:
        stmt = select(PersonModel).where(
            PersonModel.tenant_id == tenant_id,
            PersonModel.tree_id == tree_id,
        )
        if not include_deleted:
            stmt = stmt.where(PersonModel.is_deleted.is_(False))
        return await self._all(stmt)

    async def get_by_id_and_tree(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Optional[PersonModel]:
        stmt = select(PersonModel).where(
            PersonModel.id == person_id,
            PersonModel.tree_id == tree_id,
            PersonModel.tenant_id == tenant_id,
            PersonModel.is_deleted.is_(False),
        )
        return await self._first(stmt)


class SqlAlchemyFamilyGroupRepository(SqlAlchemyRepository[FamilyGroupModel]):
    model_class = FamilyGroupModel

    async def get_members(
        self,
        family_group_id: uuid.UUID,
    ) -> list[FamilyGroupMemberModel]:
        stmt = select(FamilyGroupMemberModel).where(
            FamilyGroupMemberModel.family_group_id == family_group_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_tree(
        self,
        tenant_id: uuid.UUID,
        tree_id: uuid.UUID,
    ) -> list[FamilyGroupModel]:
        stmt = select(FamilyGroupModel).where(
            FamilyGroupModel.tenant_id == tenant_id,
            FamilyGroupModel.tree_id == tree_id,
        )
        return await self._all(stmt)

    async def get_memberships_for_persons(
        self,
        person_ids: list[uuid.UUID],
    ) -> list[FamilyGroupMemberModel]:
        """Bulk-load all memberships for a set of persons — used by GraphLoader."""
        if not person_ids:
            return []
        stmt = select(FamilyGroupMemberModel).where(
            FamilyGroupMemberModel.person_id.in_(person_ids)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_member(
        self,
        family_group_id: uuid.UUID,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        role: str,
        parentage_type: str | None = None,
    ) -> FamilyGroupMemberModel:
        member = FamilyGroupMemberModel(
            family_group_id=family_group_id,
            person_id=person_id,
            tree_id=tree_id,
            tenant_id=tenant_id,
            role=role,
            parentage_type=parentage_type,
        )
        self._session.add(member)
        await self._session.flush()
        return member
