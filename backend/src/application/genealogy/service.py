"""FamilyTreeApplicationService — orchestrates domain + infrastructure.

Flow for every mutation:
  1. Load FamilyGraph from DB (GraphLoader — two queries)
  2. Call FamilyTreeDomainService → validates, returns MutationResult
  3. Persist MutationResult via repositories
  4. Return response schema

All DB work happens inside a single UoW transaction (commit on success,
rollback on any domain or DB error).
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.genealogy.schemas import (
    AddBothParentsRequest,
    AddChildRequest,
    AddParentRequest,
    AddSiblingRequest,
    AddSpouseRequest,
    AncestorsByGenerationResponse,
    KinshipResponse,
    LineagePathResponse,
    PersonDetailResponse,
    PersonResponse,
)
from src.domain.genealogy import calculators as calc
from src.domain.genealogy.entities import ParentageType, UnionType
from src.domain.genealogy.exceptions import PersonNotInTreeError
from src.domain.genealogy.services import (
    FamilyTreeDomainService,
    MutationResult,
)
from src.infrastructure.database.models.person import FamilyGroupModel, PersonModel
from src.infrastructure.repositories.graph_loader import GraphLoader
from src.infrastructure.repositories.person import (
    SqlAlchemyFamilyGroupRepository,
    SqlAlchemyPersonRepository,
)

log = structlog.get_logger(__name__)


class FamilyTreeApplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._person_repo = SqlAlchemyPersonRepository(session)
        self._fg_repo = SqlAlchemyFamilyGroupRepository(session)
        self._loader = GraphLoader(session)
        self._domain_svc = FamilyTreeDomainService()

    # ── Person CRUD ───────────────────────────────────────────────

    async def get_person(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
    ) -> PersonDetailResponse:
        graph = await self._loader.load(tree_id, tenant_id)
        person = graph.get_person(person_id)
        if person is None:
            raise PersonNotInTreeError(person_id, tree_id)

        from src.api.v1._s3 import presign_photo

        return PersonDetailResponse(
            id=person.id,
            tree_id=person.tree_id,
            display_given_name=person.display_given_name,
            display_surname=person.display_surname,
            sex=person.sex.value,
            is_living=person.is_living,
            is_deceased=person.is_deceased,
            photo_url=presign_photo(person.photo_url),
            parents=graph.parents_of(person_id),
            children=graph.children_of(person_id),
            spouses=graph.spouses_of(person_id),
            siblings=graph.siblings_of(person_id),
        )

    # ── Relationship mutations ────────────────────────────────────

    async def add_parent(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        child_id: uuid.UUID,
        req: AddParentRequest,
    ) -> None:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.add_parent(
            graph, tree_id, tenant_id,
            child_id=child_id,
            parent_id=req.parent_id,
            parentage_type=req.parentage_type,
            union_type=req.union_type,
        )
        await self._apply(result, tenant_id)
        log.info("genealogy.add_parent", child=str(child_id), parent=str(req.parent_id))

    async def add_both_parents(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        child_id: uuid.UUID,
        req: AddBothParentsRequest,
    ) -> None:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.add_both_parents(
            graph, tree_id, tenant_id,
            child_id=child_id,
            father_id=req.father_id,
            mother_id=req.mother_id,
            parentage_type=req.parentage_type,
            union_type=req.union_type,
        )
        await self._apply(result, tenant_id)
        log.info("genealogy.add_both_parents",
                 child=str(child_id), father=str(req.father_id), mother=str(req.mother_id))

    async def add_child(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        parent_id: uuid.UUID,
        req: AddChildRequest,
    ) -> None:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.add_child(
            graph, tree_id, tenant_id,
            parent_id=parent_id,
            child_id=req.child_id,
            other_parent_id=req.other_parent_id,
            parentage_type=req.parentage_type,
            union_type=req.union_type,
        )
        await self._apply(result, tenant_id)
        log.info("genealogy.add_child", parent=str(parent_id), child=str(req.child_id))

    async def add_spouse(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        req: AddSpouseRequest,
    ) -> None:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.add_spouse(
            graph, tree_id, tenant_id,
            person1_id=person_id,
            person2_id=req.spouse_id,
            union_type=req.union_type,
        )
        await self._apply(result, tenant_id)
        log.info("genealogy.add_spouse", p1=str(person_id), p2=str(req.spouse_id))

    async def add_sibling(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        req: AddSiblingRequest,
    ) -> None:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.add_sibling(
            graph, tree_id, tenant_id,
            person_id=person_id,
            sibling_id=req.sibling_id,
            parentage_type=req.parentage_type,
        )
        await self._apply(result, tenant_id)
        log.info("genealogy.add_sibling", person=str(person_id), sibling=str(req.sibling_id))

    # ── Relationship queries ──────────────────────────────────────

    async def get_ancestors(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        max_depth: int = 100,
    ) -> AncestorsByGenerationResponse:
        graph = await self._loader.load(tree_id, tenant_id)
        if not graph.has_person(person_id):
            raise PersonNotInTreeError(person_id, tree_id)
        by_gen = calc.ancestors(graph, person_id, max_depth=max_depth)
        return AncestorsByGenerationResponse(generations=by_gen)

    async def get_descendants(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person_id: uuid.UUID,
        max_depth: int = 100,
    ) -> AncestorsByGenerationResponse:
        graph = await self._loader.load(tree_id, tenant_id)
        if not graph.has_person(person_id):
            raise PersonNotInTreeError(person_id, tree_id)
        by_gen = calc.descendants(graph, person_id, max_depth=max_depth)
        return AncestorsByGenerationResponse(generations=by_gen)

    async def get_kinship(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        person1_id: uuid.UUID,
        person2_id: uuid.UUID,
    ) -> KinshipResponse:
        graph = await self._loader.load(tree_id, tenant_id)
        result = self._domain_svc.kinship(graph, person1_id, person2_id)
        return KinshipResponse(
            person1_id=result.person1_id,
            person2_id=result.person2_id,
            relationship=result.label,
            kind=result.kind,
            cousin_degree=result.cousin_degree,
            cousin_removed=result.cousin_removed,
            common_ancestor_ids=result.common_ancestor_ids,
            path=result.path,
        )

    async def get_lineage_paths(
        self,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        origin_id: uuid.UUID,
        destination_id: uuid.UUID,
    ) -> list[LineagePathResponse]:
        graph = await self._loader.load(tree_id, tenant_id)
        paths = self._domain_svc.get_lineage_paths(graph, origin_id, destination_id)
        return [
            LineagePathResponse(
                nodes=p.nodes,
                edge_labels=p.edge_labels,
                length=p.length,
            )
            for p in paths
        ]

    # ── Private: apply MutationResult to DB ──────────────────────

    async def _apply(self, result: MutationResult, tenant_id: uuid.UUID) -> None:
        """Translate a MutationResult into repository calls within the current session."""
        if result.new_family_group is not None:
            cmd = result.new_family_group
            fg = FamilyGroupModel(
                id=cmd.id,
                tree_id=cmd.tree_id,
                tenant_id=tenant_id,
                union_type=cmd.union_type.value,
            )
            self._session.add(fg)
            await self._session.flush()

        for membership in result.memberships:
            await self._fg_repo.add_member(
                family_group_id=membership.family_group_id,
                person_id=membership.person_id,
                tree_id=membership.tree_id,
                tenant_id=tenant_id,
                role=membership.role,
                parentage_type=(
                    membership.parentage_type.value
                    if membership.role == "CHILD"
                    else None
                ),
            )

        # Update parent1_id / parent2_id denormalised columns on family_group
        await self._sync_parent_columns(result, tenant_id)

    async def _sync_parent_columns(
        self, result: MutationResult, tenant_id: uuid.UUID
    ) -> None:
        """Keep the denormalised parent1_id/parent2_id columns in sync."""
        if result.new_family_group is None:
            return
        fg_id = result.new_family_group.id
        fg = await self._fg_repo.get_by_id(fg_id)
        if fg is None:
            return

        parents = [m.person_id for m in result.memberships if m.role == "PARENT"]
        if parents:
            fg.parent1_id = parents[0]
        if len(parents) > 1:
            fg.parent2_id = parents[1]
        await self._session.flush()
