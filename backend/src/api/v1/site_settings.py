"""Site settings API — maintenance mode (Super Admin only)."""
from __future__ import annotations

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
