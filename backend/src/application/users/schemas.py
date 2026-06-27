"""Pydantic schemas for user profile request/response payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    email_verified: bool
    given_name: str | None
    family_name: str | None
    avatar_url: str | None
    locale: str
    timezone: str
    is_active: bool
    app_role: str = "STANDARD"
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    oauth_providers: list[str] = []

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    given_name: str | None = Field(default=None, min_length=1, max_length=100)
    family_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=2048)
