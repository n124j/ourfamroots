"""Unit tests for AuthService.

All tests run without a real database or Redis — backed by in-memory fakes
defined in conftest.py.
"""

from __future__ import annotations

import pytest

from src.application.auth.schemas import LoginRequest, RegisterRequest
from src.application.auth.service import AuthService
from src.domain.exceptions import (
    AccountLockedError,
    AccountNotVerifiedError,
    AlreadyExistsError,
    InvalidCredentialsError,
    TokenInvalidError,
)
from src.infrastructure.database.models.user import UserModel
from tests.conftest import (
    TEST_TENANT_ID,
    TEST_USER_ID,
    FakeTokenStore,
    FakeUnitOfWork,
    FakeUserRepository,
)


pytestmark = pytest.mark.asyncio


# ── Register ──────────────────────────────────────────────────────

class TestRegister:
    async def test_register_returns_none(self, auth_service, fake_uow):
        """Registration returns None — no tokens issued."""
        req = RegisterRequest(email="new@example.com", password="Password1", given_name="New", family_name="User")
        result = await auth_service.register(req)
        assert result is None

    async def test_register_creates_user_unverified(self, auth_service, fake_uow):
        """Registered user starts unverified."""
        req = RegisterRequest(email="unverified@example.com", password="Password1", given_name="A", family_name="B")
        await auth_service.register(req)
        users = fake_uow.users._users
        new_user = next((u for u in users if u.email == "unverified@example.com"), None)
        assert new_user is not None
        assert new_user.email_verified is False
        assert new_user.email_verification_token is not None

    async def test_register_duplicate_email_raises(self, auth_service, fake_uow, verified_user):
        """Duplicate email in the same tenant raises AlreadyExistsError."""
        req = RegisterRequest(email="alice@example.com", password="Password1", given_name="A", family_name="B")
        with pytest.raises(AlreadyExistsError):
            await auth_service.register(req)


# ── Login ─────────────────────────────────────────────────────────

class TestLogin:
    async def test_successful_login(self, auth_service: AuthService) -> None:
        req = LoginRequest(email="alice@example.com", password="Password1")
        resp, _refresh = await auth_service.login(req)

        assert resp.access_token
        assert resp.user_id == TEST_USER_ID
        assert resp.tenant_id == TEST_TENANT_ID
        assert resp.expires_in == 900

    async def test_wrong_password_raises(self, auth_service: AuthService) -> None:
        req = LoginRequest(email="alice@example.com", password="wrongpassword")
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(req)

    async def test_failed_attempts_increment(
        self,
        auth_service: AuthService,
        fake_uow: FakeUnitOfWork,
    ) -> None:
        req = LoginRequest(email="alice@example.com", password="bad")
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(req)

        user = fake_uow.users._users[0]
        assert user.failed_login_attempts == 1

    async def test_account_locked_after_max_attempts(
        self,
        auth_service: AuthService,
        fake_uow: FakeUnitOfWork,
        verified_user: UserModel,
    ) -> None:
        from tests.conftest import _MAX_FAILED_ATTEMPTS  # noqa: F401
        verified_user.failed_login_attempts = 4  # one more will lock

        req = LoginRequest(email="alice@example.com", password="bad")
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(req)

        assert verified_user.locked_until is not None

    async def test_locked_account_raises(
        self,
        auth_service: AuthService,
        verified_user: UserModel,
    ) -> None:
        from datetime import timedelta, timezone
        from datetime import datetime
        verified_user.locked_until = datetime.now(tz=timezone.utc) + timedelta(minutes=10)

        req = LoginRequest(email="alice@example.com", password="Password1")
        with pytest.raises(AccountLockedError):
            await auth_service.login(req)

    async def test_unverified_email_raises(
        self,
        auth_service: AuthService,
        verified_user: UserModel,
    ) -> None:
        verified_user.email_verified = False

        req = LoginRequest(email="alice@example.com", password="Password1")
        with pytest.raises(AccountNotVerifiedError):
            await auth_service.login(req)

    async def test_nonexistent_user_raises(self, auth_service: AuthService) -> None:
        req = LoginRequest(email="ghost@example.com", password="Password1")
        with pytest.raises(InvalidCredentialsError):
            await auth_service.login(req)


# ── Refresh ───────────────────────────────────────────────────────

