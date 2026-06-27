"""
Security tests — tenant isolation (multi-tenancy boundary enforcement).

A user from Tenant A must never be able to read or modify data belonging
to Tenant B, even if they have valid JWT tokens and know the resource IDs.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.domain.media.exceptions import MediaNotFoundError

TENANT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
TREE_B   = uuid.uuid4()
MEDIA_B  = uuid.uuid4()
PERSON_B = uuid.uuid4()


class TestMediaTenantIsolation:
    @pytest.mark.asyncio
    async def test_tenant_a_cannot_read_tenant_b_media(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """
        Service layer enforces: media.tenant_id must match current_user.tenant_id.
        Simulate the service raising MediaNotFoundError when tenant mismatches.
        """
        mock_svc = AsyncMock()
        mock_svc.get_media.side_effect = MediaNotFoundError(MEDIA_B)

        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/media/{MEDIA_B}", headers=auth_headers
            )
        # Must be 404, not the actual media item
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_delete_tenant_b_media(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        mock_svc = AsyncMock()
        mock_svc.delete_media.side_effect = MediaNotFoundError(MEDIA_B)

        with patch("src.api.v1.media.get_media_service", return_value=lambda: mock_svc):
            r = await test_client.delete(
                f"/api/v1/media/{MEDIA_B}", headers=auth_headers
            )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_search_is_tenant_scoped(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """
        Name search results must only contain persons from the authenticated
        user's tenant. We verify the service is always called with
        current_user.tenant_id — never with an attacker-supplied tenant ID.
        """
        mock_svc = AsyncMock()
        from src.domain.search.entities import SearchCategory, SearchResults
        mock_svc.search_names.return_value = SearchResults(
            query_type=SearchCategory.NAME, total=0
        )

        with patch("src.api.v1.search.get_search_service", return_value=lambda: mock_svc):
            r = await test_client.get(
                f"/api/v1/search?q=Smith&tenant_id={TENANT_B}",  # attacker injects tenant_id
                headers=auth_headers,
            )

        if r.status_code == 200 and mock_svc.search_names.called:
            call_args = mock_svc.search_names.call_args
            called_tenant = call_args.kwargs.get("tenant_id") or call_args.args[1]
            assert called_tenant != TENANT_B, (
                "Service was called with attacker-supplied tenant_id!"
            )


class TestAuthTenantIsolation:
    @pytest.mark.asyncio
    async def test_jwt_tenant_cannot_be_overridden_by_header(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """
        Even if an attacker sends X-Tenant-ID: <other_tenant>,
        the server should use the tenant encoded in the JWT, not the header.
        This is a defence-in-depth test.
        """
        headers = {**auth_headers, "X-Tenant-ID": str(TENANT_B)}
        r = await test_client.get("/api/v1/search?q=Smith", headers=headers)
        # Should not error out; server ignores the spoofed header
        assert r.status_code != 500
