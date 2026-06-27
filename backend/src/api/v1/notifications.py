"""Notifications API."""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from src.api.deps import CurrentUserDep, UoWDep

router = APIRouter(tags=["notifications"])


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: Optional[str]
    data: dict
    is_read: bool
    created_at: str


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    current_user: CurrentUserDep,
    uow: UoWDep,
    limit: int = Query(200, ge=1, le=200),
) -> list[NotificationResponse]:
    # Lazy expiry: delete notifications older than 3 months on each fetch
    await uow._session.execute(
        text("DELETE FROM notifications WHERE user_id = :uid AND created_at < now() - interval '3 months'"),
        {"uid": current_user.id},
    )
    rows = (await uow._session.execute(
        text("""
            SELECT id, type, title, body, data, is_read, created_at
            FROM notifications
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :lim
        """),
        {"uid": current_user.id, "lim": limit},
    )).fetchall()
    return [
        NotificationResponse(
            id=r.id,
            type=r.type,
            title=r.title,
            body=r.body,
            data=r.data or {},
            is_read=r.is_read,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/notifications/unread-count")
async def unread_count(current_user: CurrentUserDep, uow: UoWDep) -> dict:
    count = (await uow._session.execute(
        text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = false"),
        {"uid": current_user.id},
    )).scalar_one()
    return {"count": count}


@router.patch("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def mark_read(notification_id: uuid.UUID, current_user: CurrentUserDep, uow: UoWDep) -> None:
    await uow._session.execute(
        text("UPDATE notifications SET is_read = true WHERE id = :id AND user_id = :uid"),
        {"id": notification_id, "uid": current_user.id},
    )
    await uow._session.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, response_model=None, response_class=Response)
async def mark_all_read(current_user: CurrentUserDep, uow: UoWDep) -> None:
    await uow._session.execute(
        text("UPDATE notifications SET is_read = true WHERE user_id = :uid AND is_read = false"),
        {"uid": current_user.id},
    )
    await uow._session.commit()
