"""Subscriptions — Super Admin managed access-control tiers.

A subscription is a named group (Free / Premium – Individual / Premium –
Team) that entitles its members to a set of "filters" (tree view/extension
ids, e.g. "poster", "timeline"). This is pure access-control metadata, not
real billing — no payment processor is involved, and adding/removing a
filter or member has no side effects on tree_members (unlike Permission
Groups, which grant actual tree access). Only a Super Admin can manage
subscriptions; any verified user can read their own entitled filter keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from src.api.deps import SessionDep, SuperAdminDep, VerifiedUserDep
from src.api.v1._admin_log import log_admin_action
from src.domain.collaboration.entities import AppRole
from src.infrastructure.database.models.subscription import (
    SubscriptionFilterModel,
    SubscriptionMemberModel,
    SubscriptionModel,
)
from src.infrastructure.database.models.user import UserModel

admin_router = APIRouter(prefix="/admin/subscriptions", tags=["Admin", "Subscriptions"])
self_service_router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

VALID_TIERS = {"FREE", "PREMIUM_INDIVIDUAL", "PREMIUM_TEAM"}

# Keep in sync with frontend/src/extensions/views/*/index.ts ids.
# "default" is deliberately excluded — it's always free for every user and
# is never gated behind a subscription (see TreeControls.tsx).
AVAILABLE_FILTERS = [
    {"key": "heritage", "label": "Heritage"},
    {"key": "timeline", "label": "Timeline"},
    {"key": "text-pedigree", "label": "Text Pedigree"},
    {"key": "poster", "label": "Family Tree Poster"},
]


def _ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else request.client.host if request.client else None


# ── Schemas ──────────────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    tier: str = Field(..., pattern="^(FREE|PREMIUM_INDIVIDUAL|PREMIUM_TEAM)$")
    # NULL/omitted = never expires. When set, this becomes a "promotional"
    # time-limited subscription — members lose entitlement once it passes.
    expires_at: Optional[datetime] = None


class SubscriptionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tier: Optional[str] = Field(None, pattern="^(FREE|PREMIUM_INDIVIDUAL|PREMIUM_TEAM)$")
    # Distinguish "field omitted" (leave unchanged) from "explicitly null"
    # (clear the expiration) via `model_fields_set` at the call site.
    expires_at: Optional[datetime] = None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    name: str
    tier: str
    expires_at: Optional[str]
    is_expired: bool
    filter_count: int
    member_count: int
    created_by: Optional[uuid.UUID]
    created_at: str
    updated_at: str


class FilterResponse(BaseModel):
    id: uuid.UUID
    filter_key: str
    added_by: Optional[uuid.UUID]
    added_at: str


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_display_name: str
    added_by: Optional[uuid.UUID]
    added_at: str


class AddFilterBody(BaseModel):
    filter_key: str = Field(..., min_length=1, max_length=50)


class AddMemberBody(BaseModel):
    user_id: uuid.UUID


class AvailableFilterResponse(BaseModel):
    key: str
    label: str


class MyFiltersResponse(BaseModel):
    filterKeys: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────

async def _get_subscription(session, sub_id: uuid.UUID, tenant_id: uuid.UUID) -> SubscriptionModel:
    sub = (await session.execute(
        select(SubscriptionModel).where(
            SubscriptionModel.id == sub_id,
            SubscriptionModel.tenant_id == tenant_id,
        )
    )).scalars().first()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    return sub


async def _counts(session, sub_id: uuid.UUID) -> tuple[int, int]:
    row = (await session.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM subscription_filters WHERE subscription_id = :sid) AS filter_count,
                (SELECT COUNT(*) FROM subscription_members WHERE subscription_id = :sid) AS member_count
        """),
        {"sid": sub_id},
    )).first()
    return row.filter_count, row.member_count


def _is_expired(expires_at: datetime | None) -> bool:
    return expires_at is not None and expires_at <= datetime.now(timezone.utc)


