"""JWT service — encode, decode, and validate access/refresh tokens.

Token anatomy
─────────────
Access token (Bearer, 15 min):
    {
        "sub":  "<user_id>",       # UUID string
        "tid":  "<tenant_id>",     # UUID string
        "jti":  "<uuid4>",         # unique token ID (for revocation)
        "type": "access",
        "iat":  <unix ts>,
        "exp":  <unix ts>
    }

Refresh token (HttpOnly cookie, 30 days):
    Same shape but "type": "refresh".
    jti is stored in Redis; revocation = Redis DELETE.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from src.domain.exceptions import TokenExpiredError, TokenInvalidError


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"


class JWTService:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 30,
    ) -> None:
        self._secret = secret_key
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_token_expire_days)

    # ── Token creation ────────────────────────────────────────────

    def create_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        app_role: str | None = None,
    ) -> tuple[str, str]:
        """
        Returns (encoded_jwt, jti).
        The jti is NOT stored server-side for access tokens (stateless).
        """
        jti = str(uuid.uuid4())
        payload = self._build_payload(user_id, tenant_id, jti, TokenType.ACCESS, self._access_expire)
        if app_role:
            payload["role"] = app_role
        return jwt.encode(payload, self._secret, algorithm=self._algorithm), jti

    def create_refresh_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple[str, str]:
        """
        Returns (encoded_jwt, jti).
        Caller must store jti in Redis.
        """
        jti = str(uuid.uuid4())
        payload = self._build_payload(user_id, tenant_id, jti, TokenType.REFRESH, self._refresh_expire)
        return jwt.encode(payload, self._secret, algorithm=self._algorithm), jti

    # ── Token validation ──────────────────────────────────────────

    def decode_access_token(self, token: str) -> dict:
        return self._decode(token, expected_type=TokenType.ACCESS)

    def decode_refresh_token(self, token: str) -> dict:
        return self._decode(token, expected_type=TokenType.REFRESH)

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as exc:
            msg = str(exc).lower()
            if "expired" in msg:
                raise TokenExpiredError("Token has expired") from exc
            raise TokenInvalidError(f"Token validation failed: {exc}") from exc

        if payload.get("type") != expected_type:
            raise TokenInvalidError(
                f"Expected {expected_type!r} token, got {payload.get('type')!r}"
            )
        return payload

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _build_payload(
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        jti: str,
        token_type: str,
        expire_delta: timedelta,
    ) -> dict:
        now = datetime.now(tz=timezone.utc)
        return {
            "sub":  str(user_id),
            "tid":  str(tenant_id),
            "jti":  jti,
            "type": token_type,
            "iat":  now,
            "exp":  now + expire_delta,
        }

    @staticmethod
    def extract_user_id(payload: dict) -> uuid.UUID:
        return uuid.UUID(payload["sub"])

    @staticmethod
    def extract_tenant_id(payload: dict) -> uuid.UUID:
        return uuid.UUID(payload["tid"])

    @staticmethod
    def extract_jti(payload: dict) -> str:
        return payload["jti"]

    @property
    def refresh_expire_seconds(self) -> int:
        return int(self._refresh_expire.total_seconds())
