"""
Security tests — SQL injection prevention.

All user-supplied inputs to search and query endpoints are tested with
standard SQLi payloads. The expected behaviour is either:
  - HTTP 422 (input validation rejects the payload), or
  - HTTP 200/404 with no error (query runs safely via parameterisation).

A 500 Internal Server Error always indicates a potential vulnerability.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

# Classic SQL injection payloads
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1--",
    "'; DROP TABLE persons;--",
    "' UNION SELECT null,null,null--",
    "1' AND SLEEP(5)--",
    "admin'--",
    "' OR ''='",
    "1; SELECT * FROM users--",
    "Robert'); DROP TABLE students;--",
    "' OR 1=1 LIMIT 1 OFFSET 0--",
    "\\x27 OR 1=1",
    "%27 OR %271%27=%271",
]


class TestSearchSQLInjection:
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    @pytest.mark.asyncio
    async def test_name_search_rejects_or_handles_safely(
        self, test_client: AsyncClient, auth_headers: dict, payload: str
    ):
        """Search endpoint must never return 500 for SQL injection payloads."""
        r = await test_client.get(
            f"/api/v1/search?q={payload}", headers=auth_headers
        )
        assert r.status_code != 500, (
            f"Potential SQL injection: payload={payload!r} returned 500"
        )

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    @pytest.mark.asyncio
    async def test_birth_place_filter_safe(
        self, test_client: AsyncClient, auth_headers: dict, payload: str
    ):
        r = await test_client.get(
            f"/api/v1/search?q=Smith&birth_place={payload}", headers=auth_headers
        )
        assert r.status_code != 500

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    @pytest.mark.asyncio
    async def test_login_email_safe(
        self, test_client: AsyncClient, payload: str
    ):
        """Login endpoint must never 500 on injection in email field."""
        r = await test_client.post("/api/v1/auth/login", json={
            "email": payload,
            "password": "any",
        })
        assert r.status_code != 500

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    @pytest.mark.asyncio
    async def test_register_name_fields_safe(
        self, test_client: AsyncClient, payload: str
    ):
        r = await test_client.post("/api/v1/auth/register", json={
            "email": "safe@test.com",
            "password": "Str0ng!Pass",
            "given_name": payload,
            "surname": "Smith",
        })
        assert r.status_code != 500
