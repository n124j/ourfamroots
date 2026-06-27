"""Search application service — validates queries and delegates to SearchRepository."""
from __future__ import annotations

import uuid
from typing import Optional

from src.domain.search.entities import (
    AncestorQuery,
    BranchQuery,
    NameSearchQuery,
    RelationshipQuery,
    RelativeQuery,
    SearchResults,
    SortOrder,
)
from src.domain.search.exceptions import (
    SearchDepthExceededError,
    SearchQueryTooLongError,
    SearchQueryTooShortError,
)
from src.infrastructure.search.repository import SearchRepository

MAX_DEPTH   = 30
MAX_QUERY   = 200
MIN_QUERY   = 2


class SearchService:
    def __init__(self, repo: SearchRepository) -> None:
        self._repo = repo

    # ── Name search ────────────────────────────────────────────────────────────

    async def search_names(
        self,
        raw: str,
        tenant_id: uuid.UUID,
        tree_id: Optional[uuid.UUID] = None,
        birth_year_min: Optional[int] = None,
        birth_year_max: Optional[int] = None,
        birth_place: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "relevance",
        fuzzy: bool = True,
    ) -> SearchResults:
        raw = raw.strip()
        if len(raw) < MIN_QUERY:
            raise SearchQueryTooShortError(MIN_QUERY)
        if len(raw) > MAX_QUERY:
            raise SearchQueryTooLongError(MAX_QUERY)

        return await self._repo.name_search(
            NameSearchQuery(
                raw=raw,
                tree_id=tree_id,
                tenant_id=tenant_id,
                birth_year_min=birth_year_min,
                birth_year_max=birth_year_max,
                birth_place=birth_place,
                limit=min(limit, 100),
                offset=offset,
                sort=SortOrder(sort) if sort in SortOrder._value2member_map_ else SortOrder.RELEVANCE,
                fuzzy=fuzzy,
            )
        )

    # ── Ancestor search ────────────────────────────────────────────────────────

    async def search_ancestors(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        max_depth: int = 10,
    ) -> SearchResults:
        if max_depth > MAX_DEPTH:
            raise SearchDepthExceededError(MAX_DEPTH)
        return await self._repo.ancestor_search(
            AncestorQuery(
                person_id=person_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                max_depth=max_depth,
            )
        )

    # ── Branch (descendants) ───────────────────────────────────────────────────

    async def search_branch(
        self,
        root_person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        max_depth: int = 10,
    ) -> SearchResults:
        if max_depth > MAX_DEPTH:
            raise SearchDepthExceededError(MAX_DEPTH)
        return await self._repo.branch_search(
            BranchQuery(
                root_person_id=root_person_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                max_depth=max_depth,
            )
        )

    # ── Relationship path ──────────────────────────────────────────────────────

    async def find_relationship(
        self,
        person_id_1: uuid.UUID,
        person_id_2: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        max_depth: int = 15,
    ) -> SearchResults:
        if max_depth > MAX_DEPTH:
            raise SearchDepthExceededError(MAX_DEPTH)
        return await self._repo.relationship_search(
            RelationshipQuery(
                person_id_1=person_id_1,
                person_id_2=person_id_2,
                tree_id=tree_id,
                tenant_id=tenant_id,
                max_depth=max_depth,
            )
        )

    # ── All relatives ──────────────────────────────────────────────────────────

    async def search_relatives(
        self,
        person_id: uuid.UUID,
        tree_id: uuid.UUID,
        tenant_id: uuid.UUID,
        max_hops: int = 4,
    ) -> SearchResults:
        if max_hops > 10:
            raise SearchDepthExceededError(10)
        return await self._repo.relative_search(
            RelativeQuery(
                person_id=person_id,
                tree_id=tree_id,
                tenant_id=tenant_id,
                max_hops=max_hops,
            )
        )
