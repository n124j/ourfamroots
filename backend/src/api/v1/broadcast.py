"""Broadcast email API — Super Admin only."""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from src.api.deps import SessionDep, SuperAdminDep
from src.api.v1._admin_log import log_admin_action
from src.infrastructure.database.models.broadcast_log import BroadcastLogModel
from src.infrastructure.database.models.user import UserModel

router = APIRouter(prefix="/broadcast", tags=["Broadcast"])
log = structlog.get_logger(__name__)


def _send_smtp(to: str, subject: str, html_body: str, text_body: str) -> None:
    """Blocking SMTP send that raises on failure (for accurate error counting)."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from src.config import get_settings

    settings = get_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_user and settings.smtp_password:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(settings.email_from, to, msg.as_string())


# ── Request / response schemas ────────────────────────────────────────────────

class BroadcastRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    category: str = Field("notice", pattern="^(notice|alert|event|update)$")
    recipient_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Specific user IDs. Empty list = send to all active verified users.",
    )


class BroadcastResponse(BaseModel):
    sent_count: int
    failed_count: int


class BroadcastRecipient(BaseModel):
    id: uuid.UUID
    email: str
    given_name: Optional[str]
    family_name: Optional[str]
    app_role: str
    broadcast_unsubscribed: bool = False

    model_config = {"from_attributes": True}


class BroadcastRecipientsResponse(BaseModel):
    total: int
    items: list[BroadcastRecipient]


class BroadcastHistoryItem(BaseModel):
    id: uuid.UUID
    sender_display_name: str
    subject: str
    body: str
    category: str
    recipient_count: int
    sent_count: int
    failed_count: int
    recipient_emails: list[str]
    created_at: str

    model_config = {"from_attributes": True}


class BroadcastHistoryResponse(BaseModel):
    total: int
    items: list[BroadcastHistoryItem]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/recipients",
    response_model=BroadcastRecipientsResponse,
    summary="List eligible broadcast recipients (active, verified users)",
)
async def list_recipients(
    current_user: SuperAdminDep,
    session: SessionDep,
    search: Optional[str] = None,
) -> BroadcastRecipientsResponse:
    q = select(UserModel).where(
        UserModel.tenant_id == current_user.tenant_id,
        UserModel.is_active.is_(True),
        UserModel.email_verified.is_(True),
    )
    if search:
        pattern = f"%{search}%"
        q = q.where(
            (UserModel.email.ilike(pattern))
            | (UserModel.given_name.ilike(pattern))
            | (UserModel.family_name.ilike(pattern))
        )
    q = q.order_by(UserModel.given_name.asc(), UserModel.family_name.asc())

    total = (await session.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()

    rows = (await session.execute(q.limit(500))).scalars().all()

    return BroadcastRecipientsResponse(
        total=total,
        items=[
            BroadcastRecipient(
                id=u.id,
                email=u.email,
                given_name=u.given_name,
                family_name=u.family_name,
                app_role=u.app_role,
                broadcast_unsubscribed=u.broadcast_unsubscribed,
            )
            for u in rows
        ],
    )


@router.post(
    "/send",
    response_model=BroadcastResponse,
    summary="Send a broadcast email to selected or all users (Super Admin only)",
)
async def send_broadcast(
    body: BroadcastRequest,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> BroadcastResponse:
    from src.infrastructure.email.service import broadcast_email
    from src.config import get_settings

    settings = get_settings()
    unsubscribe_base = f"{settings.frontend_base_url}/settings/notifications"

    q = select(UserModel).where(
        UserModel.tenant_id == current_user.tenant_id,
        UserModel.is_active.is_(True),
        UserModel.email_verified.is_(True),
        UserModel.broadcast_unsubscribed.is_(False),
    )
    if body.recipient_ids:
        q = q.where(UserModel.id.in_(body.recipient_ids))

    recipients = (await session.execute(q)).scalars().all()

    if not recipients:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No eligible recipients found (all may have unsubscribed)")

    async def _send_one(user: UserModel) -> bool:
        html, text = broadcast_email(
            subject=body.subject,
            body=body.body,
            recipient_name=user.full_name,
            category=body.category,
            unsubscribe_url=unsubscribe_base,
        )
        try:
            await asyncio.to_thread(_send_smtp, user.email, body.subject, html, text)
            return True
        except Exception:
            return False

    results = await asyncio.gather(*[_send_one(u) for u in recipients])
    sent = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)

    recipient_emails = [u.email for u in recipients]

    # Save broadcast log
    log_entry = BroadcastLogModel(
        tenant_id=current_user.tenant_id,
        sender_id=current_user.id,
        sender_display_name=current_user.full_name,
        subject=body.subject,
        body=body.body,
        category=body.category,
        recipient_count=len(recipients),
        sent_count=sent,
        failed_count=failed,
        recipient_emails=recipient_emails,
    )
    session.add(log_entry)

    # Log to activity feed
    target = f"{body.subject} → {sent} recipient{'s' if sent != 1 else ''}"
    ip = request.client.host if request.client else None
    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "BROADCAST_SEND", target, ip,
    )

    await session.commit()

    log.info(
        "broadcast.sent",
        sender=current_user.email,
        subject=body.subject,
        category=body.category,
        total=len(recipients),
        sent=sent,
        failed=failed,
    )

    return BroadcastResponse(sent_count=sent, failed_count=failed)


@router.get(
    "/history",
    response_model=BroadcastHistoryResponse,
    summary="List broadcast email history",
)
async def list_history(
    current_user: SuperAdminDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> BroadcastHistoryResponse:
    base = select(BroadcastLogModel).where(
        BroadcastLogModel.tenant_id == current_user.tenant_id,
    ).order_by(BroadcastLogModel.created_at.desc())

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    offset = (page - 1) * page_size
    rows = (await session.execute(base.offset(offset).limit(page_size))).scalars().all()

    return BroadcastHistoryResponse(
        total=total,
        items=[
            BroadcastHistoryItem(
                id=r.id,
                sender_display_name=r.sender_display_name,
                subject=r.subject,
                body=r.body,
                category=r.category,
                recipient_count=r.recipient_count,
                sent_count=r.sent_count,
                failed_count=r.failed_count,
                recipient_emails=r.recipient_emails or [],
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ],
    )


@router.delete(
    "/history/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Delete a broadcast log entry",
)
async def delete_history_entry(
    log_id: uuid.UUID,
    request: Request,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> None:
    result = await session.execute(
        select(BroadcastLogModel).where(
            BroadcastLogModel.id == log_id,
            BroadcastLogModel.tenant_id == current_user.tenant_id,
        )
    )
    entry = result.scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Broadcast log not found")

    await session.delete(entry)

    ip = request.client.host if request.client else None
    await log_admin_action(
        session, current_user.tenant_id, current_user.id,
        current_user.full_name, "BROADCAST_DEL", entry.subject, ip,
    )

    await session.commit()
