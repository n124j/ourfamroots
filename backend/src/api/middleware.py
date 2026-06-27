"""Custom ASGI middleware stack.

Middleware execution order (outermost → innermost):
    GZip (FastAPI built-in)
    → CORS (FastAPI built-in)
    → RequestIDMiddleware      — attaches X-Request-ID to every request/response
    → LoggingMiddleware        — structured access log via structlog
    → MaintenanceMiddleware    — returns 503 when site is under construction
    → TenantMiddleware         — validates JWT, sets tenant_id + user_id context
"""

from __future__ import annotations

import json
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

log = structlog.get_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique request ID to each request.

    - Reads X-Request-ID from the incoming request if present.
    - Generates a UUID4 otherwise.
    - Echoes the ID back in the response header.
    - Binds the ID to the structlog context so all log lines carry it.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured access log: method, path, status, duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        return response


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Decode the Bearer JWT (if present) and bind tenant_id + user_id to
    request.state so downstream dependencies can read them without
    re-parsing the token.

    Routes that require authentication use the `get_current_user`
    dependency in `api/deps.py`, which raises 401 if state is unset.
    Public routes (health, auth/register, auth/login) are unaffected.
    """

    _PUBLIC_PREFIXES = (
        "/health",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/resend-verification",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-new-login",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    def __init__(self, app: ASGIApp, jwt_secret: str, jwt_algorithm: str = "HS256") -> None:
        super().__init__(app)
        self._secret = jwt_secret
        self._algorithm = jwt_algorithm

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Mark state defaults
        request.state.user_id = None
        request.state.tenant_id = None

        path = request.url.path
        if not any(path.startswith(p) for p in self._PUBLIC_PREFIXES):
            token = self._extract_bearer(request)
            if token:
                try:
                    from jose import jwt as jose_jwt
                    payload = jose_jwt.decode(token, self._secret, algorithms=[self._algorithm])
                    request.state.user_id = payload.get("sub")
                    request.state.tenant_id = payload.get("tid")
                    structlog.contextvars.bind_contextvars(
                        user_id=request.state.user_id,
                        tenant_id=request.state.tenant_id,
                    )
                except Exception:
                    pass  # let auth dependency raise 401

        return await call_next(request)

    @staticmethod
    def _extract_bearer(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """
    When maintenance mode is enabled in site_settings, return 503 for
    all requests except those from the Super Administrator and a small
    set of pass-through paths (health, auth, maintenance-status check).

    Uses Redis to cache the maintenance state so the DB is not hit on
    every request. Cache TTL = 10 seconds.
    """

    _PASSTHROUGH_PREFIXES = (
        "/health",
        "/api/v1/auth/",
        "/api/v1/oauth/",
        "/api/v1/site-settings/maintenance",
        "/api/v1/users/me",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    _CACHE_KEY = "site:maintenance"
    _CACHE_TTL = 10  # seconds

    def __init__(self, app: ASGIApp, jwt_secret: str, jwt_algorithm: str = "HS256") -> None:
        super().__init__(app)
        self._secret = jwt_secret
        self._algorithm = jwt_algorithm

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if any(path.startswith(p) for p in self._PASSTHROUGH_PREFIXES):
            return await call_next(request)

        maintenance = await self._is_maintenance_on()
        if not maintenance["enabled"]:
            return await call_next(request)

        if self._is_super_admin_request(request):
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "detail": "Service temporarily unavailable",
                "maintenance_mode": True,
                "maintenance_message": maintenance["message"],
            },
        )

    async def _is_maintenance_on(self) -> dict:
        from src.infrastructure.cache.redis import get_redis

        try:
            redis = get_redis()
            cached = await redis.get(self._CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        enabled = False
        message = ""
        try:
            from src.infrastructure.database.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                from sqlalchemy import select
                from src.infrastructure.database.models.site_settings import SiteSettingsModel

                result = await session.execute(select(SiteSettingsModel).limit(1))
                row = result.scalars().first()
                if row:
                    enabled = row.maintenance_mode
                    message = row.maintenance_message
        except Exception:
            pass

        state = {"enabled": enabled, "message": message}
        try:
            await redis.set(self._CACHE_KEY, json.dumps(state), ex=self._CACHE_TTL)
        except Exception:
            pass
        return state

    def _is_super_admin_request(self, request: Request) -> bool:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return False
        from src.config import get_settings
        settings = get_settings()
        if not settings.super_admin_email:
            return False
        try:
            from jose import jwt as jose_jwt
            token = self._extract_bearer(request)
            if not token:
                return False
            payload = jose_jwt.decode(token, self._secret, algorithms=[self._algorithm])
            user_id_str = payload.get("sub")
            if not user_id_str:
                return False
            # We can't query the DB here efficiently, so we rely on
            # a custom claim 'role' set in the JWT at token issuance.
            role = payload.get("role", "")
            return role == "SUPER_ADMIN"
        except Exception:
            return False

    @staticmethod
    def _extract_bearer(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None
