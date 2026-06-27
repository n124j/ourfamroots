"""Unit tests for search domain entities."""
from __future__ import annotations

import uuid

import pytest

from src.domain.search.entities import (
    NameSearchQuery,
    SearchCategory,
    SortOrder,
    ancestor_label,
    descendant_label,
)
from src.domain.search.exceptions import (
    SearchDepthExceededError,
    SearchQueryTooLongError,
    SearchQueryTooShortError,
)
from src.application.search.service import SearchService


# ── Label helpers ──────────────────────────────────────────────────────────────

class TestAncestorLabel:
    @pytest.mark.parametrize("depth,expected", [
        (1, "Parent"),
        (2, "Grandparent"),
        (3, "Great-grandparent"),
        (4, "2×Great-grandparent"),
        (5, "3×Great-grandparent"),
        (6, "4×Great-grandparent"),
    ])
    def test_known_depths(self, depth: int, expected: str):
        assert ancestor_label(depth) == expected

    def test_deep_ancestor_includes_multiplier(self):
        label = ancestor_label(10)
        assert "Great-grandparent" in label


class TestDescendantLabel:
    @pytest.mark.parametrize("depth,expected", [
        (1, "Child"),
        (2, "Grandchild"),
        (3, "Great-grandchild"),
    ])
    def test_known_depths(self, depth: int, expected: str):
        assert descendant_label(depth) == expected


# ── NameSearchQuery value object ───────────────────────────────────────────────

class TestNameSearchQuery:
    def test_is_frozen_dataclass(self):
        q = NameSearchQuery(raw="Smith", tenant_id=uuid.uuid4())
        with pytest.raises((AttributeError, TypeError)):
            q.raw = "Jones"  # type: ignore[misc]

    def test_default_limit_is_20(self):
        q = NameSearchQuery(raw="Smith", tenant_id=uuid.uuid4())
        assert q.limit == 20

    def test_default_sort_is_relevance(self):
        q = NameSearchQuery(raw="Smith", tenant_id=uuid.uuid4())
        assert q.sort == SortOrder.RELEVANCE

    def test_default_fuzzy_is_true(self):
        q = NameSearchQuery(raw="Smith", tenant_id=uuid.uuid4())
        assert q.fuzzy is True


# ── SearchService validation ───────────────────────────────────────────────────

class TestSearchServiceValidation:
    """Tests validation-only paths — no DB calls needed, repo is a stub."""

    @pytest.fixture
    def svc(self):
        from unittest.mock import AsyncMock
        repo = AsyncMock()
        return SearchService(repo=repo)

    @pytest.mark.asyncio
    async def test_query_too_short_raises(self, svc: SearchService):
        with pytest.raises(SearchQueryTooShortError):
            await svc.search_names(raw="A", tenant_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, svc: SearchService):
        with pytest.raises(SearchQueryTooShortError):
            await svc.search_names(raw="", tenant_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_query_too_long_raises(self, svc: SearchService):
        with pytest.raises(SearchQueryTooLongError):
            await svc.search_names(raw="x" * 201, tenant_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_depth_exceeding_max_raises(self, svc: SearchService):
        with pytest.raises(SearchDepthExceededError):
            await svc.search_ancestors(
                person_id=uuid.uuid4(),
                tree_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                max_depth=31,
            )

    @pytest.mark.asyncio
    async def test_valid_query_delegates_to_repo(self, svc: SearchService):
        from src.domain.search.entities import SearchResults
        svc._repo.name_search.return_value = SearchResults(
            query_type=SearchCategory.NAME, total=0
        )
        result = await svc.search_names(raw="John Smith", tenant_id=uuid.uuid4())
        svc._repo.name_search.assert_called_once()
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_query_raises(self, svc: SearchService):
        with pytest.raises(SearchQueryTooShortError):
            await svc.search_names(raw="  ", tenant_id=uuid.uuid4())
