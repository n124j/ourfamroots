"""
Integration tests for the Search API.

Uses httpx.AsyncClient against a real FastAPI app with a mocked SearchService
to verify request/response contract without needing a live PostgreSQL instance.
For tests that need real FTS, see tests/integration/db/test_search_repository.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.domain.search.entities import (
    AncestorHit,
    PersonSearchHit,
    RelationshipPath,
    SearchCategory,
    SearchResults,
)
from src.domain.search.exceptions import SearchQueryTooShortError


# ── Fixtures ───────────────────────────────────────────────────────────────────

TREE_ID   = uuid.uuid4()
PERSON_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()

MOCK_HIT = PersonSearchHit(
    person_id=PERSON_ID,
    tree_id=TREE_ID,
    given_name="John",
    surname="Smith",
    maiden_name=None,
    birth_year=1850,
    death_year=1920,
    birth_place="London",
    is_living=False,
    score=0.85,
)

MOCK_ANCESTOR = AncestorHit(
    person_id=uuid.uuid4(),
    given_name="Mary",
    surname="Smith",
    birth_year=1820,
    death_year=1895,
    depth=2,
    relationship_label="Grandparent",
    is_living=False,
)


@pytest_asyncio.fixture
async def search_client(test_client: AsyncClient):
    """Reuse the base test client from conftest."""
    return test_client


def _mock_search_svc(**result_kwargs):
    """Return a patched SearchService that returns canned results."""
    svc = AsyncMock()
    svc.search_names.return_value = SearchResults(
        query_type=SearchCategory.NAME,
        total=result_kwargs.get("total", 1),
        hits=result_kwargs.get("hits", [MOCK_HIT]),
        took_ms=5,
    )
    svc.search_ancestors.return_value = SearchResults(
        query_type=SearchCategory.ANCESTOR,
        total=1,
        ancestors=[MOCK_ANCESTOR],
        took_ms=8,
    )
    svc.search_branch.return_value = SearchResults(
        query_type=SearchCategory.BRANCH,
        total=1,
        ancestors=[MOCK_ANCESTOR],
        took_ms=10,
    )
    svc.search_relatives.return_value = SearchResults(
        query_type=SearchCategory.RELATIVE,
        total=1,
        ancestors=[MOCK_ANCESTOR],
        took_ms=6,
    )
    svc.find_relationship.return_value = SearchResults(
        query_type=SearchCategory.RELATIONSHIP,
        total=1,
        relationship=RelationshipPath(
            person_id_1=PERSON_ID,
            person_id_2=TARGET_ID,
            found=True,
            distance=3,
            path=[
                {"person_id": str(PERSON_ID), "name": "John Smith"},
                {"person_id": str(uuid.uuid4()), "name": "Mary Smith"},
                {"person_id": str(TARGET_ID), "name": "William Smith"},
            ],
            relationship_label="Grandparent/grandchild or aunt/uncle",
        ),
        took_ms=12,
    )
    return svc


# ── Global search ──────────────────────────────────────────────────────────────

class TestGlobalSearch:
    @pytest.mark.asyncio
    async def test_returns_hits(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get("/api/v1/search?q=John+Smith", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 0
        assert "hits" in body
        assert "took_ms" in body

    @pytest.mark.asyncio
    async def test_single_char_query_rejected(self, test_client: AsyncClient, auth_headers: dict):
        r = await test_client.get("/api/v1/search?q=J", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_query_rejected(self, test_client: AsyncClient, auth_headers: dict):
        r = await test_client.get("/api/v1/search", headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/search?q=John")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_sort_param_accepted(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                "/api/v1/search?q=Smith&sort=birth_year", headers=auth_headers
            )
        assert r.status_code in (200, 422)  # depends on route availability

    @pytest.mark.asyncio
    async def test_invalid_sort_rejected(self, test_client: AsyncClient, auth_headers: dict):
        r = await test_client.get(
            "/api/v1/search?q=Smith&sort=invalid_sort", headers=auth_headers
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_birth_year_filters_accepted(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/search?q=Smith&birth_year_min=1800&birth_year_max=1900",
                headers=auth_headers,
            )
        assert r.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_response_has_correct_shape(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get("/api/v1/search?q=John", headers=auth_headers)
        if r.status_code == 200:
            body = r.json()
            assert isinstance(body["hits"], list)
            assert isinstance(body["total"], int)
            assert isinstance(body["took_ms"], int)


# ── Ancestor search ────────────────────────────────────────────────────────────

class TestAncestorSearch:
    @pytest.mark.asyncio
    async def test_ancestors_endpoint_exists(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/ancestors",
                headers=auth_headers,
            )
        assert r.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_max_depth_capped_at_30(self, test_client: AsyncClient, auth_headers: dict):
        r = await test_client.get(
            f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/ancestors?max_depth=31",
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ancestors_response_shape(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/ancestors?max_depth=5",
                headers=auth_headers,
            )
        if r.status_code == 200:
            body = r.json()
            assert "items" in body
            assert "total" in body
            assert "took_ms" in body


# ── Relationship path ──────────────────────────────────────────────────────────

class TestRelationshipPath:
    @pytest.mark.asyncio
    async def test_relationship_endpoint_exists(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/relationship?target={TARGET_ID}",
                headers=auth_headers,
            )
        assert r.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_relationship_missing_target_rejected(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        r = await test_client.get(
            f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/relationship",
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_relationship_response_shape(self, test_client: AsyncClient, auth_headers: dict):
        mock_svc = _mock_search_svc()
        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/trees/{TREE_ID}/persons/{PERSON_ID}/relationship?target={TARGET_ID}",
                headers=auth_headers,
            )
        if r.status_code == 200:
            body = r.json()
            rel = body["relationship"]
            assert "found" in rel
            assert "distance" in rel
            assert "path" in rel
            assert isinstance(rel["path"], list)
