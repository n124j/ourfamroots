"""Unit tests for user avatar upload/delete and profile presigning."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.api.v1.admin import AdminUserResponse, _presign_avatar as admin_presign, _serialize
from src.api.v1.users import (
    ALLOWED_AVATAR_TYPES,
    MAX_AVATAR_BYTES,
    _presign_avatar as users_presign,
)
from src.application.users.schemas import UserProfileResponse, UpdateUserRequest
from src.infrastructure.database.models.user import UserModel


# ── AdminUserResponse schema tests ────────────────────────────────────────────


class TestAdminUserResponseSchema:
    def test_avatar_url_defaults_to_none(self):
        """avatar_url is optional with a None default — no validation error."""
        resp = AdminUserResponse(
            id=uuid.uuid4(),
            email="test@example.com",
            given_name="Test",
            family_name="User",
            app_role="STANDARD",
            email_verified=True,
            is_active=True,
            last_login_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert resp.avatar_url is None

    def test_avatar_url_accepts_string(self):
        resp = AdminUserResponse(
            id=uuid.uuid4(),
            email="test@example.com",
            given_name="Test",
            family_name="User",
            avatar_url="https://example.com/avatar.png",
            app_role="STANDARD",
            email_verified=True,
            is_active=True,
            last_login_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert resp.avatar_url == "https://example.com/avatar.png"


# ── Admin _presign_avatar helper tests ────────────────────────────────────────


class TestAdminPresignAvatar:
    def test_none_passthrough(self):
        assert admin_presign(None) is None

    def test_empty_string_passthrough(self):
        assert admin_presign("") == ""

    def test_http_url_passthrough(self):
        url = "https://lh3.googleusercontent.com/photo.jpg"
        assert admin_presign(url) == url

    def test_https_url_passthrough(self):
        url = "http://example.com/avatar.png"
        assert admin_presign(url) == url

    @patch("src.api.v1._s3.presign_photo", return_value="https://minio/presigned")
    def test_s3_key_gets_presigned(self, mock_presign):
        result = admin_presign("tenants/tid/users/uid/avatar/abc.jpg")
        mock_presign.assert_called_once_with("tenants/tid/users/uid/avatar/abc.jpg")
        assert result == "https://minio/presigned"


# ── Admin _serialize tests ────────────────────────────────────────────────────


class TestAdminSerialize:
    def _make_user(self, **overrides) -> UserModel:
        user = UserModel()
        user.id = overrides.get("id", uuid.uuid4())
        user.tenant_id = overrides.get("tenant_id", uuid.uuid4())
        user.email = overrides.get("email", "alice@example.com")
        user.given_name = overrides.get("given_name", "Alice")
        user.family_name = overrides.get("family_name", "Smith")
        user.avatar_url = overrides.get("avatar_url", None)
        user.app_role = overrides.get("app_role", "STANDARD")
        user.email_verified = overrides.get("email_verified", True)
        user.is_active = overrides.get("is_active", True)
        user.last_login_at = overrides.get("last_login_at", None)
        user.created_at = overrides.get(
            "created_at", datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        return user

    def test_serialize_without_avatar(self):
        user = self._make_user()
        result = _serialize(user)
        assert result.avatar_url is None

    def test_serialize_with_http_avatar(self):
        user = self._make_user(avatar_url="https://example.com/pic.jpg")
        result = _serialize(user)
        assert result.avatar_url == "https://example.com/pic.jpg"

    @patch("src.api.v1._s3.presign_photo", return_value="https://presigned-url")
    def test_serialize_with_s3_key_avatar(self, mock_presign):
        user = self._make_user(avatar_url="tenants/t/users/u/avatar/x.jpg")
        result = _serialize(user)
        assert result.avatar_url == "https://presigned-url"
        mock_presign.assert_called_once()


# ── Users _presign_avatar helper tests ────────────────────────────────────────


class TestUsersPresignAvatar:
    def _make_profile(self, avatar_url=None) -> UserProfileResponse:
        return UserProfileResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="test@example.com",
            email_verified=True,
            given_name="Test",
            family_name="User",
            avatar_url=avatar_url,
            locale="en",
            timezone="UTC",
            is_active=True,
            app_role="STANDARD",
            last_login_at=None,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            oauth_providers=[],
        )

    def test_none_avatar_unchanged(self):
        profile = self._make_profile(avatar_url=None)
        result = users_presign(profile)
        assert result.avatar_url is None

    def test_http_avatar_unchanged(self):
        url = "https://lh3.googleusercontent.com/photo.jpg"
        profile = self._make_profile(avatar_url=url)
        result = users_presign(profile)
        assert result.avatar_url == url

    @patch("src.api.v1._s3.presign_photo", return_value="https://minio/signed")
    def test_s3_key_gets_presigned(self, mock_presign):
        profile = self._make_profile(avatar_url="tenants/t/users/u/avatar/x.jpg")
        result = users_presign(profile)
        assert result.avatar_url == "https://minio/signed"


# ── UserProfileResponse schema tests ─────────────────────────────────────────


class TestUserProfileResponseSchema:
    def test_oauth_providers_defaults_to_empty(self):
        resp = UserProfileResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="test@example.com",
            email_verified=True,
            given_name="Test",
            family_name="User",
            avatar_url=None,
            locale="en",
            timezone="UTC",
            is_active=True,
            app_role="STANDARD",
            last_login_at=None,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert resp.oauth_providers == []

    def test_oauth_providers_populated(self):
        resp = UserProfileResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="test@example.com",
            email_verified=True,
            given_name="Test",
            family_name="User",
            avatar_url="https://example.com/pic.jpg",
            locale="en",
            timezone="UTC",
            is_active=True,
            app_role="STANDARD",
            last_login_at=None,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            oauth_providers=["google"],
        )
        assert resp.oauth_providers == ["google"]


# ── Avatar upload validation tests ────────────────────────────────────────────


class TestAvatarUploadValidation:
    def test_allowed_types(self):
        assert "image/jpeg" in ALLOWED_AVATAR_TYPES
        assert "image/png" in ALLOWED_AVATAR_TYPES
        assert "image/webp" in ALLOWED_AVATAR_TYPES
        assert "image/gif" in ALLOWED_AVATAR_TYPES
        assert "image/svg+xml" not in ALLOWED_AVATAR_TYPES
        assert "application/pdf" not in ALLOWED_AVATAR_TYPES

    def test_max_size(self):
        assert MAX_AVATAR_BYTES == 5 * 1024 * 1024


# ── UpdateUserRequest schema tests ───────────────────────────────────────────


class TestUpdateUserRequestSchema:
    def test_avatar_url_field_exists(self):
        req = UpdateUserRequest(avatar_url="https://example.com/pic.jpg")
        assert req.avatar_url == "https://example.com/pic.jpg"

    def test_avatar_url_max_length(self):
        long_url = "https://example.com/" + "a" * 2030
        with pytest.raises(ValidationError):
            UpdateUserRequest(avatar_url=long_url)

    def test_all_fields_optional(self):
        req = UpdateUserRequest()
        assert req.given_name is None
        assert req.family_name is None
        assert req.locale is None
        assert req.timezone is None
        assert req.avatar_url is None
