"""
Immutable value objects for the domain layer.

Value objects are identified by their attributes, not by identity.
They carry no persistence concerns — no ORM imports here.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TenantId:
    """Identifies a tenant. Wraps a UUID."""

    value: uuid.UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def generate(cls) -> TenantId:
        return cls(value=uuid.uuid4())

    @classmethod
    def from_str(cls, raw: str) -> TenantId:
        return cls(value=uuid.UUID(raw))

    @classmethod
    def from_uuid(cls, uid: uuid.UUID) -> TenantId:
        return cls(value=uid)


@dataclass(frozen=True)
class UserId:
    """Identifies a user. Wraps a UUID."""

    value: uuid.UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def generate(cls) -> UserId:
        return cls(value=uuid.uuid4())

    @classmethod
    def from_str(cls, raw: str) -> UserId:
        return cls(value=uuid.UUID(raw))

    @classmethod
    def from_uuid(cls, uid: uuid.UUID) -> UserId:
        return cls(value=uid)


@dataclass(frozen=True)
class Email:
    """Normalised email address value object."""

    value: str

    _PATTERN: re.Pattern[str] = re.compile(
        r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )

    def __post_init__(self) -> None:
        normalised = self.value.lower().strip()
        object.__setattr__(self, "value", normalised)
        if not self._PATTERN.match(normalised):
            from src.domain.exceptions import ValidationError
            raise ValidationError(f"'{self.value}' is not a valid email address.", "email")

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, raw: str) -> Email:
        return cls(value=raw)

    @property
    def domain(self) -> str:
        return self.value.split("@")[1]


@dataclass(frozen=True)
class SubscriptionPlan:
    """Value object representing a subscription plan tier."""

    FREE = "FREE"
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    FAMILY = "FAMILY"
    PROFESSIONAL = "PROFESSIONAL"

    _ALL = {FREE, BASIC, PREMIUM, FAMILY, PROFESSIONAL}

    value: str

    def __post_init__(self) -> None:
        if self.value not in self._ALL:
            from src.domain.exceptions import ValidationError
            raise ValidationError(f"Unknown plan: {self.value!r}", "plan")

    def __str__(self) -> str:
        return self.value

    @property
    def rate_limit_per_minute(self) -> int:
        return {
            self.FREE: 60,
            self.BASIC: 300,
            self.PREMIUM: 1000,
            self.FAMILY: 1000,
            self.PROFESSIONAL: 5000,
        }[self.value]

    @property
    def max_trees(self) -> int:
        return {self.FREE: 1, self.BASIC: 5, self.PREMIUM: 20,
                self.FAMILY: 20, self.PROFESSIONAL: 100}[self.value]


@dataclass(frozen=True)
class CollaboratorRole:
    VIEWER = "VIEWER"
    CONTRIBUTOR = "CONTRIBUTOR"
    EDITOR = "EDITOR"
    ADMIN = "ADMIN"

    _HIERARCHY = {VIEWER: 0, CONTRIBUTOR: 1, EDITOR: 2, ADMIN: 3}
    _ALL = set(_HIERARCHY.keys())

    value: str

    def __post_init__(self) -> None:
        if self.value not in self._ALL:
            from src.domain.exceptions import ValidationError
            raise ValidationError(f"Unknown role: {self.value!r}", "role")

    def __str__(self) -> str:
        return self.value

    def can_read(self) -> bool:
        return True  # all roles can read

    def can_contribute(self) -> bool:
        return self._HIERARCHY[self.value] >= self._HIERARCHY[self.CONTRIBUTOR]

    def can_edit(self) -> bool:
        return self._HIERARCHY[self.value] >= self._HIERARCHY[self.EDITOR]

    def can_admin(self) -> bool:
        return self._HIERARCHY[self.value] >= self._HIERARCHY[self.ADMIN]

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, CollaboratorRole):
            return self._HIERARCHY[self.value] >= self._HIERARCHY[other.value]
        return NotImplemented
