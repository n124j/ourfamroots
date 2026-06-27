"""OAuth 2.0 provider clients — Google and GitHub (Authorization Code flow)."""
from __future__ import annotations

import httpx
import secrets
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

from src.domain.collaboration.exceptions import OAuthProviderError


@dataclass
class OAuthUserInfo:
    """Normalised user info returned by any provider."""
    provider: str
    provider_user_id: str
    email: str
    display_name: Optional[str]
    given_name: Optional[str]
    family_name: Optional[str]
    avatar_url: Optional[str]
    email_verified: bool


# ── Base client ────────────────────────────────────────────────────────────────

class OAuthClient:
    """Abstract base for OAuth 2.0 Authorization Code flow clients."""

    PROVIDER: str = ""
    AUTH_URL: str = ""
    TOKEN_URL: str = ""
    USERINFO_URL: str = ""
    SCOPES: list[str] = []

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "state": state,
            "access_type": "offline",    # get refresh_token (Google-specific; ignored by others)
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def generate_state(self) -> str:
        """Generate a CSRF state token to be stored in session."""
        return secrets.token_urlsafe(24)

    async def exchange_code(self, code: str) -> str:
        """Exchange authorization code for access token. Returns access token."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
        if resp.status_code != 200:
            raise OAuthProviderError(self.PROVIDER, f"token exchange failed: {resp.text}")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise OAuthProviderError(self.PROVIDER, f"no access_token in response: {data}")
        return token

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        raise NotImplementedError


# ── Google ─────────────────────────────────────────────────────────────────────

class GoogleOAuthClient(OAuthClient):
    PROVIDER = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    SCOPES = ["openid", "email", "profile"]

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code != 200:
            raise OAuthProviderError(self.PROVIDER, f"userinfo failed: {resp.text}")
        data = resp.json()
        return OAuthUserInfo(
            provider=self.PROVIDER,
            provider_user_id=data["sub"],
            email=data["email"],
            display_name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            avatar_url=data.get("picture"),
            email_verified=data.get("email_verified", False),
        )


# ── GitHub ─────────────────────────────────────────────────────────────────────

class GitHubOAuthClient(OAuthClient):
    PROVIDER = "github"
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAIL_URL = "https://api.github.com/user/emails"
    SCOPES = ["user:email", "read:user"]

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            user_resp = await client.get(self.USERINFO_URL, headers=headers)
            email_resp = await client.get(self.EMAIL_URL, headers=headers)

        if user_resp.status_code != 200:
            raise OAuthProviderError(self.PROVIDER, f"user fetch failed: {user_resp.text}")

        user = user_resp.json()
        # GitHub may not include email in /user; check /user/emails
        email = user.get("email")
        email_verified = False
        if email_resp.status_code == 200:
            emails = email_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            if primary:
                email = primary["email"]
                email_verified = primary.get("verified", False)

        if not email:
            raise OAuthProviderError(self.PROVIDER, "no verified email on GitHub account")

        display = user.get("name") or user.get("login") or ""
        parts = display.strip().split(None, 1)
        return OAuthUserInfo(
            provider=self.PROVIDER,
            provider_user_id=str(user["id"]),
            email=email,
            display_name=display or None,
            given_name=parts[0] if parts else None,
            family_name=parts[1] if len(parts) > 1 else None,
            avatar_url=user.get("avatar_url"),
            email_verified=email_verified,
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_oauth_client(provider: str, settings: "Settings") -> OAuthClient:  # type: ignore[name-defined]
    """Instantiate the right client from app settings."""
    if provider == "google":
        return GoogleOAuthClient(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=f"{settings.api_base_url}/api/v1/auth/oauth/google/callback",
        )
    if provider == "github":
        return GitHubOAuthClient(
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            redirect_uri=f"{settings.api_base_url}/api/v1/auth/oauth/github/callback",
        )
    raise ValueError(f"Unknown OAuth provider: {provider}")
