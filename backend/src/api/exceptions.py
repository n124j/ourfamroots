"""Map domain exceptions to RFC 7807 HTTP responses.

All handlers return a ProblemDetail JSON body with the appropriate
HTTP status code. No domain exception escapes to the default FastAPI
handler, which would expose stack traces.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.schemas.errors import FieldError, ProblemDetail
from src.domain.exceptions import (
    AccountLockedError,
    AccountNotVerifiedError,
    ActiveSessionConflictError,
    AlreadyExistsError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    ValidationError as DomainValidationError,
    VersionConflictError,
)

_BASE_TYPE = "https://ourfamroots.app/errors"


def _problem(
    status: int,
    title: str,
    detail: str,
    error_type: str,
    instance: str | None = None,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    body = ProblemDetail(
        type=f"{_BASE_TYPE}/{error_type}",
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        errors=errors or [],
    )
    return JSONResponse(
        content=body.model_dump(exclude_none=True),
        status_code=status,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all domain + framework exception handlers to the app."""

    # ── Pydantic / FastAPI validation ──────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors = [
            FieldError(
                field=".".join(str(loc) for loc in err["loc"] if loc != "body"),
                message=err["msg"],
                code="VALIDATION_ERROR",
            )
            for err in exc.errors()
        ]
        return _problem(
            status=422,
            title="Validation Error",
            detail="One or more fields failed validation.",
            error_type="validation-error",
            instance=str(request.url.path),
            errors=field_errors,
        )

    # ── Authentication ─────────────────────────────────────────────
    @app.exception_handler(TokenExpiredError)
    async def _token_expired(request: Request, exc: TokenExpiredError) -> JSONResponse:
        return _problem(401, "Unauthorized", exc.message, "token-expired", str(request.url.path))

    @app.exception_handler(TokenInvalidError)
    async def _token_invalid(request: Request, exc: TokenInvalidError) -> JSONResponse:
        return _problem(401, "Unauthorized", exc.message, "token-invalid", str(request.url.path))

    @app.exception_handler(AccountLockedError)
    async def _account_locked(request: Request, exc: AccountLockedError) -> JSONResponse:
        response = _problem(423, "Account Locked", exc.message, "account-locked", str(request.url.path))
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    @app.exception_handler(AccountNotVerifiedError)
    async def _not_verified(request: Request, exc: AccountNotVerifiedError) -> JSONResponse:
        return _problem(403, "Email Not Verified", exc.message, "account-not-verified", str(request.url.path))

    @app.exception_handler(ActiveSessionConflictError)
    async def _active_session(request: Request, exc: ActiveSessionConflictError) -> JSONResponse:
        return _problem(409, "Active Session Conflict", exc.message, "active-session-conflict", str(request.url.path))

    @app.exception_handler(AuthenticationError)
    async def _auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return _problem(401, "Unauthorized", exc.message, "unauthorized", str(request.url.path))

    # ── Authorization ──────────────────────────────────────────────
    @app.exception_handler(AuthorizationError)
    async def _authz_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        return _problem(403, "Forbidden", exc.message, "forbidden", str(request.url.path))

    # ── Not found ──────────────────────────────────────────────────
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _problem(404, "Not Found", exc.message, "not-found", str(request.url.path))

    # ── Conflict ───────────────────────────────────────────────────
    @app.exception_handler(VersionConflictError)
    async def _version_conflict(request: Request, exc: VersionConflictError) -> JSONResponse:
        return _problem(409, "Version Conflict", exc.message, "version-conflict", str(request.url.path))

    @app.exception_handler(AlreadyExistsError)
    async def _already_exists(request: Request, exc: AlreadyExistsError) -> JSONResponse:
        return _problem(409, "Conflict", exc.message, "already-exists", str(request.url.path))

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _problem(409, "Conflict", exc.message, "conflict", str(request.url.path))

    # ── Domain validation ──────────────────────────────────────────
    @app.exception_handler(DomainValidationError)
    async def _domain_validation(request: Request, exc: DomainValidationError) -> JSONResponse:
        errors = [FieldError(field=exc.field or "", message=exc.message, code=exc.code)] if exc.field else []
        return _problem(400, "Bad Request", exc.message, "validation-error", str(request.url.path), errors)

    # ── Rate limiting ──────────────────────────────────────────────
    @app.exception_handler(RateLimitError)
    async def _rate_limit(request: Request, exc: RateLimitError) -> JSONResponse:
        response = _problem(429, "Too Many Requests", exc.message, "rate-limited", str(request.url.path))
        response.headers["Retry-After"] = str(exc.retry_after_seconds)
        return response

    # ── Catch-all for any unhandled DomainError ────────────────────
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(500, "Internal Server Error", "An unexpected error occurred.", "internal-error", str(request.url.path))
