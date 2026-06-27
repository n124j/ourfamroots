"""GraphLoader — hydrates a FamilyGraph from the database.

The loader performs two bulk queries per tree (all persons + all family
group memberships) to build the in-memory graph in O(n) time with minimal
round-trips. This is intentionally denormalised for read performance —
the graph is rebuilt fresh for each write transaction.

Usage:
    loader = GraphLoader(session)
    graph = await loader.load(tree_id, tenant_id)
    # graph is ready for domain service queries and validation
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.genealogy.entities import (
    FamilyGroupNode,
    ParentageType,
    PersonNode,
    Sex,
    UnionType,
)
from src.domain.genealogy.graph import FamilyGraph
from src.infrastructure.database.models.person import (
    FamilyGroupMemberModel,
    FamilyGroupModel,
    PersonModel,
)


class GraphLoader:
    """Builds a FamilyGraph from database records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, tree_id: uuid.UUID, tenant_id: uuid.UUID) -> FamilyGraph:
        """
        Load the complete family graph for a tree.

        Two queries:
        1. SELECT * FROM persons WHERE tree_id = ? AND tenant_id = ?
        2. SELECT fgm.*, fg.union_type FROM family_group_members fgm
               JOIN family_groups fg ON fgm.family_group_id = fg.id
           WHERE fg.tree_id = ? AND fg.tenant_id = ?
        """
        graph = FamilyGraph()

        # ── Load persons ──────────────────────────────────────────
        persons_stmt = select(PersonModel).where(
            PersonModel.tree_id == tree_id,
            PersonModel.tenant_id == tenant_id,
            PersonModel.is_deleted.is_(False),
        )
        persons_result = await self._session.execute(persons_stmt)
        person_rows = persons_result.scalars().all()

        for row in person_rows:
            node = PersonNode(
                id=row.id,
                tree_id=row.tree_id,
                tenant_id=row.tenant_id,
                display_given_name=row.display_given_name,
                display_surname=row.display_surname,
                sex=Sex(row.sex) if row.sex else Sex.UNKNOWN,
                birth_date=row.birth_date,
                death_date=row.death_date,
                birth_year=row.birth_year,
                death_year=row.death_year,
                is_living=row.is_living,
                is_deceased=row.is_deceased,
                is_deleted=row.is_deleted,
                photo_url=row.photo_url,
                born_city=row.born_city,
                born_country=row.born_country,
                died_city=row.died_city,
                died_country=row.died_country,
                notes=row.notes,
            )
            graph.add_person(node)

        # ── Load family groups + memberships ──────────────────────
        fgs_stmt = select(FamilyGroupModel).where(
            FamilyGroupModel.tree_id == tree_id,
            FamilyGroupModel.tenant_id == tenant_id,
        )
        fgs_result = await self._session.execute(fgs_stmt)
        fg_rows = {row.id: row for row in fgs_result.scalars().all()}

        members_stmt = select(FamilyGroupMemberModel).where(
            FamilyGroupMemberModel.family_group_id.in_(list(fg_rows.keys()))
        )
        members_result = await self._session.execute(members_stmt)
        member_rows = members_result.scalars().all()

        # Group members by family_group_id
        members_by_fg: dict[uuid.UUID, list[FamilyGroupMemberModel]] = {}
        for m in member_rows:
            members_by_fg.setdefault(m.family_group_id, []).append(m)

        for fg_id, fg_row in fg_rows.items():
            members = members_by_fg.get(fg_id, [])

            parents = [m.person_id for m in members if m.role == "PARENT"]
            children = {
                m.person_id: ParentageType(m.parentage_type or "BIOLOGICAL")
                for m in members if m.role == "CHILD"
            }

            node = FamilyGroupNode(
                id=fg_id,
                tree_id=fg_row.tree_id,
                tenant_id=fg_row.tenant_id,
                union_type=UnionType(fg_row.union_type) if fg_row.union_type else UnionType.UNKNOWN,
                parent_ids=parents,
                children=children,
            )
            graph.add_family_group(node)

        return graph
