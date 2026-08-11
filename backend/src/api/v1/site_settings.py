"""Site settings API — maintenance mode and the announcement banner (Super Admin only)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.deps import SessionDep, SuperAdminDep
from src.infrastructure.database.models.site_settings import SiteSettingsModel

router = APIRouter(prefix="/site-settings", tags=["Site Settings"])


class MaintenanceStatusResponse(BaseModel):
    maintenance_mode: bool
    maintenance_message: str

    model_config = {"from_attributes": True}


class UpdateMaintenanceRequest(BaseModel):
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = Field(None, min_length=1, max_length=2000)


async def _get_settings(session: SessionDep) -> SiteSettingsModel:
    result = await session.execute(select(SiteSettingsModel).limit(1))
    row = result.scalars().first()
    if row is None:
        row = SiteSettingsModel()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.get(
    "/maintenance",
    response_model=MaintenanceStatusResponse,
    summary="Get current maintenance mode status (public)",
)
async def get_maintenance_status(session: SessionDep) -> MaintenanceStatusResponse:
    settings = await _get_settings(session)
    return MaintenanceStatusResponse(
        maintenance_mode=settings.maintenance_mode,
        maintenance_message=settings.maintenance_message,
    )


@router.put(
    "/maintenance",
    response_model=MaintenanceStatusResponse,
    summary="Update maintenance mode (Super Admin only)",
)
async def update_maintenance(
    body: UpdateMaintenanceRequest,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> MaintenanceStatusResponse:
    settings = await _get_settings(session)

    if body.maintenance_mode is not None:
        settings.maintenance_mode = body.maintenance_mode
    if body.maintenance_message is not None:
        settings.maintenance_message = body.maintenance_message

    settings.updated_by_id = current_user.id
    await session.commit()
    await session.refresh(settings)

    try:
        from src.infrastructure.cache.redis import get_redis
        await get_redis().delete("site:maintenance")
    except Exception:
        pass

    return MaintenanceStatusResponse(
        maintenance_mode=settings.maintenance_mode,
        maintenance_message=settings.maintenance_message,
    )


# ── Announcement banner ─────────────────────────────────────────────────
#
# Independent of maintenance mode: non-blocking, informational, and
# time-bounded (banner_starts_at/banner_ends_at, either or both may be
# null for an unbounded toggle). Unlike maintenance mode, nothing on the
# server enforces this — it's purely for display — so there's no Redis
# cache to invalidate here.

_HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class BannerStatusResponse(BaseModel):
    active: bool
    message: Optional[str] = None
    bg_color: Optional[str] = None
    text_color: Optional[str] = None


class BannerConfigResponse(BaseModel):
    banner_enabled: bool
    banner_message: Optional[str] = None
    banner_starts_at: Optional[datetime] = None
    banner_ends_at: Optional[datetime] = None
    banner_bg_color: Optional[str] = None
    banner_text_color: Optional[str] = None

    model_config = {"from_attributes": True}


class UpdateBannerRequest(BaseModel):
    banner_enabled: Optional[bool] = None
    banner_message: Optional[str] = Field(None, max_length=2000)
    banner_starts_at: Optional[datetime] = None
    banner_ends_at: Optional[datetime] = None
    # When true, banner_starts_at/banner_ends_at are reset to null, regardless
    # of what (if anything) was also passed for them — lets the admin UI's
    # "Clear schedule" action be a single explicit field rather than relying
    # on None being ambiguous with "leave unchanged".
    clear_schedule: bool = False
    banner_bg_color: Optional[str] = Field(None, pattern=_HEX_COLOR_PATTERN)
    banner_text_color: Optional[str] = Field(None, pattern=_HEX_COLOR_PATTERN)
    # Same "explicit reset" pattern as clear_schedule — resets both colors to
    # null (the frontend's built-in default) regardless of what was also passed.
    reset_colors: bool = False


def _is_banner_active(settings: SiteSettingsModel) -> bool:
    if not settings.banner_enabled:
        return False
    now = datetime.now(timezone.utc)
    if settings.banner_starts_at is not None and now < settings.banner_starts_at:
        return False
    if settings.banner_ends_at is not None and now >= settings.banner_ends_at:
        return False
    return True


@router.get(
    "/banner",
    response_model=BannerStatusResponse,
    summary="Get the current announcement banner status (public)",
)
async def get_banner_status(session: SessionDep) -> BannerStatusResponse:
    settings = await _get_settings(session)
    active = _is_banner_active(settings)
    return BannerStatusResponse(
        active=active,
        message=settings.banner_message if active else None,
        bg_color=settings.banner_bg_color if active else None,
        text_color=settings.banner_text_color if active else None,
    )


@router.get(
    "/banner/config",
    response_model=BannerConfigResponse,
    summary="Get the raw announcement banner configuration (Super Admin only)",
)
async def get_banner_config(current_user: SuperAdminDep, session: SessionDep) -> BannerConfigResponse:
    settings = await _get_settings(session)
    return BannerConfigResponse.model_validate(settings)


@router.put(
    "/banner",
    response_model=BannerConfigResponse,
    summary="Update the announcement banner (Super Admin only)",
)
async def update_banner(
    body: UpdateBannerRequest,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> BannerConfigResponse:
    settings = await _get_settings(session)

    if body.banner_enabled is not None:
        settings.banner_enabled = body.banner_enabled
    if body.banner_message is not None:
        settings.banner_message = body.banner_message

    if body.clear_schedule:
        settings.banner_starts_at = None
        settings.banner_ends_at = None
    else:
        if body.banner_starts_at is not None:
            settings.banner_starts_at = body.banner_starts_at
        if body.banner_ends_at is not None:
            settings.banner_ends_at = body.banner_ends_at

    if body.reset_colors:
        settings.banner_bg_color = None
        settings.banner_text_color = None
    else:
        if body.banner_bg_color is not None:
            settings.banner_bg_color = body.banner_bg_color
        if body.banner_text_color is not None:
            settings.banner_text_color = body.banner_text_color

    settings.updated_by_id = current_user.id
    await session.commit()
    await session.refresh(settings)

    return BannerConfigResponse.model_validate(settings)