def _to_response(sub: SubscriptionModel, filter_count: int, member_count: int) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=sub.id,
        name=sub.name,
        tier=sub.tier,
        expires_at=sub.expires_at.isoformat() if sub.expires_at else None,
        is_expired=_is_expired(sub.expires_at),
        filter_count=filter_count,
        member_count=member_count,
        created_by=sub.created_by,
        created_at=sub.created_at.isoformat(),
        updated_at=sub.updated_at.isoformat(),
    )


# ── Endpoints — Subscriptions (Super Admin) ─────────────────────────────

@admin_router.get("", response_model=list[SubscriptionResponse],
                   summary="List all subscriptions in the tenant")
async def list_subscriptions(
    current_user: SuperAdminDep,
    session: SessionDep,
) -> list[SubscriptionResponse]:
    rows = (await session.execute(
        text("""
            SELECT
                s.id, s.name, s.tier, s.expires_at, s.created_by, s.created_at, s.updated_at,
                COUNT(DISTINCT sf.id) AS filter_count,
                COUNT(DISTINCT sm.id) AS member_count
            FROM subscriptions s
            LEFT JOIN subscription_filters sf ON sf.subscription_id = s.id
            LEFT JOIN subscription_members sm ON sm.subscription_id = s.id
            WHERE s.tenant_id = :tid
            GROUP BY s.id
            ORDER BY s.name
        """),
        {"tid": current_user.tenant_id},
    )).fetchall()

    return [
        SubscriptionResponse(
            id=r.id, name=r.name, tier=r.tier,
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
            is_expired=_is_expired(r.expires_at),
            filter_count=r.filter_count, member_count=r.member_count,
            created_by=r.created_by,
            created_at=r.created_at.isoformat(), updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]


@admin_router.get("/available-filters", response_model=list[AvailableFilterResponse],
                   summary="List all known filter keys that can be granted to a subscription")
async def list_available_filters(current_user: SuperAdminDep) -> list[AvailableFilterResponse]:
    return [AvailableFilterResponse(**f) for f in AVAILABLE_FILTERS]


@admin_router.post("", response_model=SubscriptionResponse,
                    status_code=status.HTTP_201_CREATED,
                    summary="Create a subscription")
async def create_subscription(
    body: SubscriptionCreate,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> SubscriptionResponse:
    existing = (await session.execute(
        select(SubscriptionModel).where(
            SubscriptionModel.tenant_id == current_user.tenant_id,
            SubscriptionModel.name == body.name,
        )
    )).scalars().first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                             f"A subscription named '{body.name}' already exists")

    sub = SubscriptionModel(
        tenant_id=current_user.tenant_id,
        name=body.name,
        tier=body.tier,
        expires_at=body.expires_at,
        created_by=current_user.id,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_CREATE", sub.name, _ip(request))
    await session.commit()
    return _to_response(sub, 0, 0)


@admin_router.patch("/{sub_id}", response_model=SubscriptionResponse,
                     summary="Update a subscription's name/tier")
async def update_subscription(
    sub_id: uuid.UUID,
    body: SubscriptionUpdate,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> SubscriptionResponse:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)

    if body.name is not None:
        sub.name = body.name
    if body.tier is not None:
        sub.tier = body.tier
    # "expires_at" being present in the request body at all (even as null,
    # to clear it) is what triggers a change — re-arms the reminder task
    # whenever the expiry actually moves.
    if "expires_at" in body.model_fields_set and body.expires_at != sub.expires_at:
        sub.expires_at = body.expires_at
        sub.reminder_sent_at = None

    await session.commit()
    await session.refresh(sub)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_UPDATE", sub.name, _ip(request))
    await session.commit()

    filter_count, member_count = await _counts(session, sub_id)
    return _to_response(sub, filter_count, member_count)


@admin_router.delete("/{sub_id}",
                      status_code=status.HTTP_204_NO_CONTENT,
                      response_model=None,
                      summary="Delete a subscription")
async def delete_subscription(
    sub_id: uuid.UUID,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> None:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)
    sub_name = sub.name
    await session.delete(sub)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_DELETE", sub_name, _ip(request))
    await session.commit()


# ── Endpoints — Subscription Filters (Super Admin) ──────────────────────

@admin_router.get("/{sub_id}/filters", response_model=list[FilterResponse],
                   summary="List filters granted by a subscription")
async def list_subscription_filters(
    sub_id: uuid.UUID,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> list[FilterResponse]:
    await _get_subscription(session, sub_id, current_user.tenant_id)

    rows = (await session.execute(
        select(SubscriptionFilterModel)
        .where(SubscriptionFilterModel.subscription_id == sub_id)
        .order_by(SubscriptionFilterModel.filter_key)
    )).scalars().all()

    return [
        FilterResponse(
            id=r.id, filter_key=r.filter_key,
            added_by=r.added_by, added_at=r.added_at.isoformat(),
        )
        for r in rows
    ]


@admin_router.post("/{sub_id}/filters", response_model=FilterResponse,
                    status_code=status.HTTP_201_CREATED,
                    summary="Add a filter to a subscription")
async def add_subscription_filter(
    sub_id: uuid.UUID,
    body: AddFilterBody,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> FilterResponse:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)

    known_keys = {f["key"] for f in AVAILABLE_FILTERS}
    if body.filter_key not in known_keys:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown filter key '{body.filter_key}'")

    dup = (await session.execute(
        select(SubscriptionFilterModel).where(
            SubscriptionFilterModel.subscription_id == sub_id,
            SubscriptionFilterModel.filter_key == body.filter_key,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "This filter is already in the subscription")

    entry = SubscriptionFilterModel(
        subscription_id=sub_id,
        filter_key=body.filter_key,
        added_by=current_user.id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_ADD_FILTER",
                            f"{sub.name} → {body.filter_key}", _ip(request))
    await session.commit()

    return FilterResponse(
        id=entry.id, filter_key=entry.filter_key,
        added_by=entry.added_by, added_at=entry.added_at.isoformat(),
    )


@admin_router.delete("/{sub_id}/filters/{filter_key}",
                      status_code=status.HTTP_204_NO_CONTENT,
                      response_model=None,
                      summary="Remove a filter from a subscription")
async def remove_subscription_filter(
    sub_id: uuid.UUID,
    filter_key: str,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> None:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)

    entry = (await session.execute(
        select(SubscriptionFilterModel).where(
            SubscriptionFilterModel.subscription_id == sub_id,
            SubscriptionFilterModel.filter_key == filter_key,
        )
    )).scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Filter not in this subscription")

    await session.delete(entry)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_REMOVE_FILTER",
                            f"{sub.name} → {filter_key}", _ip(request))
    await session.commit()


# ── Endpoints — Subscription Members (Super Admin) ──────────────────────

@admin_router.get("/{sub_id}/members", response_model=list[MemberResponse],
                   summary="List members entitled by a subscription")
async def list_subscription_members(
    sub_id: uuid.UUID,
    current_user: SuperAdminDep,
    session: SessionDep,
) -> list[MemberResponse]:
    await _get_subscription(session, sub_id, current_user.tenant_id)

    rows = (await session.execute(
        text("""
            SELECT
                sm.id, sm.user_id,
                u.email AS user_email,
                COALESCE(NULLIF(TRIM(CONCAT(u.given_name, ' ', u.family_name)), ''), u.email) AS user_display_name,
                sm.added_by, sm.added_at
            FROM subscription_members sm
            JOIN users u ON u.id = sm.user_id
            WHERE sm.subscription_id = :sid
            ORDER BY user_display_name
        """),
        {"sid": sub_id},
    )).fetchall()

    return [
        MemberResponse(
            id=r.id, user_id=r.user_id, user_email=r.user_email,
            user_display_name=r.user_display_name,
            added_by=r.added_by, added_at=r.added_at.isoformat(),
        )
        for r in rows
    ]


@admin_router.post("/{sub_id}/members", response_model=MemberResponse,
                    status_code=status.HTTP_201_CREATED,
                    summary="Add a user to a subscription")
async def add_subscription_member(
    sub_id: uuid.UUID,
    body: AddMemberBody,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> MemberResponse:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)

    user = (await session.execute(
        select(UserModel).where(
            UserModel.id == body.user_id,
            UserModel.tenant_id == current_user.tenant_id,
        )
    )).scalars().first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in this tenant")

    dup = (await session.execute(
        select(SubscriptionMemberModel).where(
            SubscriptionMemberModel.subscription_id == sub_id,
            SubscriptionMemberModel.user_id == body.user_id,
        )
    )).scalars().first()
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already in this subscription")

    entry = SubscriptionMemberModel(
        subscription_id=sub_id,
        user_id=body.user_id,
        added_by=current_user.id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    user_display = f"{user.given_name or ''} {user.family_name or ''}".strip() or user.email
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_ADD_MEMBER",
                            f"{sub.name} → {user_display}", _ip(request))
    await session.commit()

    return MemberResponse(
        id=entry.id, user_id=entry.user_id, user_email=user.email,
        user_display_name=user_display,
        added_by=entry.added_by, added_at=entry.added_at.isoformat(),
    )


@admin_router.delete("/{sub_id}/members/{member_id}",
                      status_code=status.HTTP_204_NO_CONTENT,
                      response_model=None,
                      summary="Remove a user from a subscription")
async def remove_subscription_member(
    sub_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: SuperAdminDep,
    session: SessionDep,
    request: Request,
) -> None:
    sub = await _get_subscription(session, sub_id, current_user.tenant_id)

    entry = (await session.execute(
        select(SubscriptionMemberModel).where(
            SubscriptionMemberModel.id == member_id,
            SubscriptionMemberModel.subscription_id == sub_id,
        )
    )).scalars().first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not in this subscription")

    user_row = (await session.execute(
        text("SELECT email, given_name, family_name FROM users WHERE id = :uid LIMIT 1"),
        {"uid": entry.user_id},
    )).first()
    user_display = (
        f"{user_row.given_name or ''} {user_row.family_name or ''}".strip() or user_row.email
        if user_row else str(entry.user_id)
    )

    await session.delete(entry)
    await log_admin_action(session, current_user.tenant_id, current_user.id,
                            current_user.full_name, "SUB_REMOVE_MEMBER",
                            f"{sub.name} → {user_display}", _ip(request))
    await session.commit()


# ── Endpoints — Self-service entitlement (any verified user) ───────────

@self_service_router.get("/my-filters", response_model=MyFiltersResponse,
                          summary="List filter keys the current user is entitled to via their subscriptions")
async def get_my_filters(
    current_user: VerifiedUserDep,
    session: SessionDep,
) -> MyFiltersResponse:
    # Super Admin is opted out of the subscription model entirely — every
    # gate-able filter is always available, regardless of any subscription
    # membership (or lack thereof).
    if current_user.app_role == AppRole.SUPER_ADMIN:
        return MyFiltersResponse(filterKeys=[f["key"] for f in AVAILABLE_FILTERS])

    rows = (await session.execute(
        text("""
            SELECT DISTINCT sf.filter_key
            FROM subscription_filters sf
            JOIN subscription_members sm ON sm.subscription_id = sf.subscription_id
            JOIN subscriptions s ON s.id = sf.subscription_id
            WHERE sm.user_id = :uid
              AND (s.expires_at IS NULL OR s.expires_at > now())
        """),
        {"uid": current_user.id},
    )).fetchall()
    return MyFiltersResponse(filterKeys=[r.filter_key for r in rows])
