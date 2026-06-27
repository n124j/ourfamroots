"""Integration tests for /api/v1/auth/* endpoints.

Uses the async test client from conftest.py (no real DB/Redis).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_returns_204(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/register", json={
            "email": "bob@example.com",
            "password": "Password1",
            "given_name": "Bob",
            "family_name": "Smith",
        })
        assert resp.status_code == 204
        assert resp.content == b""  # no body

    async def test_register_does_not_set_session_cookie(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/register", json={
            "email": "nocookie@example.com",
            "password": "Password1",
            "given_name": "No",
            "family_name": "Cookie",
        })
        assert resp.status_code == 204
        assert "refresh_token" not in resp.cookies

    async def test_register_duplicate_email_returns_409(self, test_client: AsyncClient) -> None:
        payload = {
            "email": "dup@example.com",
            "password": "Password1",
            "given_name": "A",
            "family_name": "B",
        }
        await test_client.post("/api/v1/auth/register", json=payload)
        resp = await test_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_weak_password_returns_422(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "password": "short",
            "given_name": "A",
            "family_name": "B",
        })
        assert resp.status_code == 422

    async def test_register_invalid_email_returns_422(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "Password1",
            "given_name": "A",
            "family_name": "B",
        })
        assert resp.status_code == 422

    async def test_register_no_tenant_slug_field(self, test_client: AsyncClient) -> None:
        """tenant_slug is no longer accepted — payload without it must succeed."""
        resp = await test_client.post("/api/v1/auth/register", json={
            "email": "notenant@example.com",
            "password": "Password1",
            "given_name": "No",
            "family_name": "Tenant",
        })
        assert resp.status_code == 204


class TestLogin:
    async def test_unverified_user_cannot_login(self, test_client: AsyncClient) -> None:
        await test_client.post("/api/v1/auth/register", json={
            "email": "charlie@example.com",
            "password": "Password1",
            "given_name": "Charlie",
            "family_name": "Brown",
        })
        resp = await test_client.post("/api/v1/auth/login", json={
            "email": "charlie@example.com",
            "password": "Password1",
        })
        # Registration no longer verifies email — login must be blocked
        assert resp.status_code == 403

    async def test_wrong_password_returns_401(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "WrongPass1",
        })
        assert resp.status_code == 401

    async def test_missing_fields_returns_422(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/login", json={"email": "x@y.com"})
        assert resp.status_code == 422


class TestRefresh:
    async def test_missing_cookie_returns_401(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_without_cookie_returns_204(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/logout")
        assert resp.status_code == 204


class TestVerifyEmail:
    async def test_invalid_token_returns_401(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/verify-email", json={"token": "bad-token"})
        assert resp.status_code == 401


class TestResendVerification:
    async def test_always_returns_204(self, test_client: AsyncClient) -> None:
        """resend-verification never reveals whether the email exists."""
        resp = await test_client.post("/api/v1/auth/resend-verification",
                                       json={"email": "any@example.com"})
        assert resp.status_code == 204

    async def test_verified_user_also_returns_204(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/api/v1/auth/resend-verification",
                                       json={"email": "verified@example.com"})
        assert resp.status_code == 204


class TestForgotPassword:
    async def test_unknown_email_returns_204(self, test_client: AsyncClient) -> None:
        """Unknown email is silently ignored to prevent enumeration."""
        resp = await test_client.post("/api/v1/auth/forgot-password",
                                       json={"email": "unknown@example.com"})
        assert resp.status_code == 204

    async def test_unverified_account_returns_403(self, test_client: AsyncClient) -> None:
        """Unverified accounts cannot request password reset."""
        await test_client.post("/api/v1/auth/register", json={
            "email": "unverified@example.com",
            "password": "Password1",
            "given_name": "A",
            "family_name": "B",
        })
        resp = await test_client.post("/api/v1/auth/forgot-password",
                                       json={"email": "unverified@example.com"})
        assert resp.status_code == 403
        data = resp.json()
        assert "account-not-verified" in data.get("type", "")


class TestOAuthRedirect:
    async def test_google_redirect_returns_302(self, test_client: AsyncClient) -> None:
        resp = await test_client.get(
            "/api/v1/auth/oauth/google",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]

    async def test_unknown_provider_returns_404(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/auth/oauth/facebook")
        assert resp.status_code == 404

    async def test_redirect_sets_state_cookie(self, test_client: AsyncClient) -> None:
        resp = await test_client.get(
            "/api/v1/auth/oauth/google",
            follow_redirects=False,
        )
        assert "oauth_state_google" in resp.cookies

    async def test_redirect_preserves_next_param(self, test_client: AsyncClient) -> None:
        resp = await test_client.get(
            "/api/v1/auth/oauth/google?next=%2Fdashboard",
            follow_redirects=False,
        )
        assert "oauth_next_google" in resp.cookies


class TestOAuthCallback:
    async def test_callback_without_code_redirects_with_error(self, test_client: AsyncClient) -> None:
        resp = await test_client.get(
            "/api/v1/auth/oauth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "oauth_cancelled" in resp.headers["location"]

    async def test_callback_missing_state_redirects_with_error(self, test_client: AsyncClient) -> None:
        resp = await test_client.get(
            "/api/v1/auth/oauth/google/callback?code=fake-code",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "oauth_state_mismatch" in resp.headers["location"]

    async def test_callback_unknown_provider_returns_404(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/auth/oauth/facebook/callback?code=x&state=y")
        assert resp.status_code == 404


class TestHealth:
    async def test_health_returns_200(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