class TestRefresh:
    async def test_valid_refresh_issues_new_access_token(
        self,
        auth_service: AuthService,
        fake_token_store: FakeTokenStore,
        jwt_service,
    ) -> None:
        import uuid
        user_id = TEST_USER_ID
        tenant_id = TEST_TENANT_ID
        refresh_token, jti = jwt_service.create_refresh_token(user_id, tenant_id)
        await fake_token_store.store(jti, user_id, 3600)

        access_token, expires_in = await auth_service.refresh(refresh_token)

        assert access_token
        assert expires_in == 900

    async def test_revoked_refresh_raises(
        self,
        auth_service: AuthService,
        jwt_service,
    ) -> None:
        import uuid
        refresh_token, _ = jwt_service.create_refresh_token(TEST_USER_ID, TEST_TENANT_ID)
        # token not stored in redis → revoked / never issued

        with pytest.raises(TokenInvalidError):
            await auth_service.refresh(refresh_token)


# ── Logout ────────────────────────────────────────────────────────

class TestLogout:
    async def test_logout_revokes_token(
        self,
        auth_service: AuthService,
        fake_token_store: FakeTokenStore,
        jwt_service,
    ) -> None:
        refresh_token, jti = jwt_service.create_refresh_token(TEST_USER_ID, TEST_TENANT_ID)
        await fake_token_store.store(jti, TEST_USER_ID, 3600)

        await auth_service.logout(refresh_token)

        assert not await fake_token_store.exists(jti)

    async def test_logout_with_invalid_token_is_noop(self, auth_service: AuthService) -> None:
        # Should not raise
        await auth_service.logout("totally-invalid-token")


# ── Email verification ────────────────────────────────────────────

class TestEmailVerification:
    async def test_verify_marks_email_verified(
        self,
        auth_service: AuthService,
        fake_uow: FakeUnitOfWork,
        verified_user: UserModel,
    ) -> None:
        verified_user.email_verified = False
        verified_user.email_verification_token = "valid-token-abc"

        await auth_service.verify_email("valid-token-abc")

        assert verified_user.email_verified
        assert verified_user.email_verification_token is None

    async def test_invalid_token_raises(self, auth_service: AuthService) -> None:
        with pytest.raises(TokenInvalidError):
            await auth_service.verify_email("bad-token")


# ── Password reset ────────────────────────────────────────────────

class TestPasswordReset:
    async def test_reset_changes_password(
        self,
        auth_service: AuthService,
        fake_uow: FakeUnitOfWork,
        verified_user: UserModel,
        hasher,
    ) -> None:
        from datetime import timedelta, timezone, datetime
        verified_user.password_reset_token = "reset-token-xyz"
        verified_user.password_reset_expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        await auth_service.reset_password("reset-token-xyz", "NewPassword1")

        assert hasher.verify("NewPassword1", verified_user.password_hash)
        assert verified_user.password_reset_token is None

    async def test_expired_token_raises(
        self,
        auth_service: AuthService,
        verified_user: UserModel,
    ) -> None:
        from datetime import timedelta, timezone, datetime
        verified_user.password_reset_token = "expired-token"
        verified_user.password_reset_expires_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)

        from src.domain.exceptions import TokenExpiredError
        with pytest.raises(TokenExpiredError):
            await auth_service.reset_password("expired-token", "NewPassword1")


# ── Forgot password ───────────────────────────────────────────────

class TestForgotPassword:
    async def test_forgot_password_unverified_raises(self, auth_service, verified_user):
        """forgot_password raises AccountNotVerifiedError for unverified accounts."""
        verified_user.email_verified = False
        with pytest.raises(AccountNotVerifiedError):
            await auth_service.forgot_password("alice@example.com")

    async def test_forgot_password_unknown_email_is_noop(self, auth_service):
        """forgot_password silently succeeds for unknown email (no enumeration)."""
        # Should not raise
        await auth_service.forgot_password("nobody@example.com")

    async def test_forgot_password_sets_reset_token(self, auth_service, fake_uow, verified_user):
        """forgot_password sets password_reset_token on verified user."""
        assert verified_user.password_reset_token is None
        await auth_service.forgot_password("alice@example.com")
        assert verified_user.password_reset_token is not None
        assert verified_user.password_reset_expires_at is not None


# ── Resend verification ───────────────────────────────────────────

class TestResendVerification:
    async def test_resend_replaces_token(self, auth_service, fake_uow, verified_user):
        """resend_verification generates a new token for an unverified user."""
        verified_user.email_verified = False
        old_token = "old-token-xyz"
        verified_user.email_verification_token = old_token
        await auth_service.resend_verification("alice@example.com")
        assert verified_user.email_verification_token != old_token
        assert verified_user.email_verification_token is not None

    async def test_resend_noop_for_verified(self, auth_service, verified_user):
        """resend_verification is a no-op if already verified."""
        original_token = verified_user.email_verification_token
        await auth_service.resend_verification("alice@example.com")
        assert verified_user.email_verification_token == original_token

    async def test_resend_noop_for_unknown(self, auth_service):
        """resend_verification is a silent no-op for unknown email."""
        # Should not raise
        await auth_service.resend_verification("ghost@example.com")
