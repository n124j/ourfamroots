"""
FastAPI application factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.api.exceptions import register_exception_handlers
from src.api.middleware import MaintenanceMiddleware, RequestIDMiddleware, TenantMiddleware, LoggingMiddleware
from src.api.v1.router import v1_router
from src.config import get_settings
from src.infrastructure.cache.redis import close_redis, init_redis
from src.infrastructure.database.session import close_engine, init_engine

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown events."""
    logger.info("starting_up", env=settings.app_env, version=settings.app_version)
    await init_engine(settings)
    await init_redis(str(settings.redis_url))
    yield
    logger.info("shutting_down")
    await close_redis()
    await close_engine()


def create_app() -> FastAPI:
    """Application factory — returns a configured FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        swagger_ui_parameters={"persistAuthorization": True},
        lifespan=lifespan,
    )

    # ── Swagger / OpenAPI: inject Bearer auth scheme ──────────
    # Without this FastAPI's auto-generated spec has no securitySchemes,
    # so the Swagger UI "Authorize" button never appears.
    def _custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Paste the **access_token** returned by "
                    "`POST /api/v1/auth/login`. "
                    "Tokens expire in 15 minutes."
                ),
            }
        }
        # Apply BearerAuth as the global default; individual public endpoints
        # can override with security: [] to opt out.
        schema["security"] = [{"BearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = _custom_openapi  # type: ignore[method-assign]

    # ── Middleware (order matters — outermost first) ──────────
    # Middleware stack — last add_middleware = outermost (runs first).
    # Execution order: CORS → RequestID → Tenant → Maintenance → Logging → GZip → Router
    #
    # CORS MUST be outermost so that every response (including 503 maintenance)
    # gets Access-Control-Allow-Origin headers. Without this, the browser
    # silently blocks cross-origin error responses and the frontend sees a
    # network error instead of the actual status code.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        MaintenanceMiddleware,
        jwt_secret=settings.jwt_secret_key,
        jwt_algorithm=settings.jwt_algorithm,
    )
    app.add_middleware(
        TenantMiddleware,
        jwt_secret=settings.jwt_secret_key,
        jwt_algorithm=settings.jwt_algorithm,
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.rstrip('/') for o in settings.cors_origins],
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit",
                        "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # ── Exception handlers ────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────
    app.include_router(v1_router)  # prefix already set in v1_router

    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        workers=1 if settings.debug else settings.workers,
        reload=settings.debug,
        log_config=None,  # structlog handles logging
    )
