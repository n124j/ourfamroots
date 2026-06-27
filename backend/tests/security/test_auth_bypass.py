"""
Security tests — authentication bypass attempts.

Tests that the JWT validation cannot be bypassed via:
  - Missing token
  - Expired token
  - Tampered signature
  - Algorithm confusion (alg: none)
  - Wrong secret
"""
from __future__ import annotations

import time
import uuid

import pytest
from httpx import AsyncClient

try:
    from jose import jwt as jose_jwt
    _HAS_JOSE = True
except ImportError:
    _HAS_JOSE = False

TEST_SECRET   = "test-secret-key-that-is-long-enough-for-hs256"
WRONG_SECRET  = "completely-different-secret-key-that-is-long"
PROTECTED_URL = "/api/v1/search?q=Smith"


class TestMissingToken:
    @pytest.mark.asyncio
    async def test_no_auth_header_rejected(self, test_client: AsyncClient):
        r = await test_client.get(PROTECTED_URL)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_rejected(self, test_client: AsyncClient):
        r = await test_client.get(PROTECTED_URL, headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_basic_auth_rejected(self, test_client: AsyncClient):
        r = await test_client.get(
            PROTECTED_URL,
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert r.status_code == 401


@pytest.mark.skipif(not _HAS_JOSE, reason="python-jose not installed")
class TestTamperedToken:
    def _make_token(self, payload: dict, secret: str = TEST_SECRET, alg: str = "HS256") -> str:
        return jose_jwt.encode(payload, secret, algorithm=alg)

    def _valid_payload(self) -> dict:
        return {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "exp": int(time.time()) + 3600,
            "jti": str(uuid.uuid4()),
            "type": "access",
        }

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, test_client: AsyncClient):
        payload = {**self._valid_payload(), "exp": int(time.time()) - 3600}
        token = self._make_token(payload)
        r = await test_client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected(self, test_client: AsyncClient):
        token = self._make_token(self._valid_payload(), secret=WRONG_SECRET)
        r = await test_client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_none_algorithm_rejected(self, test_client: AsyncClient):
        """Algorithm confusion attack: alg=none should be rejected."""
        import base64, json
        header  = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps(self._valid_payload()).encode()
        ).rstrip(b"=").decode()
        forged  = f"{header}.{payload}."  # empty signature
        r = await test_client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_truncated_token_rejected(self, test_client: AsyncClient):
        token = self._make_token(self._valid_payload())
        r = await test_client.get(
            PROTECTED_URL,
            headers={"Authorization": f"Bearer {token[:20]}"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_cannot_access_protected_route(
        self, test_client: AsyncClient
    ):
        """Refresh tokens have type='refresh'; they must not be accepted as access tokens."""
        payload = {**self._valid_payload(), "type": "refresh"}
        token = self._make_token(payload)
        r = await test_client.get(PROTECTED_URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


class TestPasswordSecurity:
    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, test_client: AsyncClient):
        r = await test_client.post("/api/v1/auth/login", json={
            "email": "alice@example.com",
            "password": "WrongPassword!",
        })
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_401_not_404(self, test_client: AsyncClient):
        """Do not leak whether an email exists."""
        r = await test_client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "AnyPassword!",
        })
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_login_response_does_not_expose_password_hash(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """User profile responses must never contain password_hash."""
        r = await test_client.get("/api/v1/users/me", headers=auth_headers)
        if r.status_code == 200:
            body = r.text
            assert "password_hash" not in body
            assert "$2b$" not in body  # bcrypt hash prefix
