"""
Domain exception hierarchy.

Rules:
- Domain exceptions carry no HTTP knowledge (no status codes here).
- The API layer maps these to RFC 7807 Problem Detail responses.
- All exceptions are immutable value objects — no mutable state.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code!r})"


# ── Authentication & Authorization ───────────────────────────

class AuthenticationError(DomainError):
    """Invalid credentials or expired token."""


class InvalidCredentialsError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Invalid email or password.", "INVALID_CREDENTIALS")


class TokenExpiredError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Token has expired.", "TOKEN_EXPIRED")


class TokenInvalidError(AuthenticationError):
    def __init__(self, detail: str = "Token is invalid.") -> None:
        super().__init__(detail, "TOKEN_INVALID")


class AccountLockedError(AuthenticationError):
    def __init__(self, retry_after_seconds: int = 900) -> None:
        super().__init__(
            f"Account temporarily locked. Try again in {retry_after_seconds} seconds.",
            "ACCOUNT_LOCKED",
        )
        self.retry_after_seconds = retry_after_seconds


class AccountNotVerifiedError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("Email address not verified.", "ACCOUNT_NOT_VERIFIED")


class ActiveSessionConflictError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            "This account is already signed in on another device. "
            "A verification email has been sent to confirm this login.",
            "ACTIVE_SESSION_CONFLICT",
        )


class AuthorizationError(DomainError):
    """Action not permitted for the current actor."""


class PermissionDeniedError(AuthorizationError):
    def __init__(self, action: str = "") -> None:
        msg = f"Permission denied{': ' + action if action else ''}."
        super().__init__(msg, "PERMISSION_DENIED")


# ── Resource Errors ───────────────────────────────────────────

class NotFoundError(DomainError):
    """Resource not found or not accessible to current tenant."""

    def __init__(self, resource: str, identifier: str | None = None) -> None:
        id_part = f" '{identifier}'" if identifier else ""
        super().__init__(f"{resource}{id_part} not found.", "NOT_FOUND")
        self.resource = resource
        self.identifier = identifier


class ConflictError(DomainError):
    """Duplicate resource or constraint violation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFLICT")


class AlreadyExistsError(ConflictError):
    def __init__(self, resource: str, field: str, value: str) -> None:
        super().__init__(f"{resource} with {field}='{value}' already exists.")
        self.resource = resource
        self.field = field
        self.value = value


class VersionConflictError(ConflictError):
    """Optimistic lock version mismatch."""

    def __init__(self, current_version: int) -> None:
        super().__init__("Another edit was saved concurrently. Please refresh and try again.")
        self.code = "VERSION_CONFLICT"
        self.current_version = current_version


# ── Validation Errors ─────────────────────────────────────────

class ValidationError(DomainError):
    """Business-rule validation failure (distinct from Pydantic schema validation)."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field


# ── Rate Limiting ─────────────────────────────────────────────

class RateLimitError(DomainError):
    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__(
            f"Rate limit exceeded. Try again in {retry_after_seconds} seconds.",
            "RATE_LIMITED",
        )
        self.retry_after_seconds = retry_after_seconds
