"""
Security unit tests — cryptographic primitives and JWT token mechanics.

These tests verify the security properties of the password hasher and JWT
service without going through the HTTP layer, ensuring the primitives
themselves behave correctly.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from jose import jwt as jose_jwt

from src.domain.exceptions import (
    AccountLockedError,
    ActiveSessionConflictError,
    PermissionDeniedError,
    RateLimitError,
    TokenInvalidError,
)
from src.infrastructure.security.jwt import JWTService, TokenType
from src.infrastructure.security.password import PasswordHasher

TEST_SECRET = "test-secret-key-that-is-long-enough-for-hs256"


# ── PasswordHasher ────────────────────────────────────────────────

class TestPasswordHasherSecurity:
    """Verify bcrypt hashing and verification behave securely."""

    def test_hash_produces_bcrypt_string(self):
        h = PasswordHasher.hash("S3cur3P@ss!")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_verify_returns_true_for_correct_password(self):
        password = "CorrectHorseBattery"
        hashed = PasswordHasher.hash(password)
        assert PasswordHasher.verify(password, hashed) is True

    def test_verify_returns_false_for_wrong_password(self):
        hashed = PasswordHasher.hash("real-password")
        assert PasswordHasher.verify("wrong-password", hashed) is False

    def test_verify_returns_false_for_malformed_hash(self):
        # Malformed hash must never raise — it must silently return False
        result = PasswordHasher.verify("anything", "not$a$valid$bcrypt$hash")
        assert result is False

    def test_needs_rehash_returns_bool(self):
        hashed = PasswordHasher.hash("password")
        result = PasswordHasher.needs_rehash(hashed)
        assert isinstance(result, bool)

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt must use a unique salt each time."""
        h1 = PasswordHasher.hash("same-password")
        h2 = PasswordHasher.hash("same-password")
        assert h1 != h2


# ── JWTService ────────────────────────────────────────────────────

class TestJWTServiceSecurity:
    """Verify JWT token creation, decoding, and claim extraction."""

    @pytest.fixture()
    def svc(self) -> JWTService:
        return JWTService(
            secret_key=TEST_SECRET,
            access_token_expire_minutes=15,
            refresh_token_expire_days=30,
        )

    @pytest.fixture()
    def user_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture()
    def tenant_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # Access token

    def test_create_access_token_includes_role(self, svc, user_id, tenant_id):
        token, jti = svc.create_access_token(user_id, tenant_id, app_role="ADMIN")
        payload = jose_jwt.decode(token, TEST_SECRET, algorithms=["HS256"])
        assert payload["role"] == "ADMIN"
        assert jti

    def test_decode_access_token_happy_path(self, svc, user_id, tenant_id):
        token, _ = svc.create_access_token(user_id, tenant_id)
        payload = svc.decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == TokenType.ACCESS

    def test_decode_access_token_rejects_garbage(self, svc):
        with pytest.raises(TokenInvalidError):
            svc.decode_access_token("not.a.valid.jwt.at.all")

    def test_decode_access_token_rejects_refresh_token(self, svc, user_id, tenant_id):
        """An access-token decoder must reject a refresh token (wrong type)."""
        refresh_token, _ = svc.create_refresh_token(user_id, tenant_id)
        with pytest.raises(TokenInvalidError):
            svc.decode_access_token(refresh_token)

    # Refresh token

    def test_create_refresh_token_returns_token_and_jti(self, svc, user_id, tenant_id):
        token, jti = svc.create_refresh_token(user_id, tenant_id)
        assert token
        assert jti
        payload = jose_jwt.decode(token, TEST_SECRET, algorithms=["HS256"])
        assert payload["type"] == TokenType.REFRESH

    def test_decode_refresh_token_happy_path(self, svc, user_id, tenant_id):
        token, _ = svc.create_refresh_token(user_id, tenant_id)
        payload = svc.decode_refresh_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == TokenType.REFRESH

    def test_decode_refresh_token_rejects_access_token(self, svc, user_id, tenant_id):
        """A refresh-token decoder must reject an access token (wrong type)."""
        access_token, _ = svc.create_access_token(user_id, tenant_id)
        with pytest.raises(TokenInvalidError):
            svc.decode_refresh_token(access_token)

    # Claim extraction helpers

    def test_extract_user_id(self, svc, user_id, tenant_id):
        token, _ = svc.create_access_token(user_id, tenant_id)
        payload = svc.decode_access_token(token)
        assert svc.extract_user_id(payload) == user_id

    def test_extract_tenant_id(self, svc, user_id, tenant_id):
        token, _ = svc.create_access_token(user_id, tenant_id)
        payload = svc.decode_access_token(token)
        assert svc.extract_tenant_id(payload) == tenant_id

    def test_extract_jti(self, svc, user_id, tenant_id):
        token, original_jti = svc.create_access_token(user_id, tenant_id)
        payload = svc.decode_access_token(token)
        assert svc.extract_jti(payload) == original_jti

    def test_refresh_expire_seconds(self, svc):
        assert svc.refresh_expire_seconds == int(timedelta(days=30).total_seconds())

    def test_wrong_secret_raises_invalid(self, svc, user_id, tenant_id):
        """Token signed with a different secret must be rejected."""
        other_svc = JWTService(secret_key="completely-different-secret-key")
        token, _ = other_svc.create_access_token(user_id, tenant_id)
        with pytest.raises(TokenInvalidError):
            svc.decode_access_token(token)


# ── Security-relevant domain exceptions ──────────────────────────

class TestSecurityExceptionProperties:
    """Exception classes must carry the correct codes and attributes."""

    def test_account_locked_default_retry(self):
        exc = AccountLockedError()
        assert exc.retry_after_seconds == 900
        assert exc.code == "ACCOUNT_LOCKED"
        assert "900" in exc.message

    def test_account_locked_custom_retry(self):
        exc = AccountLockedError(retry_after_seconds=300)
        assert exc.retry_after_seconds == 300
        assert "300" in exc.message

    def test_active_session_conflict(self):
        exc = ActiveSessionConflictError()
        assert exc.code == "ACTIVE_SESSION_CONFLICT"

    def test_permission_denied_no_action(self):
        exc = PermissionDeniedError()
        assert exc.code == "PERMISSION_DENIED"
        assert "Permission denied" in exc.message

    def test_permission_denied_with_action(self):
        exc = PermissionDeniedError("delete record")
        assert "delete record" in exc.message

    def test_rate_limit_default(self):
        exc = RateLimitError()
        assert exc.retry_after_seconds == 60
        assert exc.code == "RATE_LIMITED"

    def test_rate_limit_custom(self):
        exc = RateLimitError(retry_after_seconds=120)
        assert exc.retry_after_seconds == 120
        assert "120" in exc.message

    def test_token_invalid_carries_detail(self):
        exc = TokenInvalidError("signature mismatch")
        assert exc.code == "TOKEN_INVALID"
        assert "signature mismatch" in exc.message
