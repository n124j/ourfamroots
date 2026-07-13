"""Shared, lightweight namespace (tenant) summary used to annotate user-facing DTOs."""
from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.tenant import TenantModel


class NamespaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_global: bool = False

    model_config = {"from_attributes": True}


async def get_namespace_summary(session: AsyncSession, tenant_id: uuid.UUID) -> NamespaceSummary | None:
    tenant = await session.get(TenantModel, tenant_id)
    return NamespaceSummary.model_validate(tenant) if tenant else None
